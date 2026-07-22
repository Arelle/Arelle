"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from collections import defaultdict, OrderedDict
from typing import TYPE_CHECKING, Any, Callable

from arelle import XmlUtil, XbrlConst
from arelle.formula.XPathParser import parse
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelValue import qname, QName
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import (
    Trace,
    ModelFormulaResource,
    ModelFormulaRules,
    ModelConceptName,
    ModelParameter,
    )
from arelle.Aspect import Aspect, aspectStr, aspectModels, aspectRuleAspects, aspectModelAspect
from arelle.ModelInstanceObject import ModelFact
from arelle.formula.FormulaEvaluator import (
    filterFacts as formulaEvaluatorFilterFacts,
    aspectsMatch,
    factsPartitions,
    VariableBinding,
    )
from arelle.formula.XPathContext import XPathException
from arelle.PrototypeInstanceObject import FactPrototype

from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing_extensions import Self

    from arelle.ModelDocument import ModelDocument
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelDtsObject import ModelRelationship
    from arelle.formula.XPathParser import ExpressionStack, RecursiveFormulaTokens
    from arelle.formula.XPathContext import XPathContext, ContextItem

_: TypeGetText

NoneType = type(None)
OPEN_ASPECT_ENTRY_SURROGATE = "\uDBFF"  # this needs to be a utf-8 compatible char
UNREPORTED_ASPECT_SORT_VALUE = "\uDBFE"  # high sort order for unreported aspect
EMPTY_SET: set[Any] = set()
EMPTY_DICT: dict[Any, Any] = {}
ROLLUP_SPECIFIES_MEMBER = 1
ROLLUP_IMPLIES_DEFAULT_MEMBER = 2
ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE = 3
ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE = 4
ROLLUP_FOR_CLOSED_DEFINITION_NODE = 5
ROLLUP_FOR_OPEN_DEFINITION_NODE = 6
ROLLUP_FOR_DEFINITION_NODE = 7

TABLE_PERIOD_SELECTORS = {"table.periodStart", "table.periodEnd"}


