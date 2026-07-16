'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Sequence

from arelle import ViewWinTree
from arelle.typing import TypeGetText

_: TypeGetText

if TYPE_CHECKING:
    from tkinter.ttk import Notebook

    from arelle.ModelObject import ModelObject
    from arelle.ModelXbrl import ModelXbrl


def viewProperties(modelXbrl: ModelXbrl, tabWin: Notebook) -> None:
    modelXbrl.modelManager.showStatus(_("viewing properties"))
    view = ViewProperties(modelXbrl, tabWin)
    view.treeView["columns"] = ("value",)
    view.treeView.column("#0", width=75, anchor="w")
    view.treeView.heading("#0", text="Property")
    view.treeView.column("value", width=600, anchor="w")
    view.treeView.heading("value", text="Value")
    view.treeView["displaycolumns"] = ("value",)
    view.view()

class ViewProperties(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl: ModelXbrl, tabWin: Notebook) -> None:
        super(ViewProperties, self).__init__(modelXbrl, tabWin, "Properties", True)
        self.openProperties: set[str] = set()

    def view(self) -> None:
        self.viewProperties(None, "")

    def cleanPreviousNodes(self, parentNode: str) -> None:
        for previousNode in self.treeView.get_children(parentNode):
            self.cleanPreviousNodes(previousNode)
            text = self.treeView.item(previousNode, "text")
            if str(self.treeView.item(previousNode, "open")) in ("true", "1"):
                self.openProperties.add(text)
            else:
                self.openProperties.discard(text)
            self.treeView.delete(previousNode)

    def viewProperties(self, modelObject: ModelObject | None, parentNode: str) -> None:
        try:
            self.cleanPreviousNodes(parentNode)
        except Exception:
            pass    # possible tkinter issues
        if modelObject is not None and hasattr(modelObject, "propertyView"):
            self.showProperties(modelObject.propertyView, parentNode, 1)

    def showProperties(
            self,
            properties: tuple[tuple[str, ...], ...] | tuple[tuple[str, Any, tuple[tuple[str, ...], ...]], ...],
            parentNode: str,
            id: int
        ) -> int:
        for tuple in properties:
            if tuple:
                lenTuple = len(tuple)
                if 2 <= lenTuple <= 3:
                    strId = str(id)
                    node = self.treeView.insert(parentNode, "end", strId, text=tuple[0], tags=("odd" if id & 1 else "even",))
                    self.treeView.set(strId, "value", tuple[1])
                    id += 1
                    if lenTuple == 3:
                        if tuple[0] in self.openProperties:
                            self.treeView.item(node, open=True)
                        id = self.showProperties(tuple[2], node, id)  # type: ignore[arg-type]
        return id

    def viewModelObject(self, modelObject: ModelObject) -> None:
        self.viewProperties(modelObject, "")
