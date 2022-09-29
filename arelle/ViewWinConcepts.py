'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ViewWinTree, XbrlConst
from arelle.ModelDtsObject import ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from collections import defaultdict

def viewConcepts(modelXbrl, tabWin, header, lang=None, altTabWin=None):
    modelXbrl.modelManager.showStatus(_("viewing concepts"))
    view = ViewConcepts(modelXbrl, tabWin, header, lang)
    view.treeView["columns"] = ("conceptname", "id", "abstr", "subsGrp", "type", "periodType", "balance", "facets")
    view.treeView.column("#0", width=250, anchor="w")
    view.treeView.heading("#0", text="Label")
    view.treeView.column("conceptname", width=250, anchor="w", stretch=False)
    view.treeView.heading("conceptname", text="Name")
    view.treeView.column("id", width=250, anchor="w", stretch=False)
    view.treeView.heading("id", text="ID")
    view.treeView.column("abstr", width=50, anchor="center", stretch=False)
    view.treeView.heading("abstr", text="Abstract")
    view.treeView.column("subsGrp", width=290, anchor="w", stretch=False)
    view.treeView.heading("subsGrp", text="Subs Grp")
    view.treeView.column("type", width=200, anchor="w", stretch=False)
    view.treeView.heading("type", text="Type")
    view.treeView.column("periodType", width=80, anchor="w", stretch=False)
    view.treeView.heading("periodType", text="Period Type")
    view.treeView.column("balance", width=70, anchor="w", stretch=False)
    view.treeView.heading("balance", text="Balance")
    view.treeView.column("facets", width=200, anchor="w", stretch=False)
    view.treeView.heading("facets", text="Facets")
    view.treeView["displaycolumns"] = ("conceptname", "id", "abstr", "subsGrp", "type", "periodType", "balance", "facets")
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

class ViewConcepts(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin, header, lang):
        super(ViewConcepts, self).__init__(modelXbrl, tabWin, header, True, lang)

    def view(self):
        # sort by labels
        self.setColumnsSortable()
        lbls = defaultdict(list)
        role = self.labelrole
        lang = self.lang
        nameIsPrefixed = self.nameIsPrefixed
        for concept in set(self.modelXbrl.qnameConcepts.values()): # may be twice if unqualified, with and without namespace
            lbls[concept.label(role,lang=lang)].append(concept.objectId())
        srtLbls = sorted(lbls.keys())
        '''
        self.nodeToObjectId = {}
        self.objectIdToNode = {}
        '''
        self.clearTreeView()
        nodeNum = 1
        excludedNamespaces = XbrlConst.ixbrlAll.union(
            (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl,
             XbrlConst.xbrldt,
             XbrlConst.xhtml))
        for label in srtLbls:
            for objectId in lbls[label]:
                concept = self.modelXbrl.modelObject(objectId)
                if concept.modelDocument.targetNamespace not in excludedNamespaces:
                    '''
                    node = "node{0}".format(nodeNum)
                    objectId = concept.objectId()
                    label = concept.label(lang=self.lang)
                    self.nodeToObjectId[node] = objectId
                    self.objectIdToNode[objectId] = node
                    if self.treeView.exists(node):
                        self.treeView.item(node, text=label)
                    else:
                        node = self.treeView.insert("", "end", node, text=label)
                    '''
                    node = self.treeView.insert("", "end",
                                                concept.objectId(),
                                                text=concept.label(role,lang=lang,linkroleHint=XbrlConst.defaultLinkRole),
                                                tags=("odd" if nodeNum & 1 else "even",))
                    nodeNum += 1
                    self.treeView.set(node, "conceptname", concept.qname if nameIsPrefixed else concept.name)
                    self.treeView.set(node, "id", concept.id)
                    self.treeView.set(node, "abstr", concept.abstract)
                    self.treeView.set(node, "subsGrp", concept.substitutionGroupQname)
                    self.treeView.set(node, "type", concept.typeQname)
                    if concept.periodType:
                        self.treeView.set(node, "periodType", concept.periodType)
                    if concept.balance:
                        self.treeView.set(node, "balance", concept.balance)
                    facets = concept.facets
                    if facets:
                        self.treeView.set(node, "facets",
                            "\n".join("{0}={1}".format(
                                   name,
                                   sorted(value.keys()) if isinstance(value,dict) else value
                                   ) for name,value in sorted(facets.items()))
                            )

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

    def viewModelObject(self, modelObject):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                if isinstance(modelObject, ModelRelationship):
                    conceptId = modelObject.toModelObject.objectId()
                elif isinstance(modelObject, ModelFact):
                    conceptId = self.modelXbrl.qnameConcepts[modelObject.qname].objectId()
                else:
                    conceptId = modelObject.objectId()
                #node = self.objectIdToNode[conceptId]
                node = conceptId
                if self.treeView.exists(node):
                    self.treeView.see(node)
                    self.treeView.selection_set(node)
            except (AttributeError, KeyError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1