class ResolutionException(Exception):
    def __init__(self, code: str, message: str, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.code = code
        self.message = message
        self.args = (self.__repr__(),)

    def __repr__(self) -> str:
        return _("[{0}] exception {1}").format(self.code, self.message % self.kwargs)


class LytMdlTableModel:
    def __init__(self, entryPointUrl: str | None) -> None:
        self.entryPointUrl = entryPointUrl
        self.lytMdlTableSets: list[LytMdlTableSet] = []

    def __repr__(self) -> str:
        return f"LytMdlTableModel[{self.entryPointUrl}]"


class LytMdlTableSet:
    def __init__(
        self,
        lytMdlTableModel: LytMdlTableModel,
        strctMdlTableSet: StrctMdlTableSet,
        label: str | None,
        srcFile: str | None,
        srcLine: int | None,
        srcLinkrole: str | None,
    ) -> None:
        self.lytMdlTableModel = lytMdlTableModel
        self.strctMdlTableSet = strctMdlTableSet
        self.label = label
        self.srcFile = srcFile
        self.srcLine = srcLine
        self.srcLinkrole = srcLinkrole
        lytMdlTableModel.lytMdlTableSets.append(self)
        self.lytMdlTables: list[LytMdlTable] = []

    def __repr__(self) -> str:
        return f"LytMdlTableSet[{self.label}]"


class LytMdlTable:
    def __init__(self, lytMdlTableSet: LytMdlTableSet, strctMdlTable: StrctMdlTable) -> None:
        self.lytMdlParentTableSet = lytMdlTableSet
        self.strctMdlTable = strctMdlTable
        self.lytMdlHeaders: list[LytMdlHeaders] = []
        lytMdlTableSet.lytMdlTables.append(self)
        self.lytMdlBodyChildren: list[LytMdlBodyCells | LytMdlBodyCell] = []

    def lytMdlAxisHeaders(self, axis: str) -> LytMdlHeaders | None:
        for lytMdlHeader in self.lytMdlHeaders:
            if lytMdlHeader.axis == axis:
                return lytMdlHeader
        return None

    def headerDepth(self, axis: str, includeOpenAspectEntrySurrogates: bool = False) -> int:
        # number of column header rows or number, row header columns, etc
        return sum(lytMdlHeader.maxNumLabels
                   for lytMdlGroup in getattr(self.lytMdlAxisHeaders(axis), "lytMdlGroups", [])
                   for lytMdlHeader in lytMdlGroup.lytMdlHeaders
                   if includeOpenAspectEntrySurrogates or
                      not all(lytMdlCell.isOpenAspectEntrySurrogate
                              for lytMdlCell in lytMdlHeader.lytMdlCells))

    def numBodyCells(self, axis: str) -> int:
        return max((sum(lytMdlCell.span  # type: ignore[no-any-return]
                        for lytMdlHdr in lytMdlGrp.lytMdlHeaders
                        for lytMdlCell in lytMdlHdr.lytMdlCells)
                    for lytMdlGrp in getattr(self.lytMdlAxisHeaders(axis), "lytMdlGroups", [])))

    def __repr__(self) -> str:
        return "LytMdlTable[]"


class LytMdlHeaders:
    def __init__(self, lytMdlTable: LytMdlTable, axis: str) -> None:
        self.lytMdlParentTable = lytMdlTable
        self.axis = axis
        lytMdlTable.lytMdlHeaders.append(self)
        self.lytMdlGroups: list[LytMdlGroup] = []

    def __repr__(self) -> str:
        return f"LytMdlHeaders[{self.axis}]"


class LytMdlGroup:
    def __init__(
        self,
        lytMdlHeaders: LytMdlHeaders,
        label: str | None,
        srcFile: str | None,
        srcLine: int | None,
    ) -> None:
        self.lytMdlParentHeaders = lytMdlHeaders
        self.label = label
        self.srcFile = srcFile
        self.srcLine = srcLine
        lytMdlHeaders.lytMdlGroups.append(self)
        self.lytMdlHeaders: list[LytMdlHeader] = []

    def __repr__(self) -> str:
        return f"LytMdlGroup[{self.label}]"


class LytMdlHeader:
    def __init__(self, lytMdlGroup: LytMdlGroup) -> None:
        self.lytMdlParentGroup = lytMdlGroup
        lytMdlGroup.lytMdlHeaders.append(self)
        self.lytMdlCells: list[LytMdlCell] = []

    @property
    def maxNumLabels(self) -> int:
        return max(len(lytMdlCell.labels) or len(lytMdlCell.lytMdlConstraints)
                   for lytMdlCell in self.lytMdlCells)

    def __repr__(self) -> str:
        return "LytMdlHeader[]"


class LytMdlCell:
    def __init__(self) -> None:
        self.lytMdlParentHeader: LytMdlHeader | None = None
        self.labels: list[tuple[str, str | None, str | None]] = []
        self.span: int = 1
        self.rollup: int | bool | None = None
        self.id: str | None = None
        self.isOpenAspectEntrySurrogate: bool | None = None
        self.lytMdlConstraints: list[LytMdlConstraint] = []

    def labelXmlText(self, iLabel: int, default: str = "") -> str | None:
        if self.labels and iLabel < len(self.labels):
            return self.labels[iLabel][0]
        if self.lytMdlConstraints and iLabel < len(self.lytMdlConstraints):
            return self.lytMdlConstraints[iLabel].label
        return default

    def __repr__(self) -> str:
        return f"LytMdlCell[{self.labels}]"


class LytMdlConstraint:
    def __init__(self, lytMdlCell: LytMdlCell, tag: str | None) -> None:
        self.lytMdlParentCell = lytMdlCell
        self.tag = tag
        self.aspect: QName | None = None
        self.value: QName | ModelObject | None = None
        self.label: str | None = None
        lytMdlCell.lytMdlConstraints.append(self)

    def __repr__(self) -> str:
        return f"LytMdlConstraint[{self.aspect}]"

    def __str__(self) -> str:
        # value to use in html and GUI representations
        if self.value is not None:
            if isinstance(self.value, QName):
                return str(self.value)
            if hasattr(self.value, "value"):
                return self.value.value  # type: ignore[no-any-return]
            elif hasattr(self.value, "stringValue"):
                return XmlUtil.innerTextList(self.value)
            return str(self.value)
        if isinstance(self.aspect, QName):
            return str(self.aspect)
        return ""


class LytMdlBodyCells:
    def __init__(self, lytMdlParent: LytMdlTable | LytMdlBodyCells, axis: str) -> None:
        self.lytMdlParent = lytMdlParent
        self.axis = axis
        # z body cells contain y's body cells; y body cells contain x's body cells; x's body cells contain individual cells
        self.lytMdlBodyChildren: list[LytMdlBodyCells | LytMdlBodyCell] = []
        lytMdlParent.lytMdlBodyChildren.append(self)

    def __repr__(self) -> str:
        return f"LytMdlBodyCells[{self.axis}]"


class LytMdlBodyCell:
    def __init__(self, lytMdlParent: LytMdlTable, isOpenAspectEntrySurrogate: bool = False) -> None:
        self.lytMdlParent = lytMdlParent
        self.isOpenAspectEntrySurrogate = isOpenAspectEntrySurrogate
        lytMdlParent.lytMdlBodyChildren.append(self)
        self.facts: tuple[tuple[ModelFact, Any, str], ...] = ()  # bound facts

    def __repr__(self) -> str:
        return f"LytMdlBodyCell[{', '.join(v for f, v, j in self.facts)}]"


def definitionNodes(nodes: Iterable[Any]) -> list[Any]:
    return [node.definitionNodeObject if isinstance(node, StrctMdlStructuralNode) else node for node in nodes]  # type: ignore[attr-defined]


def parentChildOrder(node: ModelFormulaResource) -> str | None:
    _parentChildOrder = node.get("parentChildOrder")
    if _parentChildOrder:
        return _parentChildOrder
    # look for inherited parentChildOrder
    for rel in node.modelXbrl.relationshipSet(node.ancestorArcroles).toModelObject(node):  # type: ignore[union-attr, attr-defined]
        if rel.fromModelObject is not None:
            _parentChildOrder = parentChildOrder(rel.fromModelObject)  # type: ignore[arg-type]
            if _parentChildOrder:
                return _parentChildOrder
    return None


def aspectStrctNodes(strctNode: StrctMdlNode | None) -> dict[int, set[Any]]:
    if strctNode is None:
        return EMPTY_DICT
    _aspectStrctNodes: defaultdict[int, set[Any]] = defaultdict(set)
    for aspect in aspectModels["dimensional"]:
        strctNodeDefiningAspect = strctNode.hasAspect(aspect)
        if not strctNodeDefiningAspect:
            for a in aspectRuleAspects.get(aspect, ()):
                strctNodeDefiningAspect = strctNode.hasAspect(a)
                if strctNodeDefiningAspect:
                    break
        if strctNodeDefiningAspect:
            if aspect == Aspect.DIMENSIONS:
                for dim in (strctNode.aspectValue(Aspect.DIMENSIONS) or ()):  # type: ignore[attr-defined]
                    _aspectStrctNodes[dim].add(strctNodeDefiningAspect)
            else:
                if aspect in aspectRuleAspects:
                    _strctNodeDefiningAspect = None
                    for asp in aspectRuleAspects[aspect]:
                        _strctNodeDefiningAspect = strctNode.hasAspect(asp)
                        if _strctNodeDefiningAspect:
                            _aspectStrctNodes[asp].add(_strctNodeDefiningAspect)
                    if not _strctNodeDefiningAspect:  # use top level aspect, e.g. PERIOD instead of PERIOD_START...
                        _aspectStrctNodes[aspect].add(strctNodeDefiningAspect)
                else:
                    _aspectStrctNodes[aspect].add(strctNodeDefiningAspect)
    return _aspectStrctNodes


# Structural model
class StrctMdlNode:
    # attributes provided by subclasses or set dynamically at runtime
    _rendrCntx: XPathContext
    _axis: str
    _tagSelectors: set[str | None]
    abstract: bool
    tableNode: DefnMdlTable | None
    aspectEntryObjectId: str
    parentOrdinateContext: bool
    hasOpenNode: bool

    def __init__(self, strctMdlParentNode: StrctMdlNode | None, defnMdlNode: DefnMdlDefinitionNode | None = None) -> None:
        self.defnMdlNode = defnMdlNode
        self.strctMdlParentNode = strctMdlParentNode
        self.strctMdlChildNodes: list[StrctMdlNode] = []
        if strctMdlParentNode:
            strctMdlParentNode.strctMdlChildNodes.append(self)
        self.aspects: dict[int, set[Any]] = {}
        self.hasChildRollup: bool = False
        self.contextItemBinding: VariableBinding | None = None
        self.variables: dict[QName, Any] = {}
        self.zInheritance: Any = None
        self.rollup: int | bool = False  # true when this is the rollup node among its siblings
        self.choiceNodeIndex: int = 0
        self.tagSelector: str | None = getattr(defnMdlNode, "tagSelector", None)
        self.isUnreported: bool = False

    @property
    def axis(self) -> str:
        return getattr(self, "_axis", self.strctMdlParentNode.axis if self.strctMdlParentNode else "")

    @property
    def depth(self) -> int:
        return self.strctMdlParentNode.depth + 1 if self.strctMdlParentNode else 0

    def aspectsCovered(self, inherit: bool = False) -> set[Any]:
        return EMPTY_SET

    def hasAspect(self, aspect: int, inherit: bool = True) -> Self | None:
        return None  # if aspect found would return its defining structural node

    @property
    def parentChildOrder(self) -> str | None:
        if self.defnMdlNode is not None:
            return self.defnMdlNode.parentChildOrder
        return "parent-first"  # default value

    @property
    def hasRollUpChild(self) -> bool:
        return any(c.hasChildRollup for c in self.strctMdlChildNodes)

    @property
    def tagSelectors(self) -> set[str | None]:
        try:
            return self._tagSelectors
        except AttributeError:
            if self.strctMdlParentNode is not None:
                self._tagSelectors = self.strctMdlParentNode.tagSelectors.copy()
            else:
                self._tagSelectors = set()
            if not self.rollup and isinstance(self.defnMdlNode, DefnMdlConceptRelationshipNode):
                self._tagSelectors -= TABLE_PERIOD_SELECTORS  # these can't inherit
            else:
                _defnTagSelector = getattr(self.defnMdlNode, "tagSelector", None)
                if _defnTagSelector:
                    self._tagSelectors.add(_defnTagSelector)
            if self.tagSelector:
                self._tagSelectors.add(self.tagSelector)
            return self._tagSelectors

    @tagSelectors.setter
    def tagSelectors(self, newValue: set[str | None]) -> None:
        self._tagSelectors = newValue

    @property
    def leafNodeCount(self) -> int:
        childLeafCount = 0
        if self.strctMdlChildNodes:
            for strctMdlChildNode in self.strctMdlChildNodes:
                childLeafCount += strctMdlChildNode.leafNodeCount
        if childLeafCount == 0:
            return 1
        if not self.isAbstract and isinstance(self.defnMdlNode, DefnMdlClosedDefinitionNode):
            childLeafCount += 1  # has a roll up
        return childLeafCount

    @property
    def cardinalityAndDepth(self) -> tuple[int, int]:
        if self.defnMdlNode is not None:
            return self.defnMdlNode.cardinalityAndDepth(self)
        return 1, 0  # no breakdown

    def objectId(self, refId: str = "") -> str | None:
        if self.defnMdlNode is not None:
            return self.defnMdlNode.objectId(refId)
        return None

    @property
    def xlinkLabel(self) -> str | None:
        if self.defnMdlNode is not None:
            return self.defnMdlNode.xlinkLabel
        return None

    @property
    def structuralDepth(self) -> int:
        return 0

    @property
    def childRollupStrctNode(self) -> StrctMdlNode | None:
        for childStrctNode in self.strctMdlChildNodes:
            if childStrctNode.rollup:
                return childStrctNode
            grandchildStrctRollup = childStrctNode.childRollupStrctNode
            if grandchildStrctRollup:
                return grandchildStrctRollup
        return None

    def headerAndSource(
        self,
        role: str | None = None,
        lang: str | None = None,
        evaluate: bool = True,
        returnGenLabel: bool = True,
        returnMsgFormatString: bool = False,
        recurseParent: bool = True,
        returnStdLabel: bool = True,
        layoutMdlSortOrder: bool = False,
    ) -> tuple[str | None, str | None]:
        if self.defnMdlNode is None:  # root
            return None, None
        if returnGenLabel:
            label = self.defnMdlNode.genLabel(role=role, lang=lang)
            if label:
                return label, None  # explicit is default source
        if self.isEntryAspect and role is None:
            # True if open node bound to a prototype, false if bound to a real fact
            return OPEN_ASPECT_ENTRY_SURROGATE, None  # sort pretty high, work ok for python 2.7/3.2 as well as 3.3
        # if there's a child roll up, check for it
        if self.childRollupStrctNode is not None:  # check the rolling-up child too
            label, typ = self.childRollupStrctNode.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent)
            if label:
                return label, typ
        # if aspect is a concept of dimension, return its standard label
        concept = None
        if role is None and returnStdLabel:
            for aspect in self.aspectsCovered():
                aspectValue = self.aspectValue(aspect, inherit=recurseParent)  # type: ignore[attr-defined]
                if isinstance(aspect, QName) or aspect == Aspect.CONCEPT:  # dimension or concept
                    if isinstance(aspectValue, QName):
                        concept = self.modelXbrl.qnameConcepts.get(aspectValue)  # type: ignore[attr-defined]
                        break
                    elif isinstance(aspectValue, ModelDimensionValue):
                        if aspectValue.isExplicit:
                            concept = aspectValue.member
                        elif aspectValue.isTyped:
                            return XmlUtil.innerTextList(aspectValue.typedMember), "processor"  # type: ignore[arg-type]
                    elif aspectValue is None:
                        dimConcept = self.modelXbrl.qnameConcepts[aspect]  # type: ignore[attr-defined]
                        if dimConcept.isTypedDimension:
                            if layoutMdlSortOrder:
                                return UNREPORTED_ASPECT_SORT_VALUE, "processor"
                elif isinstance(aspectValue, ModelObject):
                    text = XmlUtil.innerTextList(aspectValue)
                    if aspect == Aspect.PERIOD:
                        cntx = aspectValue.getparent()
                        if layoutMdlSortOrder:
                            if cntx.isInstantPeriod:  # type: ignore[union-attr]
                                text = "1 " + text  # sort inst first for conformance suite
                            elif cntx.isStartEndPeriod:  # type: ignore[union-attr]
                                text = "2 " + text  # sort startEnd second for conformance suite
                            elif cntx.isForeverPeriod:  # type: ignore[union-attr]
                                text = "3 forever "  # sort forever third for conformance suite
                        elif cntx.isForeverPeriod:  # type: ignore[union-attr]
                            text = "forever"
                    elif aspect == Aspect.UNIT:
                        text = f"{aspectValue.objectIndex:05d} {text}"  # conf suites use instance order of contexts
                    elif aspect == Aspect.ENTITY_IDENTIFIER and layoutMdlSortOrder:
                        text = f"{aspectValue.get('scheme')}#{aspectValue.stringValue}"
                    return text, "processor"
        # TODO for conformance, concept should not be contributing labels
        if concept is not None and layoutMdlSortOrder:
            label = concept.label(lang=lang)
            if label:
                return label, "processor"
        # if there is a role, check if it's available on a parent node
        if role and recurseParent and self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent)
        return None, None

    def header(
        self,
        role: str | None = None,
        lang: str | None = None,
        evaluate: bool = True,
        returnGenLabel: bool = True,
        returnMsgFormatString: bool = False,
        recurseParent: bool = True,
        returnStdLabel: bool = True,
        layoutMdlSortOrder: bool = False,
    ) -> str | None:
        return self.headerAndSource(role, lang, evaluate, returnGenLabel, returnMsgFormatString, recurseParent, returnStdLabel, layoutMdlSortOrder)[0]

    @property
    def isAbstract(self) -> bool:
        try:
            try:
                return self.abstract  # ordinate may have an abstract attribute
            except AttributeError:  # if none use axis object
                return self.defnMdlNode.isAbstract  # type: ignore[union-attr]
        except AttributeError:  # axis may never be abstract
            return False

    @property
    def isEntryAspect(self) -> bool:
        # true if open node and bound to a fact prototype
        return self.contextItemBinding is not None and isinstance(self.contextItemBinding.yieldedFact, FactPrototype)

    def isEntryPrototype(self, default: bool = False) -> bool:
        # true if all axis open nodes before this one are entry prototypes (or not open axes)
        if self.contextItemBinding is not None:
            # True if open node bound to a prototype, false if bound to a real fact
            return isinstance(self.contextItemBinding.yieldedFact, FactPrototype)
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.isEntryPrototype(default)
        return default  # nothing open to be bound to a fact

    def evaluate(
        self,
        evalObject: ModelObject,
        evalMethod: Callable[[XPathContext, ...], Any],  # type: ignore[misc]
        otherAxisStructuralNode: StrctMdlNode | None = None,
        evalArgs: tuple[Any, ...] = (),
        handleXPathException: bool = True,
        **kwargs: Any,
    ) -> Any:
        xc = self._rendrCntx
        if self.contextItemBinding and not isinstance(xc.contextItem, ModelFact):
            previousContextItem = xc.contextItem  # xbrli.xbrl
            xc.contextItem = self.contextItemBinding.yieldedFact
        else:
            previousContextItem = None
        variables = self.variables
        removeVarQnames: list[QName] = []
        for qn, value in variables.items():
            if qn not in xc.inScopeVars:
                removeVarQnames.append(qn)
                xc.inScopeVars[qn] = value
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            result = self.strctMdlParentNode.evaluate(evalObject, evalMethod, otherAxisStructuralNode, evalArgs)
        elif otherAxisStructuralNode is not None:
            # recurse to other ordinate (which will recurse to z axis)
            result = otherAxisStructuralNode.evaluate(evalObject, evalMethod, None, evalArgs)
        elif self.zInheritance is not None:
            result = self.zInheritance.evaluate(evalObject, evalMethod, None, evalArgs)
        else:
            try:
                result = evalMethod(xc, *evalArgs)
            except XPathException as err:
                if not handleXPathException:
                    raise
                xc.modelXbrl.error(err.code,
                         _("%(element)s set %(xlinkLabel)s \nException: %(error)s"),
                         modelObject=evalObject, element=evalObject.localName,
                         xlinkLabel=evalObject.xlinkLabel, error=err.message)
                result = ""
        for qn in removeVarQnames:
            xc.inScopeVars.pop(qn)
        if previousContextItem is not None:
            xc.contextItem = previousContextItem  # xbrli.xbrl
        return result

    def hasValueExpression(self, otherAxisStructuralNode: StrctMdlNode | None = None) -> bool:
        return (self.defnMdlNode.hasValueExpression or  # type: ignore[union-attr]
                not isinstance(otherAxisStructuralNode, StrctMdlBreakdown) and
                (otherAxisStructuralNode is not None and
                 otherAxisStructuralNode.defnMdlNode is not None and
                 otherAxisStructuralNode.defnMdlNode.hasValueExpression))

    def evalValueExpression(self, fact: Any, otherAxisStructuralNode: StrctMdlNode | None = None) -> Any:
        for structuralNode in (self, otherAxisStructuralNode):
            if (structuralNode is not None and
                structuralNode.defnMdlNode is not None and
                structuralNode.defnMdlNode.hasValueExpression):
                return self.evaluate(self.defnMdlNode, structuralNode.defnMdlNode.evalValueExpression, otherAxisStructuralNode=otherAxisStructuralNode, evalArgs=(fact,))  # type: ignore[arg-type]
        return None

    @property
    def hasBreakdownWithoutNodes(self) -> bool:
        if isinstance(self, StrctMdlBreakdown) and not self.strctMdlChildNodes:
            return True
        for childStructuralNode in self.strctMdlChildNodes:
            if childStructuralNode.hasBreakdownWithoutNodes:
                return True
        return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}[{self.xlinkLabel}]"


