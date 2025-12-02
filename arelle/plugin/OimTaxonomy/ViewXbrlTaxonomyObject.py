'''
See COPYRIGHT.md for copyright information.
'''
from typing import ForwardRef, Union, get_origin, _AnnotatedAlias, _GenericAlias, ClassVar
from collections import defaultdict
from decimal import Decimal
from typing import GenericAlias
from arelle import ViewWinTree, XbrlConst
from arelle.FunctionFn import false
from arelle.ModelValue import qname
from arelle.PythonUtil import OrderedSet
from .XbrlCube import XbrlCube, XbrlPeriodConstraint
from .XbrlDimension import XbrlDomain
from .XbrlGroup import XbrlGroup
from .XbrlNetwork import XbrlNetwork
from .XbrlReport import XbrlReport, XbrlFactspace
from .XbrlObject import EMPTY_DICT, XbrlTaxonomyObject
from .XbrlConst import qnStdLabel


def viewXbrlTaxonomyObject(xbrlTxmyMdl, objClass, tabWin, header, additionalViews=None):
    xbrlTxmyMdl.modelManager.showStatus(_("viewing concepts"))
    view = ViewXbrlTxmyObj(xbrlTxmyMdl, objClass, tabWin, header)
    view.propNameTypes = []
    initialParentObjProp = True
    for propName, propType in objClass.propertyNameTypes():
        if initialParentObjProp:
            initialParentProp = False
            if isinstance(propType, str):
                continue
            elif get_origin(propType) is Union:
                if any((arg.__forward_arg__.startswith("Xbrl") if isinstance(arg,ForwardRef) else arg.__name__.startswith("Xbrl"))
                       for arg in propType.__args__):
                    continue
            elif propType.__name__.startswith("Xbrl"): # skip taxonomy alias type
                continue
        if not isinstance(propType, GenericAlias) or propName == "factDimensions": # set, dict, etc
            view.propNameTypes.append((propName, propType))
    # add label col if first col is name for Concepts pane
    if view.propNameTypes and view.propNameTypes[0][0] == "name":
        if objClass.__name__ in ("XbrlConcept", "XbrlFactspace"):
            view.propNameTypes.insert(0, ("label", str))
        else:
            view.propNameTypes[0] = ("name", view.propNameTypes[0][1])
    # check nested object types
    for i in range(len(view.propNameTypes),10):
        view.propNameTypes.append( (f"col{i+1}",str))
    view.colNames = tuple(propName for propName, _propType in view.propNameTypes[1:])
    view.treeView["columns"] = view.colNames
    firstCol = True
    for propName, propType in view.propNameTypes:
        colName = propName
        if firstCol:
            firstCol = False
            colName = "#0"
            w = 360
        elif isinstance(propType, (int,float,Decimal)):
            w = 50
        else:
            w = 120
        view.treeView.column(colName, width=w, anchor="w")
        view.treeView.heading(colName, text=propName)
    view.treeView["displaycolumns"] = view.colNames
    if objClass.__name__ == "XbrlReference":
        view.labelRole = None
    else:
        view.labelrole = qnStdLabel
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

    # languages menu
    menu = view.contextMenu()
    if objClass.__name__ != "XbrlConcept":
        view.menuAddExpandCollapse() # for tree view panes but not for Concept table pane
    view.menuAddClipboard()
    view.menuAddLangs()

    view.menuAddLabelRoles(usedLabelroles=
        (("1Name",XbrlConst.conceptNameLabelRole),
         ("2Standard Label", qnStdLabel)) +
        tuple((f"3{t}", t) for t in sorted(xbrlTxmyMdl.labelTypes) if t != qnStdLabel))
    view.menuAddNameStyle()
    view.menuAddViews(addClose=False, additionalViews=additionalViews, additionalViewMethod=viewXbrlTaxonomyObject)

