"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle import XbrlConst, XmlUtil
from arelle.formula import XPathContext
from arelle.ModelFormulaObject import ModelTypedDimension, ModelParameter
from arelle.Aspect import aspectStr, Aspect
from arelle.ModelRenderingObject import (
    DefnMdlDefinitionNode,
    DefnMdlBreakdown,
    DefnMdlClosedDefinitionNode,
    DefnMdlRuleDefinitionNode,
    DefnMdlAspectNode,
    DefnMdlRelationshipNode,
    DefnMdlDimensionRelationshipNode, DefnMdlTable,
    )
from arelle.ModelValue import QName
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDtsObject import ModelRelationship
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelObject import ModelObject

_: TypeGetText


def init(modelXbrl: ModelXbrl) -> None:
    # setup modelXbrl for rendering evaluation

    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions, ModelDocument
    from arelle.formula import ValidateFormula, FormulaEvaluator
    ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)

    hasXbrlTables = False

    # validate table linkbase dimensions
    for baseSetKey in modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and XbrlConst.isTableRenderingArcrole(arcrole):
            ValidateFormula.checkBaseSet(modelXbrl, arcrole, ELR, modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname))
            if arcrole in (XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD):
                hasXbrlTables = True

    # provide context for view
    if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):  # type: ignore[union-attr]
        instance = None # use instance of the entry point
    else: # need dummy instance
        instance = ModelDocument.create(modelXbrl, ModelDocument.Type.INSTANCE,
                                        "dummy.xml",  # fake URI and fake schemaRef
                                        ["http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd"])

    if hasXbrlTables:
        FormulaEvaluator.init()
        modelXbrl.rendrCntx = XPathContext.create(modelXbrl, instance)  # type: ignore[attr-defined]

        modelXbrl.profileStat(None)

        # setup fresh parameters from formula options
        modelXbrl.parameters = modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces)  # type: ignore[attr-defined]

        # validate parameters and custom function signatures
        ValidateFormula.validate(modelXbrl, xpathContext=modelXbrl.rendrCntx,  # type: ignore[attr-defined,arg-type]
                                  parametersOnly=True, statusMsg=_("compiling rendering tables"))

        # compile and validate tables
        for modelTable in modelXbrl.modelRenderingTables:
            modelTable.fromInstanceQnames = None  # type: ignore[attr-defined] # required if referred to by variables scope chaining
            modelTable.compile()
            # remove unwanted messages when running conformance suite
            if (len(modelXbrl.factsInInstance) == 0 and # these errors not expected when there are no instance facts
                modelXbrl.modelManager.loadedModelXbrls[0].modelDocument.type in ModelDocument.Type.TESTCASETYPES):  # type: ignore[union-attr]
                for i in range(len(modelXbrl.errors)):
                    if modelXbrl.errors[i] in ("xfie:invalidExplicitDimensionQName",):
                        del modelXbrl.errors[i]

            modelTable.priorAspectAxisDisposition = {}  # type: ignore[attr-defined]
            # check ordinate aspects against aspectModel
            uncoverableAspects: tuple[int | QName, ...] = ()
            aspectsCovered: set[int | QName] = set()
            for tblBrkdnRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD)).fromModelObject(modelTable):
                breakdownAspectsCovered: set[int | QName] = set()
                hasCoveredAspect = checkBreakdownDefinitionNode(modelXbrl, modelTable, tblBrkdnRel, tblBrkdnRel.axis, uncoverableAspects, breakdownAspectsCovered)
                aspectsCovered |= breakdownAspectsCovered
                checkBreakdownLeafNodeAspects(modelXbrl, modelTable, tblBrkdnRel, set(), breakdownAspectsCovered)
            if Aspect.CONCEPT not in aspectsCovered:
                modelXbrl.error("xbrlte:tableMissingConceptAspect",
                    _("Table %(xlinkLabel)s does not include the concept aspect as one of its participating aspects"),
                    modelObject=modelTable, xlinkLabel=modelTable.xlinkLabel)
            del modelTable.priorAspectAxisDisposition  # type: ignore[attr-defined]
            # check for table-parameter name clash
            parameterNames: dict[QName | None, ModelRelationship] = {}
            for tblParamRel in modelXbrl.relationshipSet((XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)).fromModelObject(modelTable):
                parameterName = tblParamRel.variableQname
                if parameterName in parameterNames:
                    modelXbrl.error("xbrlte:tableParameterNameClash",
                        _("Table %(xlinkLabel)s has parameter name clash for variable %(name)s"),
                        modelObject=(modelTable, tblParamRel, parameterNames[parameterName]), xlinkLabel=modelTable.xlinkLabel, name=parameterName)
                else:
                    parameterNames[parameterName] = tblParamRel

        if instance is not None: # no instance was provided, check for context-dependent XPath expressions
            for paramQname, modelParameter in modelXbrl.qnameParameters.items():
                if isinstance(modelParameter, ModelParameter):
                    if any(hasattr(p, "name") and p.name in XPathContext.PATH_OPS for p in modelParameter.selectProg):  # type: ignore[union-attr]
                        modelXbrl.error("arelle:tableParameterRequiresInstance",
                            _("Parameter %(qname)s requires an instance as a context item for the XPath expression but no instance was provided."),
                            modelObject=modelParameter, qname=paramQname)

        modelXbrl.profileStat(_("compileTables"))


