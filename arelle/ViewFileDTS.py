'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from typing import TYPE_CHECKING

from arelle import ViewFile
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewDTS(modelXbrl: ModelXbrl, outfile: str | None) -> None:
    view = ViewDTS(modelXbrl, outfile)
    modelXbrl.modelManager.showStatus(_("viewing DTS"))
    assert modelXbrl.modelDocument is not None
    view.treeDepth(modelXbrl.modelDocument, 1, set()) # count of cols starts at 1 because no ELR headers as with relationships
    view.addRow(["DTS"], asHeader=True)
    view.viewDtsElement(modelXbrl.modelDocument, {"entry"}, 0, set())
    view.close()


class ViewDTS(ViewFile.View):
    def __init__(self, modelXbrl: ModelXbrl, outfile: str | None) -> None:
        super(ViewDTS, self).__init__(modelXbrl, outfile, "DTS")

    def treeDepth(self, modelDocument: ModelDocument, indent: int, visited: set[ModelDocument]) -> None:
        visited.add(modelDocument)
        if indent > self.treeCols: self.treeCols = indent
        for referencedDocument in modelDocument.referencesDocument.keys():
            if referencedDocument not in visited:
                self.treeDepth(referencedDocument, indent + 1, visited)
        visited.remove(modelDocument)

    def viewDtsElement(
            self,
            modelDocument: ModelDocument,
            referenceTypes: set[str],
            indent: int,
            visited: set[ModelDocument]
        ) -> None:
        visited.add(modelDocument)
        dtsObjectType = modelDocument.gettype()
        xmlRowElementName = dtsObjectType
        sortedReferenceTypes: list[str] | str = sorted(referenceTypes)
        if self.type == ViewFile.XML:
            xmlRowElementName = xmlRowElementName.replace(" ", "-")
            sortedReferenceTypes = " ".join(sortedReferenceTypes)
        attr: dict[str, str | list[str]] = {"file": modelDocument.basename, "referenceTypes": sortedReferenceTypes}
        if not modelDocument.inDTS:
            attr["inDTS"] = "false"
        self.addRow(["{0} - {1}".format(modelDocument.basename, dtsObjectType)], treeIndent=indent,
                    xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr, xmlCol0skipElt=True)
        for referencedDocument, ref in modelDocument.referencesDocument.items():
            if referencedDocument not in visited:
                self.viewDtsElement(referencedDocument, ref.referenceTypes, indent + 1, visited)
        visited.remove(modelDocument)