class StrctMdlTableSet(StrctMdlNode):
    def __init__(self, defnMdlTable: DefnMdlDefinitionNode | None) -> None:
        super(StrctMdlTableSet, self).__init__(None, defnMdlTable)


class StrctMdlTable(StrctMdlNode):
    def __init__(self, strctMdlParentNode: StrctMdlNode | None, defnMdlTable: DefnMdlDefinitionNode | None) -> None:
        super(StrctMdlTable, self).__init__(strctMdlParentNode, defnMdlTable)
        self._rendrCntx = defnMdlTable.renderingXPathContext  # type: ignore[union-attr]
        # childStrctMdlNodes are StrctMdlBreakdowns
        self.defnMdlBreakdowns: dict[Any, list[Any]] = defaultdict(list)
        self.axisDepth: dict[str, int] = {"x": 0, "y": 0, "z": 0}
        self.layoutMdlCells: list[Any] = []  # z body cells
        self.tblParamValues: OrderedDict[Any, Any] = OrderedDict()

    def strctMdlFirstAxisBreakdown(self, axis: str) -> StrctMdlNode | None:
        for c in self.strctMdlChildNodes:
            if c._axis == axis:
                return c
        return None


class StrctMdlBreakdown(StrctMdlNode):
    # breakdown also acts as the layout model group containing headers of cells
    def __init__(self, strctMdlParentNode: StrctMdlNode, defnMdlBreakdown: DefnMdlDefinitionNode | None, axis: str) -> None:
        super(StrctMdlBreakdown, self).__init__(None, defnMdlBreakdown)
        self._rendrCntx = strctMdlParentNode._rendrCntx  # copy from parent except at root
        self._axis = axis
        self.rendrCntx = strctMdlParentNode._rendrCntx
        self.hasOpenNode = False
        self.isLabeled: bool = False
        self.layoutMdlHdrCells: list[Any] = []  # layoutMdlHeaderCells objects

        # find all leaf not of the parent to add it to them (see 9.3.2)
        self.strctMdlParentNode = strctMdlParentNode
        if isinstance(strctMdlParentNode, StrctMdlBreakdown):
            self._addBreakdownToLeafs(strctMdlParentNode, set())
        else:
            strctMdlParentNode.strctMdlChildNodes.append(self)

    def _addBreakdownToLeafs(self, sn: StrctMdlNode, alreadyAddedTo: set[StrctMdlNode]) -> None:
        if not sn.strctMdlChildNodes:
            if sn not in alreadyAddedTo:
                sn.strctMdlChildNodes.append(self)
                alreadyAddedTo.add(sn)
        else:
            for c in sn.strctMdlChildNodes:
                self._addBreakdownToLeafs(c, alreadyAddedTo)

    def siblingBreakdownNode(self) -> tuple[StrctMdlNode, ...]:
        if self.strctMdlParentNode is not None:
            for sibling in self.strctMdlParentNode.strctMdlChildNodes[
                                    self.strctMdlParentNode.strctMdlChildNodes.index(self) + 1:]:
                if sibling._axis == self._axis:
                    return (sibling,)
        return ()

    @property
    def strctMdlAncestorBreakdownNode(self) -> Self:
        return self

    @property
    def strctMdlEffectiveChildNodes(self) -> Iterable[StrctMdlNode]:
        if self.strctMdlChildNodes:  # not leaf
            return self.strctMdlChildNodes
        # effective child nodes at a leaf node is sibling beakdown node subtee
        return self.siblingBreakdownNode()

    def setHasOpenNode(self) -> None:
        self.hasOpenNode = True

    def inheritedAspectValue(self, *args: Any) -> Any:
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.inheritedAspectValue(*args)
        else:
            return None

    # for __hash__ and __eq__: at some point, the breakdown is used a key of a dict
    # when 2 same axis exist, multiple breakdown for the same definition node can be created
    # but we want to only have one as key
    # (see headerElts in ViewFileRenderedGrid.py)
    def __hash__(self) -> int:
        return self.defnMdlNode.__hash__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StrctMdlBreakdown):
            return NotImplemented
        return self.defnMdlNode == other.defnMdlNode