class ViewXbrlTxmyObj(ViewWinTree.ViewTree):
    def __init__(self, xbrlTxmyMdl, objClass, tabWin, header):
        super(ViewXbrlTxmyObj, self).__init__(xbrlTxmyMdl, tabWin, header, True, None)
        self.xbrlTxmyMdl = xbrlTxmyMdl
        self.objClass = objClass

    def view(self):
        # sort by labels
        self.setColumnsSortable()
        self.tag_has = defaultdict(list)
        lbls = defaultdict(list)
        role = self.labelrole
        lang = self.lang
        self.clearTreeView()
        self.id = 1
        nodeNum = 0
        excludedNamespaces = XbrlConst.ixbrlAll.union(
            (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
             XbrlConst.xbrldt,
             XbrlConst.xhtml))
        for obj in self.xbrlTxmyMdl.filterNamedObjects(self.objClass, role, lang): # this is a yield generator
            if isinstance(obj, XbrlFactspace):
                self.viewProps("", nodeNum, obj, False)
                nodeNum += 1
                continue
            propName = self.propNameTypes[0][0]
            node = self.treeView.insert("", "end",
                                        f"_{self.id}_{obj.xbrlMdlObjIndex}",
                                        text=str(self.xbrlTxmyMdl.labelValue(obj.getProperty(propName, self.labelrole), self.labelrole, self.lang)),
                                        tags=("odd" if nodeNum & 1 else "even",))
            self.tag_has[f"_{obj.xbrlMdlObjIndex}"].append(node)
            self.id += 1
            nodeNum += 1
            for propName, _propType in self.propNameTypes[1:]:
                self.treeView.set(node, propName, str(obj.getProperty(propName)))
            if isinstance(obj, XbrlGroup):
                self.viewGroupContent(node, nodeNum, obj)
            elif isinstance(obj, XbrlCube):
                self.viewDims(node, nodeNum, obj)
            elif isinstance(obj, (XbrlNetwork, XbrlDomain)):
                self.viewRoots(node, nodeNum, obj)
            elif isinstance(obj, XbrlReport):
                self.viewFacts(node, nodeNum, obj)

    def viewProps(self, parentNode, nodeNum, obj, nestedObjs=True):
        propView = obj.propertyView
        node = self.treeView.insert(parentNode, "end",
                                    f"_{self.id}_{obj.xbrlMdlObjIndex}",
                                    text=propView[0][1],
                                    tags=("odd" if nodeNum & 1 else "even",))
        self.tag_has[f"_{obj.xbrlMdlObjIndex}"].append(node)
        nodeNum += 1
        self.id += 1
        for i, propViewEntry in enumerate(propView[1:]):
            if i >= len(self.colNames):
                print(f"i problem {i}")
            if len(propViewEntry) < 2:
                print(f"propViewEntry problem {propViewEntry} class {type(obj).__name__}")
            self.treeView.set(node, self.colNames[i], propViewEntry[1])
        # process nested objects
        if nestedObjs:
            for propName, propType in obj.propertyNameTypes():
                childObj = getattr(obj, propName, None)
                if isinstance(getattr(propType, "__origin__", None), type(Union)): # Optional[ ] type
                    if isinstance(propType.__args__[0], XbrlTaxonomyObject): # e.g. dateResolution object
                        childObj = getattr(obj, propName, None)
                        if childObj is not None:
                            self.viewProps(node, nodeNum, childObj)
                elif getattr(propType, "__origin__", None) in (set, OrderedSet) and issubclass(propType.__args__[0], XbrlTaxonomyObject):
                    if childObj is not None and len(childObj) > 0 and propName != "relationships":
                        for childObjObj in childObj:
                            self.viewProps(node, nodeNum, childObjObj)
        return node

    def viewGroupContent(self, parentNode, nodeNum, obj):
        # related content for the Group object are under tagged content
        for relatedObjQn in self.xbrlTxmyMdl.groupContents.get(obj.name, ()):
            relatedObj = self.xbrlTxmyMdl.namedObjects.get(relatedObjQn)
            if relatedObj is not None:
                node = self.viewProps(parentNode, nodeNum, relatedObj, nestedObjs=False)
                nodeNum += 1
                if isinstance(relatedObj, XbrlCube):
                    self.viewDims(node, nodeNum, relatedObj)
                elif isinstance(relatedObj, (XbrlNetwork, XbrlDomain)):
                    self.viewRoots(node, nodeNum, relatedObj)

    def viewDims(self, parentNode, nodeNum, obj):
        for cubeDim in obj.cubeDimensions:
            node = self.viewProps(parentNode, nodeNum, cubeDim)
            nodeNum += 1
            domName = getattr(cubeDim, "domainName", None)
            if domName:
                domObj = self.xbrlTxmyMdl.namedObjects.get(domName)
                if domObj is not None:
                    domNode = self.viewProps(node, nodeNum, domObj)
                    nodeNum += 1
                    self.viewRoots(domNode, nodeNum, domObj)

    def viewRoots(self, parentNode, nodeNum, obj):
        if not isinstance(obj, (XbrlDomain, XbrlNetwork)):
            return
        for qn in obj.relationshipRoots:
            rootObj = self.xbrlTxmyMdl.namedObjects.get(qn)
            if rootObj is not None:
                node = self.treeView.insert(parentNode, "end",
                                            f"_{self.id}_{rootObj.xbrlMdlObjIndex}",
                                            text=str(rootObj.getProperty("label", self.labelrole, self.lang, "")),
                                            tags=("odd" if nodeNum & 1 else "even",))
                self.id += 1
                nodeNum += 1
                for relObj in obj.relationshipsFrom.get(qn, ()):
                    self.viewRelationships(node, nodeNum, obj, relObj, set())

    def viewFacts(self, parentNode, nodeNum, obj):
        for fact in obj.facts.values():
            node = self.viewProps(parentNode, nodeNum, fact)
            nodeNum += 1

    def viewRelationships(self, parentNode, nodeNum, obj, relObj, visited):
        target = relObj.target
        qnObj = self.xbrlTxmyMdl.namedObjects.get(target)
        if qnObj is not None:
            loop = target in visited
            txt = self.xbrlTxmyMdl.labelValue(relObj.target, self.labelrole, self.lang)
            if loop:
                txt = "(loop) " + txt
            node = self.treeView.insert(parentNode, "end",
                                        f"_{self.id}_{qnObj.xbrlMdlObjIndex}",
                                        text=txt,
                                        tags=("odd" if nodeNum & 1 else "even",))
            self.id += 1
            nodeNum += 1
            if not loop:
                visited.add(target)
                for relTgtObj in obj.relationshipsFrom.get(relObj.target, ()):
                    self.viewRelationships(node, nodeNum, obj, relTgtObj, visited)
                visited.remove(target)

    def treeviewEnter(self, *args):
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args):
        self.blockSelectEvent = 1

    def treeviewSelect(self, event):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            #self.modelXbrl.viewModelObject(self.nodeToObjectId[self.treeView.selection()[0]])
            selection = self.treeView.selection()
            if selection is not None and len(selection)>0:
                self.xbrlTxmyMdl.viewTaxonomyObject(selection[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, txmyObj):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                items = self.tag_has.get(f"_{txmyObj.xbrlMdlObjIndex}")
                if items:
                    for item in items:
                        if self.treeView.exists(item):
                            self.treeView.see(item)
                            self.treeView.selection_set(item)
                            break
            except (AttributeError, KeyError, ValueError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1
