'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
from arelle import ViewWinTree, ModelDtsObject, XbrlConst, XmlUtil, Locale

def viewRoleTypes(modelXbrl, tabWin, isArcrole=False, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing arcrole types") if isArcrole else _("viewing role types"))
    view = ViewRoleTypes(modelXbrl,
                         tabWin,
                         "Arcrole Types" if isArcrole else "Role Types",
                         isArcrole,
                         lang)
    view.view(firstTime=True)
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

    # pop up menu
    menu = view.contextMenu()
    view.menuAddClipboard()
    view.menuAddLangs()
    view.menuAddLabelRoles(includeConceptName=True)
    view.menuAddViews()


class ViewRoleTypes(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin, header, isArcrole, lang=None):
        super(ViewRoleTypes, self).__init__(modelXbrl, tabWin, header, True, lang)
        self.isArcrole = isArcrole

    def view(self, firstTime=False):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6

        roletypes = self.modelXbrl.arcroleTypes if self.isArcrole else self.modelXbrl.roleTypes
        if not roletypes:
            return False # nothing to display

        if firstTime:
            # set up treeView widget and tabbed pane
            hdr = _("Arcrole Types") if self.isArcrole else _("Role Types")
            self.treeView.heading("#0", text=hdr)
            self.treeView.column("#0", width=300, anchor="w")
            if self.isArcrole:
                self.treeView["columns"] = ("definition", "cyclesAllowed", "usedOn")
            else:
                self.treeView["columns"] = ("definition", "usedOn")
            self.treeView.column("definition", width=300, anchor="w", stretch=True)
            self.treeView.heading("definition", text=_("Definition"))
            if self.isArcrole:
                self.treeView.column("cyclesAllowed", width=60, anchor="w", stretch=False)
                self.treeView.heading("cyclesAllowed", text=_("Cycles Allowed"))
            self.treeView.column("usedOn", width=200, anchor="w", stretch=False)
            self.treeView.heading("usedOn", text=_("Used On"))
            self.setColumnsSortable()
        self.id = 1
        self.clearTreeView()
        # sort URIs by definition
        nodeNum = 1
        if roletypes:
            for roleUri in sorted(roletypes.keys()):
                for modelRoleType in roletypes[roleUri]:
                    roleId = modelRoleType.objectId(self.id)
                    node = self.treeView.insert("", "end", modelRoleType.objectId(self.id), text=roleUri, tags=("odd" if nodeNum & 1 else "even",))
                    nodeNum += 1
                    self.treeView.set(node, "definition", modelRoleType.genLabel(lang=self.lang, strip=True) or modelRoleType.definition or '')
                    if self.isArcrole:
                        self.treeView.set(node, "cyclesAllowed", modelRoleType.cyclesAllowed)
                    self.treeView.set(node, "usedOn", ', '.join(str(usedOn)
                                                               for usedOn in modelRoleType.usedOns))

    def getToolTip(self, tvRowId, tvColId):
        # override tool tip when appropriate
        return None

    def treeviewEnter(self, *args):
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args):
        self.blockSelectEvent = 1

    def treeviewSelect(self, *args):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            self.modelXbrl.viewModelObject(self.treeView.selection()[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, modelObject):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            try:
                # check if modelObject is a relationship in given linkrole
                if isinstance(modelObject, ModelDtsObject.ModelRoleType):
                    roleId = modelObject.objectId()
                else:
                    roleId = None
                # get concept of fact or toConcept of relationship, role obj if roleType
                node = roleId
                if self.treeView.exists(node):
                    self.treeView.see(node)
                    self.treeView.selection_set(node)
            except (AttributeError, KeyError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1