class StrctMdlStructuralNode(StrctMdlNode):
    def __init__(
        self,
        strctMdlParentNode: StrctMdlNode | None,
        defnMdlNode: DefnMdlDefinitionNode | None,
        zInheritance: Any = None,
        contextItemFact: Any = None,
        tableNode: DefnMdlTable | None = None,
        rendrCntx: XPathContext | None = None,
    ) -> None:
        super(StrctMdlStructuralNode, self).__init__(strctMdlParentNode, defnMdlNode)
        self._rendrCntx = rendrCntx or strctMdlParentNode._rendrCntx  # type: ignore[union-attr] # copy from parent except at root
        self.zInheritance = zInheritance
        if contextItemFact is not None:
            self.contextItemBinding = VariableBinding(self._rendrCntx,  # type: ignore[no-untyped-call]
                                                      boundFact=contextItemFact)
            if isinstance(self.contextItemBinding.yieldedFact, FactPrototype):
                for aspect in defnMdlNode.aspectsCovered():  # type: ignore[union-attr]
                    if aspect != Aspect.DIMENSIONS:
                        self.aspectEntryObjectId = self.aspects[aspect] = contextItemFact.aspectEntryObjectId
                        break
        else:
            self.contextItemBinding = None
        if tableNode is not None:
            self.tableNode = tableNode
        self.isLabeled = True

    @property
    def modelXbrl(self) -> ModelXbrl | None:
        return self.defnMdlNode.modelXbrl  # type: ignore[union-attr]

    @property
    def structuralDepth(self) -> int:
        if self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.structuralDepth + 1
        return 0

    def siblingBreakdownNode(self) -> tuple[StrctMdlNode, ...]:
        if self.strctMdlParentNode is not None:
            return self.strctMdlParentNode.siblingBreakdownNode()  # type: ignore[attr-defined, no-any-return]
        return ()

    @property
    def strctMdlEffectiveChildNodes(self) -> Iterable[StrctMdlNode]:
        if self.strctMdlChildNodes:  # not leaf
            # if nested breakdown which is unlabeled return children of breakdown
            if len(self.strctMdlChildNodes) == 1 and isinstance(self.strctMdlChildNodes[0], StrctMdlBreakdown):  # nested layout node
                return self.strctMdlChildNodes[0].strctMdlChildNodes
            return self.strctMdlChildNodes
        # effective child nodes at a leaf node is sibling beakdown node subtee
        return self.siblingBreakdownNode()

    @property
    def strctMdlAncestorBreakdownNode(self) -> StrctMdlBreakdown | None:
        if isinstance(self.strctMdlParentNode, StrctMdlBreakdown):
            return self.strctMdlParentNode
        return self.strctMdlParentNode.strctMdlAncestorBreakdownNode  # type: ignore[no-any-return, union-attr]

    def constraintSet(self, tagSelectors: set[str | None] | None = None) -> Any:
        defnMdlNode = self.defnMdlNode
        if defnMdlNode is None:
            return None  # root node
        # may be both a period override and other in the selectors

        if tagSelectors:
            ts = set(tagSelectors)
            if TABLE_PERIOD_SELECTORS & ts and len(ts & defnMdlNode.constraintSets.keys()) > 1:
                return defnMdlNode.constraintSets[(TABLE_PERIOD_SELECTORS & ts & defnMdlNode.constraintSets.keys()).pop()]  # type: ignore[index]

            for tag in tagSelectors:
                if tag in defnMdlNode.constraintSets:
                    return defnMdlNode.constraintSets[tag]
        return defnMdlNode.constraintSets.get(None)  # returns None if no default constraint set

    def constraintTags(self) -> list[Any] | None:
        defnMdlNode = self.defnMdlNode
        if defnMdlNode is None:
            return None  # root node
        return list(defnMdlNode.constraintSets.keys())

    def aspectsCovered(self, inherit: bool = False) -> set[int]:
        if self.aspects is None:
            return EMPTY_SET
        aspectsCovered = set(self.aspects.keys())
        if self.defnMdlNode is not None and hasattr(self.defnMdlNode, "aspectsCovered"):
            aspectsCovered |= self.defnMdlNode.aspectsCovered()
        if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            aspectsCovered |= self.strctMdlParentNode.aspectsCovered(inherit=inherit)
        elif inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            aspectsCovered |= self.strctMdlParentNode.strctMdlParentNode.aspectsCovered(inherit=inherit)  # type: ignore[union-attr]
        return aspectsCovered

    def hasAspect(self, aspect: int, inherit: bool = True) -> Self | None:
        if (aspect in self.aspects or
            (self.defnMdlNode is not None and self.defnMdlNode.hasAspect(self, aspect))):
            return self
        if inherit:
            # block override of aspect rule aspects, e.g. don't inherit period duration aspects if this str node defines an instant aspect
            if any(aspect in _aspectRuleAspects and self.hasAspect(_aspect, inherit=False)
                   for _aspect, _aspectRuleAspects in aspectRuleAspects.items()):
                return None
            if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
                return self.strctMdlParentNode.hasAspect(aspect, inherit)  # type: ignore[return-value]
            if isinstance(self.strctMdlParentNode, StrctMdlBreakdown):
                return self.strctMdlParentNode.strctMdlParentNode.hasAspect(aspect, inherit)  # type: ignore[union-attr,return-value]
        return None

    def dimRAV(self, aspect: Any, value: Any) -> Any:  # dimensional rollup aspect value (None for a rollup node)
        if isinstance(value, QName) and self.rollup == ROLLUP_IMPLIES_DEFAULT_MEMBER and aspect in self.defnMdlNode.modelXbrl.qnameDimensionDefaults:  # type: ignore[union-attr]
            return self.defnMdlNode.modelXbrl.qnameDimensionDefaults[aspect]  # type: ignore[union-attr]
        return value

    def aspectValue(
        self,
        aspect: int ,
        inherit: bool = True,
        dims: set[Any] | None = None,
        depth: int = 0,
        tagSelectors: set[str | None] | None = None,
    ) -> Any:
        if self.rollup in (ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE):
            return self.strctMdlParentNode.aspectValue(aspect, inherit, dims, depth, tagSelectors)  # type: ignore[union-attr]
        xc = self._rendrCntx
        aspects = self.aspects
        defnMdlNode = self.defnMdlNode
        contextItemBinding = self.contextItemBinding
        constraintSet = self.constraintSet(tagSelectors)
        if aspect == Aspect.DIMENSIONS:
            if dims is None:
                dims = set()
            if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
                dims |= self.strctMdlParentNode.aspectValue(aspect, dims=dims, depth=depth + 1)
            if inherit and isinstance(self.strctMdlParentNode, StrctMdlBreakdown) and isinstance(self.strctMdlParentNode.strctMdlParentNode, StrctMdlStructuralNode):
                dims |= self.strctMdlParentNode.strctMdlParentNode.aspectValue(aspect, dims=dims, depth=depth + 1)
            if aspect in aspects:
                dims |= aspects[aspect]
            elif constraintSet is not None and constraintSet.hasAspect(self, aspect):
                dims |= set(defnMdlNode.aspectValue(xc, aspect) or {})  # type: ignore[union-attr]
            if constraintSet is not None and constraintSet.hasAspect(self, Aspect.OMIT_DIMENSIONS):
                dims -= set(constraintSet.aspectValue(xc, Aspect.OMIT_DIMENSIONS))
            return dims
        if aspect in aspects:
            return aspects[aspect]
        elif constraintSet is not None and constraintSet.hasAspect(self, aspect):
            if isinstance(defnMdlNode, DefnMdlAspectNode):
                if contextItemBinding:
                    return self.dimRAV(aspect, contextItemBinding.aspectValue(aspect))  # type: ignore[no-untyped-call]
            else:
                return self.dimRAV(aspect, constraintSet.aspectValue(xc, aspect))
        if inherit and isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.aspectValue(aspect, depth=depth + 1)
        elif inherit and isinstance(self.strctMdlParentNode, StrctMdlBreakdown) and isinstance(self.strctMdlParentNode.strctMdlParentNode, StrctMdlStructuralNode):
            return self.strctMdlParentNode.strctMdlParentNode.aspectValue(aspect, depth=depth + 1)
        return None

    '''
    @property
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        if Aspect.CONCEPT in self.aspects:
            return self.aspects[Aspect.CONCEPT]
        return self.defnMdlNode.primaryItemQname
    @property
    def explicitDims(self):
        return self.defnMdlNode.explicitDims
    '''

    @property
    def tableDefinitionNode(self) -> Any:
        if self.strctMdlParentNode is None:
            return self.tableNode
        else:
            return self.strctMdlParentNode.tableDefinitionNode  # type: ignore[attr-defined]

    @property
    def leafNodeCount(self) -> int:
        childLeafCount = 0
        if self.strctMdlChildNodes:
            for childStructuralNode in self.strctMdlChildNodes:
                childLeafCount += childStructuralNode.leafNodeCount
        if childLeafCount == 0:
            return 1
        return childLeafCount

    def setHasOpenNode(self) -> None:
        if isinstance(self.strctMdlParentNode, StrctMdlStructuralNode):
            self.strctMdlParentNode.setHasOpenNode()
        else:
            self.hasOpenNode = True

    def inheritedAspectValue(
        self,
        otherAxisStructuralNode: StrctMdlNode | None,
        view: Any,
        aspect: int,
        tagSelectors: set[str | None] | None,
        xAspectStructuralNodes: dict[int, set[Any]],
        yAspectStructuralNodes: dict[int, set[Any]],
        zAspectStructuralNodes: dict[int, set[Any]],
    ) -> Any:
        aspectStructuralNodes = xAspectStructuralNodes.get(aspect, EMPTY_SET) | yAspectStructuralNodes.get(aspect, EMPTY_SET) | zAspectStructuralNodes.get(aspect, EMPTY_SET)
        structuralNode: StrctMdlStructuralNode | None = None
        if len(aspectStructuralNodes) == 1:
            structuralNode = aspectStructuralNodes.pop()
        elif len(aspectStructuralNodes) > 1:
            strctNodesWithAspect = set(_aspectStructuralNode
                                       for _aspectStructuralNode in aspectStructuralNodes
                                       if not _aspectStructuralNode.rollup
                                       if _aspectStructuralNode.defnMdlNode.hasAspect(self, aspect))
            if len(strctNodesWithAspect) == 1:
                structuralNode = strctNodesWithAspect.pop()
            else:
                # check if all nodes have same value
                if aspect == Aspect.LOCATION:
                    hasClash = False
                    for _aspectStructuralNode in aspectStructuralNodes:
                        if not _aspectStructuralNode.defnMdlNode.aspectValueDependsOnVars(aspect):
                            if structuralNode:
                                hasClash = True
                            else:
                                structuralNode = _aspectStructuralNode
                else:
                    # take closest structural node
                    hasClash = True
            ''' reported in static analysis by RenderingEvaluator.py
            if hasClash:
                from arelle.ModelFormulaObject import aspectStr
                view.modelXbrl.error("xbrlte:aspectClashBetweenBreakdowns",
                    _("Aspect %(aspect)s covered by multiple axes."),
                    modelObject=view.modelTable, aspect=aspectStr(aspect))
            '''
        if structuralNode:
            definitionNodeConstraintSet = structuralNode.constraintSet(tagSelectors)
            if definitionNodeConstraintSet is not None and definitionNodeConstraintSet.aspectValueDependsOnVars(aspect):
                return self.evaluate(definitionNodeConstraintSet,
                                     definitionNodeConstraintSet.aspectValue,  # this passes a method
                                     otherAxisStructuralNode=otherAxisStructuralNode,
                                     evalArgs=(aspect,))
            return structuralNode.aspectValue(aspect, tagSelectors=tagSelectors)
        return None