def checkBreakdownDefinitionNode(
        modelXbrl: ModelXbrl,
        modelTable: DefnMdlTable,
        tblBrkdnRel: ModelRelationship,
        tblAxisDisposition: Any,
        uncoverableAspects: tuple[int | QName, ...],
        aspectsCovered: set[int | QName],
) -> bool:
    definitionNode: ModelObject | None = tblBrkdnRel.toModelObject
    hasCoveredAspect = False
    if isinstance(definitionNode, DefnMdlDefinitionNode):
        for aspect in definitionNode.aspectsCovered():
            aspectsCovered.add(aspect)
            if (aspect in uncoverableAspects or
                (isinstance(aspect, QName) and modelTable.aspectModel == "non-dimensional")):
                modelXbrl.error("xbrlte:axisAspectModelMismatch",
                    _("%(definitionNode)s %(xlinkLabel)s, aspect model %(aspectModel)s, aspect %(aspect)s not allowed"),
                    modelObject=modelTable, definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel, aspectModel=modelTable.aspectModel,
                    aspect=str(aspect) if isinstance(aspect, QName) else Aspect.label[aspect])
            hasCoveredAspect = True
            if aspect in modelTable.priorAspectAxisDisposition:  # type: ignore[attr-defined]
                otherAxisDisposition, otherDefinitionNode = modelTable.priorAspectAxisDisposition[aspect]  # type: ignore[attr-defined]
                if tblAxisDisposition != otherAxisDisposition and aspect != Aspect.DIMENSIONS:
                    modelXbrl.error("xbrlte:aspectClashBetweenBreakdowns",
                        _("%(definitionNode)s %(xlinkLabel)s, aspect %(aspect)s defined on axes of disposition %(axisDisposition)s and %(axisDisposition2)s"),
                        modelObject=(modelTable, definitionNode, otherDefinitionNode), definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel,
                        axisDisposition=tblAxisDisposition, axisDisposition2=otherAxisDisposition,
                        aspect=str(aspect) if isinstance(aspect, QName) else Aspect.label[aspect])
            else:
                modelTable.priorAspectAxisDisposition[aspect] = (tblAxisDisposition, definitionNode)  # type: ignore[attr-defined]
        ruleSetChildren = XmlUtil.children(definitionNode, definitionNode.namespaceURI, "ruleSet")
        if definitionNode.isMerged or isinstance(definitionNode, (DefnMdlRelationshipNode, DefnMdlAspectNode)):
            labelRels = modelXbrl.relationshipSet(XbrlConst.elementLabel).fromModelObject(definitionNode)
            if labelRels:
                modelXbrl.error("xbrlte:invalidUseOfLabel",
                    _("Merged %(definitionNode)s %(xlinkLabel)s has label(s)"),
                    modelObject=[modelTable, definitionNode] + [r.toModelObject for r in labelRels],
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
        if definitionNode.isMerged:
            if ruleSetChildren:
                modelXbrl.error("xbrlte:mergedRuleNodeWithTaggedRuleSet",
                    _("Merged %(definitionNode)s %(xlinkLabel)s has tagged rule set(s)"),
                    modelObject=[modelTable, definitionNode, *ruleSetChildren],
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
            if not definitionNode.isAbstract:
                modelXbrl.error("xbrlte:nonAbstractMergedRuleNode",
                    _("Merged %(definitionNode)s %(xlinkLabel)s is not abstract"),
                    modelObject=(modelTable, definitionNode), definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
    if isinstance(definitionNode, DefnMdlRuleDefinitionNode):
        tagConstraintSets: dict[str, ModelObject] = {}
        otherConstraintSet = None
        # must look at xml constructs for duplicates
        for ruleSet in XmlUtil.children(definitionNode, definitionNode.namespaceURI, "ruleSet"):
            tag = ruleSet.tagName  # type: ignore[attr-defined]
            if tag is not None:  # named constraint sets only
                for aspect in ruleSet.aspectsCovered():  # type: ignore[attr-defined]
                    if aspect != Aspect.DIMENSIONS:
                        modelTable.aspectsInTaggedConstraintSets.add(aspect)
            if tag in tagConstraintSets:
                modelXbrl.error("xbrlte:duplicateTag",
                    _("%(definitionNode)s %(xlinkLabel)s duplicate rule set tags %(tag)s"),
                    modelObject=(modelTable, definitionNode, tagConstraintSets[tag], ruleSet),
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel, tag=tag)
            else:
                tagConstraintSets[tag] = ruleSet
            if aspect in ruleSet.aspectsCovered():  # type: ignore[attr-defined]
                hasCoveredAspect = True
                aspectsCovered.add(aspect)
        for tag, constraintSet in definitionNode.constraintSets.items():
            if otherConstraintSet is None:
                otherConstraintSet = constraintSet
            elif otherConstraintSet.aspectsModelCovered() != constraintSet.aspectsModelCovered():  # type: ignore[attr-defined,union-attr]
                modelXbrl.error("xbrlte:constraintSetAspectMismatch",
                    _("%(definitionNode)s %(xlinkLabel)s constraint set mismatches between %(tag1)s and %(tag2)s in constraints %(aspects)s"),
                    modelObject=(modelTable, definitionNode, otherConstraintSet, constraintSet),
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel,
                    tag1=getattr(otherConstraintSet, "tagName", "(no tag)"), tag2=getattr(constraintSet, "tagName", "(no tag)"),
                    aspects=", ".join(aspectStr(aspect)
                                      for aspect in otherConstraintSet.aspectsCovered() ^ constraintSet.aspectsCovered()  # type: ignore[attr-defined,union-attr]
                                      if aspect != Aspect.DIMENSIONS))
    if isinstance(definitionNode, DefnMdlDimensionRelationshipNode):
        hasCoveredAspect = True
        if modelTable.aspectModel == "non-dimensional":
            modelXbrl.error("xbrlte:axisAspectModelMismatch",
                _("DimensionRelationship axis %(xlinkLabel)s can't be used in non-dimensional aspect model"),
                modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel)
        # TLB 1.0 legacy use of Hypercube Linkroles to find domain roots
        if modelXbrl.parameters.get(QName(None, None, "tlbDimRelsUseHcRoleForDomainRoots"), ("", ""))[1] in ("true", True):  # type: ignore[attr-defined]
            definitionNode.tlbDimRelsUseHcRoleForDomainRoots = True

    definitionNodeHasChild = False
    for axisSubtreeRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)).fromModelObject(definitionNode):  # type: ignore[arg-type]
        if checkBreakdownDefinitionNode(modelXbrl, modelTable, axisSubtreeRel, tblAxisDisposition, uncoverableAspects, aspectsCovered):
            hasCoveredAspect = True # something below was covering
        definitionNodeHasChild = True
    if isinstance(definitionNode, DefnMdlAspectNode):
        for aspect in definitionNode.aspectsCovered():
            if isinstance(aspect, QName):  # dimension aspect
                concept = modelXbrl.qnameConcepts.get(aspect)
                if concept is None or not concept.isDimensionItem:
                    modelXbrl.error("xbrlte:invalidDimensionQNameOnAspectNode",
                        _("Aspect node %(xlinkLabel)s dimensional aspect %(dimension)s is not a dimension"),
                        modelObject=(modelTable, definitionNode), xlinkLabel=definitionNode.xlinkLabel, dimension=aspect)
            for rel in definitionNode.filterRelationships:
                filter: ModelObject | None = rel.toModelObject  # type: ignore[union-attr]
                if filter is not None:
                    if isinstance(filter, ModelTypedDimension) and filter.dimQname:
                        concept = modelXbrl.qnameConcepts.get(filter.dimQname)
                        if (concept is None or not concept.isDimensionItem) and len(modelXbrl.factsInInstance) > 0:
                            modelXbrl.error("xfie:invalidTypedDimensionQName",
                                _("Aspect node %(xlinkLabel)s dimensional aspect %(dimension)s is not a dimension"),
                                modelObject=(modelTable, definitionNode), xlinkLabel=definitionNode.xlinkLabel, dimension=aspect)

    if not definitionNodeHasChild:
        if (definitionNode.namespaceURI in ("http://www.eurofiling.info/2010/rendering", "http://xbrl.org/2011/table")  # type: ignore[operator,union-attr]
            and not hasCoveredAspect):
            modelXbrl.error("xbrlte:aspectValueNotDefinedByOrdinate",
                _("%(definitionNode)s %(xlinkLabel)s does not define an aspect"),
                modelObject=(modelTable, definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName)  # type: ignore[union-attr]
        if (isinstance(definitionNode, DefnMdlClosedDefinitionNode) and
            definitionNode.isAbstract):
            modelXbrl.error("xbrlte:abstractRuleNodeNoChildren",
                _("Abstract %(definitionNode)s %(xlinkLabel)s has no children"),
                modelObject=(modelTable, definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName)
    return hasCoveredAspect


def checkBreakdownLeafNodeAspects(
        modelXbrl: ModelXbrl,
        modelTable: DefnMdlTable,
        tblBrkdnRel: ModelRelationship,
        parentAspectsCovered: set[int | QName],
        breakdownAspects: set[int | QName],
) -> None:
    breakdown = tblBrkdnRel.toModelObject

    for dfnRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD)).fromModelObject(breakdown):  # type: ignore[arg-type]
        definitionNode: ModelObject | None = dfnRel.toModelObject
        aspectsCovered = parentAspectsCovered.copy()
        if isinstance(definitionNode, DefnMdlDefinitionNode):
            for aspect in definitionNode.aspectsCovered():
                aspectsCovered.add(aspect)
            if isinstance(definitionNode, DefnMdlRuleDefinitionNode):
                for ruleSet in XmlUtil.children(definitionNode, definitionNode.namespaceURI, "ruleSet"):
                    for aspect in ruleSet.aspectsCovered():  # type: ignore[attr-defined]
                        aspectsCovered.add(aspect)
            definitionNodeHasChild = False
            for axisSubtreeRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD)).fromModelObject(definitionNode):
                checkBreakdownLeafNodeAspects(modelXbrl, modelTable, axisSubtreeRel, aspectsCovered, breakdownAspects)
                definitionNodeHasChild = True

            if not definitionNode.isAbstract and not isinstance(definitionNode, DefnMdlBreakdown): # this is a leaf node
                missingAspects = set(aspect
                                     for aspect in breakdownAspects
                                     if aspect not in aspectsCovered and
                                        aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS) and not isinstance(aspect, QName))

                isForever = definitionNode.aspectValue(modelXbrl.rendrCntx, Aspect.PERIOD_TYPE) == "forever"  # type: ignore[attr-defined,comparison-overlap]
                # a definition node cannot define a period and a instant, but it's not the case for the breakdown Aspects
                if (Aspect.START in aspectsCovered and Aspect.END in aspectsCovered) or isForever:
                    missingAspects.discard(Aspect.INSTANT)
                elif Aspect.INSTANT in aspectsCovered or isForever:
                    missingAspects.discard(Aspect.START)
                    missingAspects.discard(Aspect.END)

                if (missingAspects):
                    modelXbrl.error("xbrlte:missingAspectValue",
                        _("%(definitionNode)s %(xlinkLabel)s does not define an aspect for %(aspect)s"),
                        modelObject=(modelTable, definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName,
                        aspect=", ".join(aspectStr(aspect) for aspect in missingAspects))
