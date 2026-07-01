'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import os
from tkinter.ttk import Notebook
from typing import TYPE_CHECKING, Iterable

from arelle import ViewWinTree
from arelle.ModelDocumentType import ModelDocumentType
from arelle.typing import TypeGetText

_: TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelObject import ModelObject
    from arelle.ModelXbrl import ModelXbrl


def viewDTS(
    modelXbrl: ModelXbrl,
    tabWin: Notebook,
    altTabWin: Notebook | None = None,
) -> None:
    view = ViewDTS(modelXbrl, tabWin)
    modelXbrl.modelManager.showStatus(_("viewing DTS"))
    view.view()

    view.contextMenu()
    view.menuAddExpandCollapse()
    view.menuAddClipboard()
    view.menuAddViews(addClose=False, tabWin=altTabWin)


class ViewDTS(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl: ModelXbrl, tabWin: Notebook) -> None:
        super(ViewDTS, self).__init__(modelXbrl, tabWin, "DTS", True)

    def view(self) -> None:
        self.clearTreeView()
        self.viewDtsElement(self.modelXbrl.modelDocument, "", 1, set(), {self.modelXbrl.modelDocument})  # type: ignore[arg-type]

    def viewDtsElement(
        self,
        modelDocument: ModelDocument,
        parentNode: str,
        n: int,
        parents: set[ModelDocument],
        siblings: Iterable[ModelDocument],
    ) -> None:
        if modelDocument.type == ModelDocumentType.INLINEXBRLDOCUMENTSET:
            if modelDocument.entrypoint is not None and "id" in modelDocument.entrypoint:
                text = f"{modelDocument.entrypoint['id']} (IXDS)"
            else:
                text = "Inline XBRL Document Set"  # no file name or ID to display
        else:
            text = "{0} - {1}".format(os.path.basename(modelDocument.uri), modelDocument.gettype())
        node = self.treeView.insert(parentNode, "end",
                    text=text,
                    tags=("odd" if n & 1 else "even",))
        children = modelDocument.referencesDocument.keys()
        childFamily: set[ModelDocument] = parents | set(siblings)
        for i, referencedDocument in enumerate(sorted(children, key=lambda d: d.objectIndex)):  # provide consistent order
            if referencedDocument not in parents:
                self.viewDtsElement(referencedDocument, node, n + i + 1, childFamily, children)

    def viewModelObject(self, modelObject: ModelObject) -> None:
        pass