# Root class for rendering is formula, to allow linked and nested compiled expressions
def defnMdlLabelsView(mdlObj: ModelObject) -> tuple[tuple[str, str], ...]:
    return tuple(sorted([("{} {} {} {}".format(label.localName,  # type: ignore[union-attr]
                                            str(rel.order).rstrip("0").rstrip("."),
                                            os.path.basename(label.role or ""),  # type: ignore[union-attr]
                                            label.xmlLang),  # type: ignore[union-attr]
                          label.stringValue)  # type: ignore[union-attr]
                         for rel in mdlObj.modelXbrl.relationshipSet((XbrlConst.elementLabel, XbrlConst.elementReference)).fromModelObject(mdlObj)  # type: ignore[union-attr]
                         for label in (rel.toModelObject,)] +
                        [("xlink:label", mdlObj.xlinkLabel)]))


# REC Table linkbase
class DefnMdlTable(ModelFormulaResource):
    _rendrCntx: XPathContext | None
    _filterRelationships: list[ModelRelationship]

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlTable, self).init(modelDocument)
        self.modelXbrl.modelRenderingTables.add(self)  # type: ignore[union-attr]
        self.modelXbrl.hasRenderingTables = True  # type: ignore[union-attr]
        self.aspectsInTaggedConstraintSets: set[int] = set()

    def clear(self) -> None:  # type: ignore[override]
        if getattr(self, "_rendrCntx", None):
            self._rendrCntx.close()  # type: ignore[union-attr]
        super(DefnMdlTable, self).clear()  # delete children

    @property
    def isMerged(self) -> bool:
        return False

    @property
    def parentTableNode(self) -> Self:
        return self

    @property
    def parentChildOrder(self) -> str | None:
        return parentChildOrder(self)

    @property
    def descendantArcroles(self) -> tuple[str, ...]:  # type: ignore[override]
        return (XbrlConst.tableFilter, XbrlConst.tableFilterMMDD,
                XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD,
                XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)

    @property
    def ancestorArcroles(self) -> tuple[()]:
        return ()

    @property
    def aspectModel(self) -> str:
        return "dimensional"  # attribute removed 2013-06, always dimensional

    @property
    def filterRelationships(self) -> list[ModelRelationship]:
        try:
            return self._filterRelationships
        except AttributeError:
            rels: list[ModelRelationship] = []  # order so conceptName filter is first (if any) (may want more sorting in future)
            for rel in self.modelXbrl.relationshipSet((XbrlConst.tableFilter, XbrlConst.tableFilterMMDD)).fromModelObject(self):  # type: ignore[union-attr]
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            self._filterRelationships = rels
            return rels
    ''' now only accessed from structural node
    def header(self, role=None, lang=None, strip=False, evaluate=True):
        return self.genLabel(role=role, lang=lang, strip=strip)
    '''

    @property
    def definitionLabelsView(self) -> tuple[tuple[str, str], ...]:
        return defnMdlLabelsView(self)

    def filteredFacts(self, xpCtx: XPathContext, facts: Iterable[ModelFact]) -> Any:
        return formulaEvaluatorFilterFacts(xpCtx, VariableBinding(xpCtx),  # type: ignore[no-untyped-call]
                                           facts, self.filterRelationships, None)

    @property
    def renderingXPathContext(self) -> XPathContext | None:
        try:
            return self._rendrCntx
        except AttributeError:
            xpCtx = getattr(self.modelXbrl, "rendrCntx", None)
            if xpCtx is not None:
                self._rendrCntx = xpCtx.copy()
                for tblParamRel in self.modelXbrl.relationshipSet((XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)).fromModelObject(self):  # type: ignore[union-attr]
                    varQname = tblParamRel.variableQname
                    parameter = tblParamRel.toModelObject
                    if isinstance(parameter, ModelParameter):
                        self._rendrCntx.inScopeVars[varQname] = xpCtx.inScopeVars.get(parameter.parameterQname)  # type: ignore[index]
            else:
                self._rendrCntx = None
            return self._rendrCntx

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return ((("id", self.id), ("xlink:label", self.xlinkLabel)) +
                self.definitionLabelsView)

    def __repr__(self) -> str:
        return "DefnMdlTable[{0}]{1})".format(self.objectId(), self.propertyView)

    @property
    def definitionNodeView(self) -> str:
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)


class DefnMdlBreakdown(ModelFormulaResource):
    strctMdlRollupType = ROLLUP_FOR_DEFINITION_NODE

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlBreakdown, self).init(modelDocument)

    @property
    def isMerged(self) -> bool:
        return False

    def hasAspect(self, *args: Any) -> bool:
        return False

    @property
    def parentTableNode(self) -> DefnMdlTable | None:
        for rel in self.modelXbrl.relationshipSet("Table-rendering").toModelObject(self):  # type: ignore[union-attr]
            if rel.fromModelObject is not None:
                p = rel.fromModelObject.parentTableNode  # type: ignore[union-attr]
                if p is not None:
                    return p  # type: ignore[no-any-return]
        return None

    @property
    def parentChildOrder(self) -> str | None:
        return parentChildOrder(self)

    @property
    def descendantArcroles(self) -> tuple[str, str]:  # type: ignore[override]
        return XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD

    @property
    def ancestorArcroles(self) -> tuple[str, str]:
        return XbrlConst.tableModel, XbrlConst.tableModelMMDD

    @property
    def childrenCoverSameAspects(self) -> bool:
        return False

    def aspectsCovered(self) -> set[Any]:
        return EMPTY_SET

    @property
    def constraintSets(self) -> dict[Any, Any]:
        return EMPTY_DICT

    @property
    def isAbstract(self) -> bool:  # type: ignore[override]
        return False

    def cardinalityAndDepth(self, structuralNode: StrctMdlNode, **kwargs: Any) -> tuple[int, int]:
        return 1, 1 if structuralNode.header(evaluate=False) is not None else 0

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("parent child order", self.get("parentChildOrder"))) +
                 defnMdlLabelsView(self))

    def __repr__(self) -> str:
        return "DefnMdlBreakdown[{0}]{1})".format(self.objectId(), self.propertyView)

    @property
    def definitionNodeView(self) -> str:
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)

    @property
    def definitionLabelsView(self) -> tuple[tuple[str, str], ...]:
        return defnMdlLabelsView(self)


class DefnMdlDefinitionNode(ModelFormulaResource):
    aspectModel = "dimensional"

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlDefinitionNode, self).init(modelDocument)

    @property
    def isMerged(self) -> bool:
        return False

    @property
    def parentTableNode(self) -> DefnMdlTable | None:
        for rel in self.modelXbrl.relationshipSet("Table-rendering").toModelObject(self):  # type: ignore[union-attr]
            if rel.fromModelObject is not None:
                p = rel.fromModelObject.parentTableNode  # type: ignore[union-attr]
                if p is not None:
                    return p  # type: ignore[no-any-return]
        return None

    @property
    def descendantArcroles(self) -> tuple[str, str]:  # type: ignore[override]
        return XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int) -> bool:
        return False

    def aspectValueDependsOnVars(self, aspect: Any) -> bool:
        return False

    @property
    def variablename(self) -> str | None:
        """(str) -- name attribute"""
        return self.getStripped("name")

    @property
    def variableQname(self) -> QName | None:
        """(QName) -- resolved name for an XPath bound result having a QName name attribute"""
        varName = self.variablename
        return qname(self, varName, noPrefixIsNoNamespace=True) if varName else None

    def aspectValue(self, xpCtx: XPathContext, aspect: int, inherit: bool = True) -> list[Any] | None:
        if aspect == Aspect.DIMENSIONS:
            return []
        return None

    def aspectsCovered(self) -> set[Any]:
        return EMPTY_SET

    @property
    def constraintSets(self) -> dict[None, Self]:
        return {None: self}

    @property
    def tagSelector(self) -> str | None:
        return self.get("tagSelector")

    @property
    def valueExpression(self) -> str | None:
        return self.get("value")

    @property
    def hasValueExpression(self) -> bool:
        return bool(self.valueProg)  # non empty program

    def compile(self) -> None:
        if not hasattr(self, "valueProg"):
            value = self.valueExpression
            self.valueProg = parse(self, value, self, "value", Trace.VARIABLE)
        # duplicates formula resource for RuleAxis but not for other subclasses
        super(DefnMdlDefinitionNode, self).compile()

    def evalValueExpression(self, xpCtx: XPathContext, fact: ContextItem) -> Any:
        # compiled by FormulaResource compile()
        return xpCtx.evaluateAtomicValue(self.valueProg, "xs:string", fact)  # type: ignore[arg-type]

    '''
    @property
    def primaryItemQname(self):  # for compatibility with viewRelationsihps
        return None
    @property
    def explicitDims(self):
        return set()
    '''

    @property
    def isAbstract(self) -> bool:  # type: ignore[override]
        return False

    def cardinalityAndDepth(self, structuralNode: StrctMdlNode, **kwargs: Any) -> tuple[int, int]:
        return 1, 1 if structuralNode.header(evaluate=False) is not None else 0
    ''' now only accessed from structural node (mulst have table context for evaluate)
    def header(self, role=None, lang=None, strip=False, evaluate=True):
        if role is None:
            # check for message before checking for genLabel
            msgsRelationshipSet = self.modelXbrl.relationshipSet((XbrlConst.tableDefinitionNodeMessage201301, XbrlConst.tableAxisMessage2011))
            if msgsRelationshipSet:
                msg = msgsRelationshipSet.label(self, XbrlConst.standardMessage, lang, returnText=False)
                if msg is not None:
                    if evaluate:
                        result = msg.evaluate(self.modelXbrl.rendrCntx)
                    else:
                        result = XmlUtil.text(msg)
                    if strip:
                        return result.strip()
                    return result
        return self.genLabel(role=role, lang=lang, strip=strip)
    '''

    @property
    def definitionNodeView(self) -> str:
        return XmlUtil.xmlstring(self, stripXmlns=True, prettyPrint=True)

    @property
    def definitionLabelsView(self) -> tuple[tuple[str, str], ...]:
        return defnMdlLabelsView(self)

    @property
    def parentChildOrder(self) -> str | None:
        return None


