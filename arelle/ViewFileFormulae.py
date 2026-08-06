"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from arelle import XbrlConst, ViewFile
from arelle.ModelDtsObject import ModelRelationship
from arelle.ModelFormulaObject import ModelParameter, ModelVariable, ModelVariableSetAssertion, ModelConsistencyAssertion
from arelle.ViewUtilFormulae import rootFormulaObjects, formulaObjSortKey
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelObject import ModelObject
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelRelationshipSet import ModelRelationshipSet
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewFormulae(
    modelXbrl: ModelXbrl | None,
    outfile: str | FileNamedStringIO | None,
    header: str,
    lang: str | None = None,
) -> None:
    modelXbrl.modelManager.showStatus(_("viewing formulae"))  # type: ignore[union-attr]
    view = ViewFormulae(modelXbrl, outfile, header, lang)
    view.view()
    view.close()


class ViewFormulae(ViewFile.View):
    varSetFilterRelationshipSet: ModelRelationshipSet
    allFormulaRelationshipsSet: ModelRelationshipSet
    treeCols: int

    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        outfile: str | FileNamedStringIO | None,
        header: str,
        lang: str | None,
    ) -> None:
        super(ViewFormulae, self).__init__(modelXbrl, outfile, header, lang)

    def view(self) -> None:
        # determine relationships indent depth
        rootObjects = rootFormulaObjects(self)
        self.treeCols = 0
        for rootObject in rootObjects:
            self.treeDepth(rootObject, 1, set())
        self.addRow(["Formula object", "Label", "Cover", "Com\u00ADple\u00ADment", "Bind as se\u00ADquence", "Expression"], asHeader=True)
        for rootObject in sorted(rootObjects, key=formulaObjSortKey):
            self.viewFormulaObjects(rootObject, None, 0, set())
        for cfQnameArity in sorted(qnameArity
                                   for qnameArity in self.modelXbrl.modelCustomFunctionSignatures.keys()  # type: ignore[union-attr]
                                   if isinstance(qnameArity, (tuple, list))):
            cfObject = self.modelXbrl.modelCustomFunctionSignatures[cfQnameArity]  # type: ignore[union-attr,index]
            self.viewFormulaObjects(cfObject, None, 0, set())

    def treeDepth(self, fromObject: ModelObject | None, indent: int, visited: set[ModelObject]) -> None:
        if fromObject is None:
            return
        if indent > self.treeCols:
            self.treeCols = indent
        if fromObject not in visited:
            visited.add(fromObject)
            relationshipArcsShown = set()
            for relationshipSet in (self.varSetFilterRelationshipSet,
                                    self.allFormulaRelationshipsSet):
                for modelRel in relationshipSet.fromModelObject(fromObject):
                    if modelRel.arcElement not in relationshipArcsShown:
                        relationshipArcsShown.add(modelRel.arcElement)
                        toObject = modelRel.toModelObject
                        self.treeDepth(toObject, indent + 1, visited)
            visited.remove(fromObject)

    def viewFormulaObjects(
        self,
        fromObject: ModelObject | None,
        fromRel: ModelRelationship | None,
        indent: int,
        visited: set[ModelObject],
    ) -> None:
        if fromObject is None:
            return
        if isinstance(fromObject, (ModelVariable, ModelParameter)) and fromRel is not None:
            text = "{0} ${1}".format(fromObject.localName, fromRel.variableQname)
            xmlRowEltAttr = {"type": str(fromObject.localName), "name": str(fromRel.variableQname)}
        elif isinstance(fromObject, (ModelVariableSetAssertion, ModelConsistencyAssertion)):
            text = "{0} {1}".format(fromObject.localName, fromObject.id)
            xmlRowEltAttr = {"type": str(fromObject.localName), "id": str(fromObject.id)}
        else:
            text = fromObject.localName
            xmlRowEltAttr = {"type": str(fromObject.localName)}
        cols: list[str | None] = [text, fromObject.xlinkLabel]  # label
        if fromRel is not None and fromRel.elementQname == XbrlConst.qnVariableFilterArc:
            cols.append("true" if fromRel.isCovered else "false")  # cover
            cols.append("true" if fromRel.isComplemented else "false")  # complement
        else:
            cols.append(None)  # cover
            cols.append(None)  # compelement
        if isinstance(fromObject, ModelVariable):
            cols.append(fromObject.bindAsSequence) # bind as sequence
        else:
            cols.append(None)  # bind as sequence
        if hasattr(fromObject, "viewExpression"):
            cols.append(fromObject.viewExpression)  # expression
        else:
            cols.append(None)  # expression
        self.addRow(cols, treeIndent=indent, xmlRowElementName="formulaObject", xmlRowEltAttr=xmlRowEltAttr, xmlCol0skipElt=True)
        if fromObject not in visited:
            visited.add(fromObject)
            relationshipArcsShown = set()
            for relationshipSet in (self.varSetFilterRelationshipSet,
                                    self.allFormulaRelationshipsSet):
                for modelRel in relationshipSet.fromModelObject(fromObject):
                    if modelRel.arcElement not in relationshipArcsShown:
                        relationshipArcsShown.add(modelRel.arcElement)
                        toObject = modelRel.toModelObject
                        self.viewFormulaObjects(toObject, modelRel, indent + 1, visited)
            visited.remove(fromObject)
