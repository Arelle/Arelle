"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import io
import json
from collections import OrderedDict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from arelle import ViewFile
from arelle.ModelObject import ModelObject
from arelle.Aspect import Aspect, aspectStr
from arelle.ModelRenderingObject import (StrctMdlNode, StrctMdlTable, StrctMdlStructuralNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_IMPLIES_DEFAULT_MEMBER,
                                         ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         ROLLUP_FOR_CLOSED_DEFINITION_NODE, ROLLUP_FOR_OPEN_DEFINITION_NODE,
                                         ROLLUP_FOR_DEFINITION_NODE)
from arelle.rendering.RenderingResolution import resolveTableStructure
from arelle import XbrlConst
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewRenderedStructuralModel(
        modelXbrl: ModelXbrl,
        outfile: str,
        lang: str | None = None,
        viewTblELR: str | None = None,
        sourceView: Any = None,
        cssExtras: str = "",
) -> None:
    modelXbrl.modelManager.showStatus(_("saving rendered structure"))
    view = ViewRenderedStructuralModel(modelXbrl, outfile, lang, cssExtras)
    view.view(outfile, viewTblELR)
    view.close(noWrite=True)  # written out below
    modelXbrl.modelManager.showStatus(_("rendering table saved to {0}").format(outfile), clearAfter=5000)


class ViewRenderedStructuralModel(ViewFile.View):
    def __init__(self, modelXbrl: ModelXbrl, outfile: str, lang: str | None, cssExtras: str) -> None:
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedStructuralModel, self).__init__(modelXbrl, outfile,
                                               "dummyObject",
                                               lang,
                                               style="rendering",
                                               cssExtras=cssExtras)

        class nonTkBooleanVar:
            def __init__(self, value: bool = True) -> None:
                self.value = value

            def set(self, value: bool) -> None:
                self.value = value

            def get(self) -> bool:
                return self.value

        # context menu boolean vars (non-tkinter boolean
        self.ignoreDimValidity = nonTkBooleanVar(value=True)

    def tableModelQName(self, localName: str) -> str:
        return "{" + self.tableModelNamespace + "}" + localName

    def viewReloadDueToMenuAction(self, *args: Any) -> None:
        self.view()  # type: ignore[call-arg]

    def view(self, outfile: str, viewTblELR: str | None = None) -> None:
        tblELRs: Iterable[str]
        if viewTblELR is not None:
            tblELRs = (viewTblELR,)
        else:
            tblELRs = self.modelXbrl.relationshipSet("Table-rendering").linkRoleUris  # type: ignore[union-attr]

        for tblELR in tblELRs:
            self.zOrdinateChoices: dict[Any, Any] = {}

            strctMdlTable = resolveTableStructure(self, tblELR)  # type: ignore[no-untyped-call]
            if strctMdlTable is None:
                continue

            # uncomment below for debugging Definition and Structural Models
            def jsonStrctMdlEncoder(obj: StrctMdlNode, indent: str = "\n") -> OrderedDict[str, Any] | None:
                if isinstance(obj, StrctMdlNode):
                    o: OrderedDict[str, Any] = OrderedDict()
                    o["object"] = obj.__repr__()
                    if obj.xlinkLabel is not None:
                        o["defnMdlNode"] = f"{obj.defnMdlNode.modelXbrl.modelDocument.basename} line {obj.defnMdlNode.sourceline} {obj.xlinkLabel}"  # type: ignore[union-attr]
                    if isinstance(obj, StrctMdlTable):
                        o["entryFile"] = obj.defnMdlNode.modelXbrl.modelDocument.basename,  # type: ignore[union-attr]
                    if obj.axis:
                        o["axis"] = obj.axis
                    if obj.isAbstract:
                        o["abstract"] = True
                    if isinstance(obj, StrctMdlStructuralNode):
                        if obj.hasChildRollup:
                            o["hasChildRollup"] = True
                        if obj.rollup:
                            o["rollup"] = {ROLLUP_SPECIFIES_MEMBER: "rollup specifies member",
                                           ROLLUP_IMPLIES_DEFAULT_MEMBER: "rollup implies default member",
                                           ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE: "rollup for concept relationship nesting",
                                           ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE: "rollup for concept relationship nesting",
                                           ROLLUP_FOR_CLOSED_DEFINITION_NODE: "rollup for closed definition node",
                                           ROLLUP_FOR_OPEN_DEFINITION_NODE: "rollup for open definition node",
                                           ROLLUP_FOR_DEFINITION_NODE: "rollup for definition node"}[obj.rollup]
                        o["structuralDepth"] = obj.structuralDepth
                        _aspectsCovered = obj.aspectsCovered()
                        if _aspectsCovered:
                            o["aspectsCovered"] = OrderedDict((aspectStr(a),
                                                               str(v.stringValue if isinstance(v, ModelObject) else v
                                                                   ).replace(OPEN_ASPECT_ENTRY_SURROGATE, "OPEN_ASPECT_ENTRY_"))
                                                              for a in _aspectsCovered
                                                              if a != Aspect.DIMENSIONS
                                                              for v in (obj.aspectValue(a),))
                    if obj.tagSelector:
                        o["tagSelector"] = obj.tagSelector
                    if obj.strctMdlChildNodes:
                        o["strctMdlChildNodes"] = obj.strctMdlChildNodes
                    return o
                raise TypeError("Type {} is not supported for json output".format(type(obj).__name__))
            with io.open(outfile, "wt") as fh:
                json.dump(strctMdlTable, fh, ensure_ascii=False, indent=2, default=jsonStrctMdlEncoder)