class DefnMdlClosedDefinitionNode(DefnMdlDefinitionNode):
    strctMdlRollupType = ROLLUP_FOR_CLOSED_DEFINITION_NODE

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlClosedDefinitionNode, self).init(modelDocument)

    @property
    def abstract(self) -> str | None:
        return self.get("abstract")

    @property
    def isAbstract(self) -> bool:  # type: ignore[override]
        return self.abstract == "true"

    @property
    def parentChildOrder(self) -> str | None:
        return parentChildOrder(self)

    @property
    def descendantArcroles(self) -> tuple[str, str]:  # type: ignore[override]
        return XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD

    @property
    def ancestorArcroles(self) -> tuple[str, str, str, str]:
        return (
            XbrlConst.tableBreakdownTree,
            XbrlConst.tableBreakdownTreeMMDD,
            XbrlConst.tableDefinitionNodeSubtree,
            XbrlConst.tableDefinitionNodeSubtreeMMDD,
        )

    def filteredFacts(self, xpCtx: XPathContext, facts: Iterable[ModelFact]) -> set[ModelFact]:
        aspects = self.aspectsCovered()
        axisAspectValues = dict((aspect, self.aspectValue(xpCtx, aspect))
                                for aspect in aspects)
        fp = FactPrototype(self, axisAspectValues)
        return set(fact
                   for fact in facts
                   if aspectsMatch(xpCtx, fact, fp, aspects))  # type: ignore[no-untyped-call]

    @property
    def childrenCoverSameAspects(self) -> bool:
        # indicates this definition node has children with same aspect
        descendantRels = self.modelXbrl.relationshipSet(self.descendantArcroles).fromModelObject(self)  # type: ignore[union-attr]
        if descendantRels:
            selfAspectsCovered = self.aspectsCovered()
            if selfAspectsCovered:  # is roll up if self and descendants cover same aspects
                return all(selfAspectsCovered == rel.toModelObject.aspectsCovered()  # type: ignore[union-attr]
                           for rel in descendantRels
                           if not isinstance(rel.toModelObject, (NoneType, DefnMdlTable)))
            aDescendantAspectsCovered = None
            for rel in descendantRels:  # no self aspects, find any descendant's aspects
                if rel.toModelObject is not None:
                    aDescendantAspectsCovered = rel.toModelObject.aspectsCovered()  # type: ignore[union-attr]
                    break
            if aDescendantAspectsCovered:  # all descendants must contribute same aspects to be a roll up
                return all(aDescendantAspectsCovered == rel.toModelObject.aspectsCovered()  # type: ignore[union-attr]
                           for rel in descendantRels
                           if rel.toModelObject is not None)
        return False


class DefnMdlConstraintSet(ModelFormulaRules):
    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlConstraintSet, self).init(modelDocument)
        self.aspectValues: dict[int, list[QName] | QName | ModelObject | str | None] = {}  # type: ignore[assignment] # only needed if error blocks compiling this node, replaced by compile()
        self.aspectProgs: dict[int, list[ExpressionStack | None]] = {}  # type: ignore[assignment] # ditto

    def isMerged(self) -> bool:
        return False

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int, inherit: bool = False) -> bool:
        return self._hasAspect(structuralNode, aspect, inherit)

    def _hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int, inherit: bool = False) -> bool:  # opaque from ModelRuleDefinitionNode
        if aspect in aspectRuleAspects:
            return any(self.hasRule(a) for a in aspectRuleAspects[aspect])
        return self.hasRule(aspect)

    def aspectValue(self, xpCtx: XPathContext | None, aspect: int, inherit: bool = False) -> Any:
        try:
            return self.evaluateRule(xpCtx, aspect)
        except AttributeError:
            return "(unavailable)"  # table defective or not initialized

    def aspectValueDependsOnVars(self, aspect: int) -> bool:
        return aspect in self.aspectProgs.keys()

    def aspectsCovered(self) -> set[int]:
        return self.aspectValues.keys() | self.aspectProgs.keys()

    def aspectsModelCovered(self) -> set[int]:
        return set(aspectModelAspect.get(aspect, aspect) for aspect in self.aspectsCovered())

    '''
    @property
    def primaryItemQname(self):
        return self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.CONCEPT)
    @property
    def explicitDims(self):
        dimMemSet = set()
        dims = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.DIMENSIONS)
        if dims: # may be none if no dim aspects on this ruleAxis
            for dim in dims:
                mem = self.evaluateRule(self.modelXbrl.rendrCntx, dim)
                if mem: # may be none if dimension was omitted
                    dimMemSet.add( (dim, mem) )
        return dimMemSet
    @property
    def instant(self):
        periodType = self.evaluateRule(self.modelXbrl.rendrCntx, Aspect.PERIOD_TYPE)
        if periodType == "forever":
            return None
        return self.evaluateRule(self.modelXbrl.rendrCntx,
                                 {"instant": Aspect.INSTANT,
                                  "duration": Aspect.END}[periodType])
    '''

    def cardinalityAndDepth(self, structuralNode: StrctMdlNode, **kwargs: Any) -> tuple[int, int]:
        if self.aspectValues or self.aspectProgs or structuralNode.header(role="*", evaluate=False) is not None:
            return 1, 1
        else:
            return 0, 0


class DefnMdlRuleSet(DefnMdlConstraintSet, ModelFormulaResource):  # type: ignore[misc]
    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlRuleSet, self).init(modelDocument)

    @property
    def tagName(self) -> str | None:  # can't call it tag because that would hide ElementBase.tag
        return self.get("tag")


class DefnMdlRuleDefinitionNode(DefnMdlConstraintSet, DefnMdlClosedDefinitionNode):  # type: ignore[misc]
    _constraintSets: dict[str | None, ModelObject | Self]
    _aspectsInTaggedConstraintSet: set[int]

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlRuleDefinitionNode, self).init(modelDocument)

    @property
    def merge(self) -> str | None:
        return self.get("merge")

    @property
    def isMerged(self) -> bool:  # type: ignore[override]
        return self.merge in ("true", "1")

    @property
    def constraintSets(self) -> dict[str | None, ModelObject | Self]:  # type: ignore[override]
        try:
            return self._constraintSets
        except AttributeError:
            self._constraintSets = dict((ruleSet.tagName, ruleSet)  # type: ignore[attr-defined]
                                        for ruleSet in XmlUtil.children(self, self.namespaceURI, "ruleSet"))
            if self.aspectsCovered():  # any local rule?
                self._constraintSets[None] = self
            return self._constraintSets

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int, inherit: bool = False) -> bool:
        return any(constraintSet._hasAspect(structuralNode, aspect)  # type: ignore[union-attr]
                   for constraintSet in self.constraintSets.values())

    @property
    def aspectsInTaggedConstraintSet(self) -> set[int]:
        try:
            return self._aspectsInTaggedConstraintSet
        except AttributeError:
            self._aspectsInTaggedConstraintSet = set()
            for tag, constraintSet in self.constraitSets().items():  # type: ignore[attr-defined]
                if tag is not None:
                    for aspect in constraintSet.aspectsCovered():
                        if aspect != Aspect.DIMENSIONS:
                            self._aspectsInTaggedConstraintSet.add(aspect)
            return self._aspectsInTaggedConstraintSet

    def compile(self) -> None:
        super(DefnMdlRuleDefinitionNode, self).compile()
        for constraintSet in self.constraintSets.values():
            if constraintSet != self:  # compile nested constraint sets
                constraintSet.compile()  # type: ignore[union-attr]

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("abstract", self.abstract),
                 ("merge", self.merge),
                 ("definition", self.definitionNodeView)) +
                 self.definitionLabelsView)

    def __repr__(self) -> str:
        return "DefnMdlRuleDefinitionNode[{0}]{1})".format(self.objectId(), self.propertyView)


