'''
See COPYRIGHT.md for copyright information.
'''
from arelle import (ViewWinTree, ModelObject)
from tkinter import TRUE

def viewProperties(modelXbrl, tabWin):
    modelXbrl.modelManager.showStatus(_("viewing properties"))
    view = ViewProperties(modelXbrl, tabWin)
    view.treeView["columns"] = ("value")
    # Only the value column stretches to take up spare width; the Property (tree) column keeps the
    # width it is given. With both columns stretchable (the ttk default) every relayout is taken
    # out of the tree column, so dragging the separator to widen Property instead snapped it to a
    # sliver. Making value the sole stretcher, with minwidths so neither vanishes, means a drag
    # resizes only the dragged column. NOTE: this is a local stopgap of the same tree-column-resize
    # bug shared by all infrastructure ViewWin* panes; the general fix is owed as a separate PR to
    # master (see the XbrlModel plugin's ViewXbrlTaxonomyObject columns for the same approach).
    view.treeView.column("#0", width=140, minwidth=60, stretch=False, anchor="w")
    view.treeView.heading("#0", text="Property")
    view.treeView.column("value", width=600, minwidth=100, stretch=True, anchor="w")
    view.treeView.heading("value", text="Value")
    view.treeView["displaycolumns"] = ("value")
    view.view()

class ViewProperties(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super(ViewProperties, self).__init__(modelXbrl, tabWin, "Properties", True)
        self.openProperties = set()

    def view(self):
        self.viewProperties(None, "")

    def cleanPreviousNodes(self,parentNode):
        for previousNode in self.treeView.get_children(parentNode):
            self.cleanPreviousNodes(previousNode)
            text = self.treeView.item(previousNode,'text')
            if str(self.treeView.item(previousNode,'open')) in ('true','1'): self.openProperties.add(text)
            else: self.openProperties.discard(text)
            self.treeView.delete(previousNode)

    def viewProperties(self, modelObject, parentNode):
        try:
            self.cleanPreviousNodes(parentNode)
        except Exception:
            pass    # possible tkinter issues
        if modelObject is not None and hasattr(modelObject, "propertyView"):
            self.showProperties(modelObject.propertyView, parentNode, 1)

    def showProperties(self, properties, parentNode, id):
        for tuple in properties:
            if tuple:
                lenTuple = len(tuple)
                if 2 <= lenTuple <= 3:
                    strId = str(id)
                    node = self.treeView.insert(parentNode, "end", strId, text=tuple[0], tags=("odd" if id & 1 else "even",))
                    self.treeView.set(strId, "value", tuple[1])
                    id += 1;
                    if lenTuple == 3:
                        if tuple[0] in self.openProperties:
                            self.treeView.item(node,open=True)
                        id = self.showProperties(tuple[2], node, id)
        return id

    def viewModelObject(self, modelObject):
        self.viewProperties(modelObject, "")
