'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
from decimal import Decimal
from typing import GenericAlias
from arelle import ViewWinTree, XbrlConst
from arelle.FunctionFn import false
from .XbrlCube import XbrlCube
from .XbrlNetwork import XbrlNetwork
from .XbrlTaxonomyObject import XbrlTaxonomyObject

def viewXbrlTxmyObj(xbrlDts, objClass, objCollection, tabWin, header, lang=None, altTabWin=None):
    xbrlDts.modelManager.showStatus(_("viewing concepts"))
    view = ViewXbrlTxmyObj(xbrlDts, objClass, objCollection, tabWin, header, lang)
    view.propNameTypes = []
    initialParentObjProp = True
    for propName, propType in getattr(objClass, "__annotations__", {}).items():
        if initialParentObjProp:
            initialParentProp = False
            if isinstance(propType, str) or propType.__name__.startswith("Xbrl"): # skip taxonomy alias type
                continue
        if not isinstance(propType, GenericAlias): # set, dict, etc
            view.propNameTypes.append((propName, propType))
    view.treeView["columns"] = tuple(propName for propName, _propType in view.propNameTypes[1:])
    print(f"cols {view.treeView['columns']}")
    firstCol = True
    for propName, propType in view.propNameTypes:
        colName = propName
        if firstCol:
            firstCol = False
            colName = "#0"
        if isinstance(propType, (int,float,Decimal)):
            w = 50
        else:
            w = 120
        print(f"trace prop {propName}")
        view.treeView.column(colName, width=w, anchor="w")
        view.treeView.heading(colName, text=propName)
    view.treeView["displaycolumns"] = tuple(propName for propName, _propType in view.propNameTypes[1:])
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

    # languages menu
    menu = view.contextMenu()
    view.menuAddClipboard()
    view.menuAddLangs()
    view.menuAddLabelRoles()
    view.menuAddNameStyle()
    view.menuAddViews(addClose=False, tabWin=altTabWin)

class ViewXbrlTxmyObj(ViewWinTree.ViewTree):
    def __init__(self, xbrlDts, objClass, objCollection, tabWin, header, lang):
        super(ViewXbrlTxmyObj, self).__init__(xbrlDts, tabWin, header, True, lang)
        self.xbrlDts = xbrlDts
        self.objClass = objClass
        self.objCollection = objCollection

    def view(self):
        # sort by labels
        self.setColumnsSortable()
        lbls = defaultdict(list)
        role = self.labelrole
        lang = self.lang
        self.clearTreeView()
        nodeNum = 1
        excludedNamespaces = XbrlConst.ixbrlAll.union(
            (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
             XbrlConst.xbrldt,
             XbrlConst.xhtml))
        for obj in self.objCollection:
            node = self.treeView.insert("", "end",
                                        f"{self.objClass.__name__}_{obj.dtsObjectIndex}",
                                        text=str(getattr(obj, self.propNameTypes[0][0])),
                                        tags=("odd" if nodeNum & 1 else "even",))
            nodeNum += 1
            for propName, _propType in self.propNameTypes[1:]:
                self.treeView.set(node, propName, str(getattr(obj, propName, "")))
            if isinstance(obj, XbrlCube):
                self.viewDims(node, nodeNum, obj)
            elif isinstance(obj, XbrlNetwork):
                self.viewRoots(node, nodeNum, obj)

    def viewProps(self, parentNode, nodeNum, obj):
        propView = obj.propertyView
        node = self.treeView.insert(parentNode, "end",
                                    f"{type(obj).__name__}_{obj.dtsObjectIndex}",
                                    text=propView[0][1],
                                    tags=("odd" if nodeNum & 1 else "even",))
        print(f"treeview cols {self.treeView['columns']} len(propView) {len(propView)}")
        for i, propViewEntry in enumerate(propView[1:]):
            self.treeView.set(node, self.treeView["columns"][i], propViewEntry[1])
        return node

    def viewDims(self, parentNode, nodeNum, obj):
        for cubeDim in obj.cubeDimensions:
            node = self.viewProps(parentNode, nodeNum, cubeDim)
            nodeNum += 1            

    def viewRoots(self, parentNode, nodeNum, obj):
        for rootQn in getattr(obj, "roots", ()):
            rootObj = self.xbrlDts.taxonomyObjects.get(rootQn)
            if rootObj is not None:
                node = self.viewProps(parentNode, nodeNum, cubeDim)
                nodeNum += 1

    def treeviewEnter(self, *args):
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args):
        self.blockSelectEvent = 1

    def treeviewSelect(self, event):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            #self.modelXbrl.viewModelObject(self.nodeToObjectId[self.treeView.selection()[0]])
            self.modelXbrl.viewModelObject(self.treeView.selection()[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, txmyObj):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                if isinstance(txmyObj, XbrlTaxonomyObject):
                    node = f"{self.objClass.__name__}_{obj.dtsObjectIndex}"
                    if self.treeView.exists(node):
                        self.treeView.see(node)
                        self.treeView.selection_set(node)
            except (AttributeError, KeyError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1