class DefnMdlRelationshipNode(DefnMdlClosedDefinitionNode):
    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlRelationshipNode, self).init(modelDocument)
        self.relationshipSourceQnamesAndQnameExpressionProgs: list[Any] = []

    def aspectsCovered(self) -> set[int]:
        return {Aspect.CONCEPT}

    @property
    def conceptQname(self) -> QName | None:
        name = self.getStripped("conceptname")
        return qname(self, name, noPrefixIsNoNamespace=True) if name else None

    @property
    def linkrole(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkrole")

    @property
    def formulaAxis(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "formulaAxis")

    @property
    def generations(self) -> int:
        try:
            return int(XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "generations"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            if self.formulaAxis in ("sibling", "sibling-or-self", "child", "parent"):
                return 1
            return 0

    @property
    def relationshipSourceQnamesAndExpressions(self) -> list[str | QName | None]:
        return [qname(e, XmlUtil.text(e)) if e.qname.localName == "relationshipSource" else XmlUtil.text(e)
                for e in XmlUtil.children(self, (XbrlConst.table, XbrlConst.tableMMDD), ("relationshipSource", "relationshipSourceExpression"))]

    @property
    def linkroleExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkroleExpression")

    @property
    def formulaAxisExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "formulaAxisExpression")

    @property
    def generationsExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "generationsExpression")

    def compile(self) -> None:
        if not hasattr(self, "linkroleExpressionProg"):
            self.relationshipSourceQnamesAndQnameExpressionProgs = [
                qe if isinstance(qe, QName) else parse(self, qe, self, "relationshipSourceQnamesExpressionProg", Trace.VARIABLE)
                for qe in self.relationshipSourceQnamesAndExpressions]
            self.linkroleExpressionProg = parse(self, self.linkroleExpression, self, "linkroleQnameExpressionProg", Trace.VARIABLE)
            self.formulaAxisExpressionProg = parse(self, self.formulaAxisExpression, self, "formulaAxisExpressionProg", Trace.VARIABLE)
            self.generationsExpressionProg = parse(self, self.generationsExpression, self, "generationsExpressionProg", Trace.VARIABLE)
            super(DefnMdlRelationshipNode, self).compile()

    def variableRefs(self, progs: RecursiveFormulaTokens = [], varRefSet: set[QName] | None = None) -> set[QName]:  # type: ignore[override]
        if (self.relationshipSourceQnamesAndQnameExpressionProgs
                and self.relationshipSourceQnamesAndQnameExpressionProgs != [XbrlConst.qnXfiRoot]):
            if varRefSet is None:
                varRefSet = set()
        varRefs = super(DefnMdlRelationshipNode, self).variableRefs(
                                        [p
                                         for p in self.relationshipSourceQnamesAndQnameExpressionProgs + [
                                                        self.linkroleExpressionProg, self.formulaAxisExpressionProg,
                                                        self.generationsExpressionProg]
                                        if p], varRefSet)
        return varRefs

    def evalRrelationshipSourceQnames(self, xpCtx: XPathContext, fact: ContextItem = None) -> list[Any]:
        return [qp if isinstance(qp, QName) else xpCtx.evaluateAtomicValue(qp, "xs:QName", fact)
                for qp in self.relationshipSourceQnamesAndQnameExpressionProgs]

    def evalLinkrole(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.linkrole:
            return self.linkrole
        return xpCtx.evaluateAtomicValue(self.linkroleExpressionProg, "xs:anyURI", fact)  # type: ignore[arg-type]

    def evalFormulaAxis(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.formulaAxis:
            return self.formulaAxis
        return xpCtx.evaluateAtomicValue(self.formulaAxisExpressionProg, "xs:token", fact)  # type: ignore[arg-type]

    def evalGenerations(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.generations:
            return self.generations
        return xpCtx.evaluateAtomicValue(self.generationsExpressionProg, "xs:integer", fact)  # type: ignore[arg-type]

    def cardinalityAndDepth(self, structuralNode: StrctMdlNode, **kwargs: Any) -> tuple[int, int]:
        return self.lenDepth(self.relationships(structuralNode, **kwargs), self.isOrSelfAxis)  # type: ignore[attr-defined]

    def lenDepth(self, nestedRelationships: Iterable[Any], includeSelf: bool) -> tuple[int, int]:
        l = 0
        d = 1
        for rel in nestedRelationships:
            if isinstance(rel, list):
                nl, nd = self.lenDepth(rel, False)
                l += nl
                nd += 1  # returns 0 if sublist is not nested
                if nd > d:
                    d = nd
            else:
                l += 1
                if includeSelf:
                    l += 1  # root relationships include root in addition
        if includeSelf:
            l += 1
            d += 1
        return l, d

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("abstract", self.abstract),
                 ("definition", self.definitionNodeView)) +
                self.definitionLabelsView)

    def __repr__(self) -> str:
        return "defnMdlRelationshipNode[{0}]{1})".format(self.objectId(), self.propertyView)


class DefnMdlConceptRelationshipNode(DefnMdlRelationshipNode):
    strctMdlRollupType = ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlConceptRelationshipNode, self).init(modelDocument)

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int) -> bool:
        return aspect == Aspect.CONCEPT

    @property
    def arcrole(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcrole")

    @property
    def arcQname(self) -> QName | None:
        arcnameElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcname")
        if arcnameElt is not None:
            return qname(arcnameElt, XmlUtil.text(arcnameElt))
        return None

    @property
    def linkQname(self) -> QName | None:
        linknameElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "linkname")
        if linknameElt is not None:
            return qname(linknameElt, XmlUtil.text(linknameElt))
        return None

    def compile(self) -> None:
        if not hasattr(self, "arcroleExpressionProg"):
            self.arcroleExpressionProg = parse(self, self.arcroleExpression, self, "arcroleExpressionProg", Trace.VARIABLE)
            self.linkQnameExpressionProg = parse(self, self.linkQnameExpression, self, "linkQnameExpressionProg", Trace.VARIABLE)
            self.arcQnameExpressionProg = parse(self, self.arcQnameExpression, self, "arcQnameExpressionProg", Trace.VARIABLE)
            super(DefnMdlConceptRelationshipNode, self).compile()

    def variableRefs(self, progs: RecursiveFormulaTokens = [], varRefSet: set[QName] | None = None) -> set[QName]:  # type: ignore[override]
        return super(DefnMdlConceptRelationshipNode, self).variableRefs(
                                                [p for p in (self.arcroleExpressionProg,
                                                             self.linkQnameExpressionProg, self.arcQnameExpressionProg)
                                                 if p], varRefSet)

    def evalArcrole(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.arcrole:
            return self.arcrole
        return xpCtx.evaluateAtomicValue(self.arcroleExpressionProg, "xs:anyURI", fact)  # type: ignore[arg-type]

    def evalLinkQname(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.linkQname:
            return self.linkQname
        return xpCtx.evaluateAtomicValue(self.linkQnameExpressionProg, "xs:QName", fact)  # type: ignore[arg-type]

    def evalArcQname(self, xpCtx: XPathContext, fact: ContextItem = None) -> Any:
        if self.arcQname:
            return self.arcQname
        return xpCtx.evaluateAtomicValue(self.arcQnameExpressionProg, "xs:QName", fact)  # type: ignore[arg-type]

    @property
    def arcroleExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcroleExpression")

    @property
    def linkQnameExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "linknameExpression")

    @property
    def arcQnameExpression(self) -> str | None:
        return XmlUtil.childText(self, (XbrlConst.table, XbrlConst.tableMMDD), "arcnameExpression")

    @property
    def isOrSelfAxis(self) -> bool:
        return self._formulaAxis.endswith("-or-self") and self._formulaAxis not in ("sibling-or-self", "sibling-or-descendant-or-self")

    def coveredAspect(self, ordCntx: XPathContext | None = None) -> int:
        return Aspect.CONCEPT

    def relationships(self, structuralNode: StrctMdlNode, **kwargs: Any) -> list[Any]:
        self._sourceQnames = structuralNode.evaluate(self, self.evalRrelationshipSourceQnames, **kwargs) or [XbrlConst.qnXfiRoot]
        linkrole = structuralNode.evaluate(self, self.evalLinkrole, handleXPathException=False)  # expect cast exception on bad anyURI
        if not linkrole:
            linkrole = XbrlConst.defaultLinkRole
        linkQname = structuralNode.evaluate(self, self.evalLinkQname, handleXPathException=False) or ()
        arcrole = structuralNode.evaluate(self, self.evalArcrole, handleXPathException=False) or ()
        arcQname = structuralNode.evaluate(self, self.evalArcQname, handleXPathException=False) or ()
        self._formulaAxis = structuralNode.evaluate(self, self.evalFormulaAxis, handleXPathException=False) or "descendant-or-self"
        rels_axis = self._formulaAxis
        if rels_axis not in ("sibling-or-self", "sibling-or-descendant-or-self"):
            rels_axis = rels_axis.replace("-or-self", "")
        self._generations = structuralNode.evaluate(self, self.evalGenerations, handleXPathException=False) or ()
        if self._generations == () and self._formulaAxis in ("child", "child-or-self", "parent", "parent-or-self", "sibling", "sibling-or-self"):
            self._generations = 1
        rels: list[Any] = []
        for srcQname in self._sourceQnames:
            rels.extend(concept_relationships(self.modelXbrl.rendrCntx,  # type: ignore[union-attr]
                                      None,  # type: ignore[arg-type]
                                      (srcQname,  # type: ignore[arg-type]
                                       linkrole,
                                       arcrole,
                                       rels_axis,
                                       self._generations,
                                       linkQname,
                                       arcQname),
                                       True))  # return nested lists representing concept tree nesting
        return rels


class DefnMdlDimensionRelationshipNode(DefnMdlRelationshipNode):
    strctMdlRollupType = ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE
    _coveredAspect: Any

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlDimensionRelationshipNode, self).init(modelDocument)
        self.tlbDimRelsUseHcRoleForDomainRoots = False  # legacy feature for Dutch taxonomies before 2025, set by formula parameter tlbDimRelsUseHcRoleForDomainRoots

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int) -> bool:
        return aspect == self.coveredAspect(structuralNode) or aspect == Aspect.DIMENSIONS

    def aspectValue(self, xpCtx: XPathContext, aspect: int, inherit: bool = False) -> Any:
        if aspect == Aspect.DIMENSIONS:
            return (self.coveredAspect(xpCtx),)  # type: ignore[arg-type]
        return None

    def aspectsCovered(self) -> set[QName | None]:  # type: ignore[override]
        return {self.dimensionQname}

    @property
    def dimensionQname(self) -> QName | None:
        dimensionElt = XmlUtil.child(self, (XbrlConst.table, XbrlConst.tableMMDD), "dimension")
        if dimensionElt is not None:
            return qname(dimensionElt, XmlUtil.text(dimensionElt))
        return None

    def compile(self) -> None:
        super(DefnMdlDimensionRelationshipNode, self).compile()

    def variableRefs(self, progs: RecursiveFormulaTokens = [], varRefSet: set[QName] | None = None) -> set[QName]:  # type: ignore[override]
        return super(DefnMdlDimensionRelationshipNode, self).variableRefs(self.relationshipSourceQnamesAndQnameExpressionProgs, varRefSet)

    def evalDimensionQname(self, xpCtx: Any, fact: Any = None) -> QName | None:
        return self.dimensionQname

    @property
    def isOrSelfAxis(self) -> bool:
        return False  # always return relationships into nodes for domain members

    def coveredAspect(self, structuralNode: StrctMdlStructuralNode | None = None) -> Any:
        try:
            return self._coveredAspect
        except AttributeError:
            self._coveredAspect = self.dimRelationships(structuralNode, getDimQname=True)  # type: ignore[arg-type]
            return self._coveredAspect

    def relationships(self, structuralNode: StrctMdlStructuralNode, **kwargs: Any) -> Any:
        return self.dimRelationships(structuralNode, getMembers=True)

    def dimRelationships(self, structuralNode: StrctMdlStructuralNode, getMembers: bool = False, getDimQname: bool = False) -> Any:
        self._dimensionQname: QName = structuralNode.evaluate(self, self.evalDimensionQname)
        self._sourceQnames: list[QName] = structuralNode.evaluate(self, self.evalRrelationshipSourceQnames, handleXPathException=False) or []
        linkrole = structuralNode.evaluate(self, self.evalLinkrole, handleXPathException=False)  # expect cast exception on bad anyURI
        if not linkrole and getMembers:
            linkrole = XbrlConst.defaultLinkRole
        dimConcept = self.modelXbrl.qnameConcepts.get(self._dimensionQname)  # type: ignore[union-attr]
        sourceConcepts = [self.modelXbrl.qnameConcepts.get(qn) for qn in self._sourceQnames]  # type: ignore[union-attr]
        self._formulaAxis = (structuralNode.evaluate(self, self.evalFormulaAxis, handleXPathException=False) or "descendant-or-self")
        if self._formulaAxis not in ("descendant", "descendant-or-self", "child", "child-or-self"):
            raise ResolutionException("xbrlte:expressionNotCastableToRequiredType", _("Dimension relationship contains an invalid axis specification"))
        isOrSelf = self._formulaAxis.endswith("-or-self")
        self._generations = (structuralNode.evaluate(self, self.evalGenerations, handleXPathException=False) or ())
        if self._generations == () and self._formulaAxis in ("child", "child-or-self"):
            self._generations = 1
        if ((self._dimensionQname and (dimConcept is None or not dimConcept.isDimensionItem)) or
            (self._sourceQnames and (
                    any(c is None or not c.isItem for c in sourceConcepts)))):
            return ()
        if getDimQname:
            return self._dimensionQname
        if getMembers:
            rels: list[ModelRelationship] = []

            def srcQnDims(srcRel: ModelRelationship, srcQn: QName) -> None:
                if not srcQn or srcRel.toModelObject.qname == srcQn:  # type: ignore[union-attr]
                    _rels = concept_relationships(self.modelXbrl.rendrCntx,  # type: ignore[union-attr]
                                          None,  # type: ignore[arg-type]
                                          (srcRel.toModelObject.qname,  # type: ignore[arg-type, union-attr]
                                           srcRel.consecutiveLinkrole,
                                           XbrlConst.domainMember,
                                           self._formulaAxis.replace("-or-self", ""),
                                           self._generations),
                                          True,
                                          targetRole=True)
                    if isOrSelf:
                        rels.append(srcRel)
                        if _rels:
                            rels.append(_rels)
                    elif _rels:
                        rels.extend(_rels)  # return nested lists representing concept tree nesting)
                    return  # found the starting source QName
                for rel in self.modelXbrl.relationshipSet(XbrlConst.domainMember, srcRel.consecutiveLinkrole).fromModelObject(srcRel.toModelObject):  # type: ignore[union-attr, arg-type]
                    srcQnDims(rel, srcQn)
            if self.tlbDimRelsUseHcRoleForDomainRoots:
                # legacy mode uses Hc Linkrole for roots instead of Dim linkrole (Dutch taxonomies before 2025)
                sourceDimRels = self.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, linkrole).toModelObject(dimConcept)  # type: ignore[union-attr, arg-type]
                for srcQn in self._sourceQnames or (None,):
                    for rel in sourceDimRels:
                        for dimDomRel in self.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, rel.consecutiveLinkrole).fromModelObject(rel.toModelObject):  # type: ignore[union-attr, arg-type]
                            srcQnDims(dimDomRel, srcQn)  # type: ignore[arg-type]
            else:
                dimRels = self.modelXbrl.relationshipSet(XbrlConst.dimensionDomain, linkrole).fromModelObject(dimConcept)  # type: ignore[union-attr, arg-type]
                for srcQn in self._sourceQnames or (None,):
                    for dimDomRel in dimRels:
                        srcQnDims(dimDomRel, srcQn)  # type: ignore[arg-type]
            return rels
        return None


coveredAspectToken = {"concept": Aspect.CONCEPT,
                      "entity-identifier": Aspect.VALUE,
                      "period-start": Aspect.START, "period-end": Aspect.END,
                      "period-instant": Aspect.INSTANT, "period-instant-end": Aspect.INSTANT_END,
                      "unit": Aspect.UNIT}


class DefnMdlOpenDefinitionNode(DefnMdlDefinitionNode):
    strctMdlRollupType = ROLLUP_FOR_OPEN_DEFINITION_NODE

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlOpenDefinitionNode, self).init(modelDocument)

    @property
    def childrenCoverSameAspects(self) -> bool:
        return False


aspectNodeAspectCovered = {"conceptAspect": Aspect.CONCEPT,
                           "unitAspect": Aspect.UNIT,
                           "entityIdentifierAspect": Aspect.ENTITY_IDENTIFIER,
                           "periodAspect": Aspect.PERIOD}


class DefnMdlAspectNode(DefnMdlOpenDefinitionNode):
    _filterRelationships: list[ModelRelationship | ModelConceptName]
    _aspectsCovered: set[int | QName]
    _dimensionsCovered: set[QName]
    includeUnreportedValue: bool

    def init(self, modelDocument: ModelDocument) -> None:
        super(DefnMdlAspectNode, self).init(modelDocument)

    @property
    def descendantArcroles(self) -> tuple[str, str, str, str]:  # type: ignore[override]
        return (XbrlConst.tableAspectNodeFilter, XbrlConst.tableAspectNodeFilterMMDD,
                XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)

    @property
    def filterRelationships(self) -> list[ModelRelationship | ModelConceptName]:
        try:
            return self._filterRelationships
        except AttributeError:
            rels: list[ModelRelationship | ModelConceptName] = []  # order so conceptName filter is first (if any) (may want more sorting in future)
            # fact space is filtered by both table filter and aspect filters, table first.
            for rel in self.modelXbrl.relationshipSet((XbrlConst.tableAspectNodeFilterMMDD, XbrlConst.tableAspectNodeFilter)).fromModelObject(self):  # type: ignore[union-attr]
                if isinstance(rel.toModelObject, ModelConceptName):
                    rels.insert(0, rel)  # put conceptName filters first
                else:
                    rels.append(rel)
            tableNode = self.parentTableNode
            if tableNode is not None:
                rels.extend(tableNode.filterRelationships)
            self._filterRelationships = rels
            return rels

    def hasAspect(self, structuralNode: StrctMdlStructuralNode, aspect: int) -> bool:
        return aspect in self.aspectsCovered()

    def aspectsCovered(self, varBinding: VariableBinding | None = None) -> set[int | QName]:
        try:
            return self._aspectsCovered
        except AttributeError:
            self._aspectsCovered = set()
            self._dimensionsCovered = set()
            self.includeUnreportedValue = False
            aspectElt = XmlUtil.child(self, self.namespaceURI, ("conceptAspect", "unitAspect", "entityIdentifierAspect", "periodAspect", "dimensionAspect"))
            if aspectElt is not None:
                if aspectElt.localName == "dimensionAspect":
                    dimQname = qname(aspectElt, aspectElt.textValue)
                    self._aspectsCovered.add(dimQname)
                    self._aspectsCovered.add(Aspect.DIMENSIONS)
                    self._dimensionsCovered.add(dimQname)
                    self.includeUnreportedValue = aspectElt.get("includeUnreportedValue") in ("true", "1")
                else:
                    self._aspectsCovered.add(aspectNodeAspectCovered[aspectElt.localName])
            return self._aspectsCovered

    def aspectValue(self, xpCtx: XPathContext, aspect: int, inherit: bool = False) -> set[QName] | None:  # type: ignore[override]
        if aspect == Aspect.DIMENSIONS:
            return self._dimensionsCovered
        # does not apply to filter, value can only come from a bound fact
        return None

    def filteredFactsPartitions(self, xpCtx: XPathContext, facts: Iterable[ModelFact]) -> Any:
        filteredFacts = formulaEvaluatorFilterFacts(xpCtx, VariableBinding(xpCtx),  # type: ignore[no-untyped-call]
                                                    facts, self.filterRelationships, None)
        if not self.includeUnreportedValue:
            # remove unreported falue
            reportedAspectFacts = set()
            for fact in filteredFacts:
                if all(fact.context is not None and
                       isinstance(fact.context.dimValue(dimAspect), (ModelDimensionValue, QName))  # include default dimension values
                       for dimAspect in self._dimensionsCovered):
                    reportedAspectFacts.add(fact)
        else:
            reportedAspectFacts = filteredFacts
        return factsPartitions(xpCtx, reportedAspectFacts, self.aspectsCovered())  # type: ignore[no-untyped-call]

    @property
    def propertyView(self) -> tuple[tuple[str, str | None], ...]:
        return ((("id", self.id),
                 ("xlink:label", self.xlinkLabel),
                 ("aspect", ", ".join(aspectStr(aspect)
                                      for aspect in self.aspectsCovered()
                                      if aspect != Aspect.DIMENSIONS)),
                 ("definition", self.definitionNodeView)) +
                self.definitionLabelsView)


from arelle.ModelObjectFactory import elementSubstitutionModelClass

elementSubstitutionModelClass.update((
    # IWD
    (XbrlConst.qnTableTableMMDD, DefnMdlTable),
    (XbrlConst.qnTableBreakdownMMDD, DefnMdlBreakdown),
    (XbrlConst.qnTableRuleSetMMDD, DefnMdlRuleSet),
    (XbrlConst.qnTableRuleNodeMMDD, DefnMdlRuleDefinitionNode),
    (XbrlConst.qnTableConceptRelationshipNodeMMDD, DefnMdlConceptRelationshipNode),
    (XbrlConst.qnTableDimensionRelationshipNodeMMDD, DefnMdlDimensionRelationshipNode),
    (XbrlConst.qnTableAspectNodeMMDD, DefnMdlAspectNode),
    # REC
    (XbrlConst.qnTableTable, DefnMdlTable),
    (XbrlConst.qnTableBreakdown, DefnMdlBreakdown),
    (XbrlConst.qnTableRuleSet, DefnMdlRuleSet),
    (XbrlConst.qnTableRuleNode, DefnMdlRuleDefinitionNode),
    (XbrlConst.qnTableConceptRelationshipNode, DefnMdlConceptRelationshipNode),
    (XbrlConst.qnTableDimensionRelationshipNode, DefnMdlDimensionRelationshipNode),
    (XbrlConst.qnTableAspectNode, DefnMdlAspectNode),
     ))

# import after other modules resolved to prevent circular references
from arelle.FunctionXfi import concept_relationships
