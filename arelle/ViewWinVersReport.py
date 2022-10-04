'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
import os
from arelle import ViewWinTree
from arelle.ModelDtsObject import ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelVersObject import ModelRelationshipSetChange, ModelInstanceAspectsChange

def viewVersReport(modelXbrl, tabWin):
    modelXbrl.modelManager.showStatus(_("viewing versioning report"))
    view = ViewVersReport(modelXbrl, tabWin)
    view.view()
    # pop up menu
    menu = view.contextMenu()
    menu.add_cascade(label=_("Expand"), underline=0, command=view.expand)
    menu.add_cascade(label=_("Collapse"), underline=0, command=view.collapse)
    # set up treeView widget and tabbed pane
    view.treeView.column("#0", width=300, anchor="w")
    view.treeView.heading("#0", text=_("Versioning Report"))
    view.menuAddClipboard()
    view.menuAddLangs()
    view.menuAddLabelRoles(includeConceptName=True,menulabel=_("Concept Label Role"))

    # sort URIs by definition
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')

class ViewVersReport(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin):
        super(ViewVersReport, self).__init__(modelXbrl, tabWin, "Versioning Report", True)

    def view(self):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6

        self.clearTreeView()

        versReport = self.modelXbrl.modelDocument
        # root node for tree view
        self.id = 1
        rootnode = self.treeView.insert("", "end", versReport.objectId(),
                    text=os.path.basename(self.modelXbrl.modelDocument.basename),
                    tags=("odd",))
        nsRenamingsNode = self.treeView.insert("", "end", "node_{0}".format(self.id),
                    text=_("namespace renamings"),
                    tags=("even",))
        self.id += 1
        srtfromURIs = sorted(versReport.namespaceRenameFrom)
        for i, fromURI in enumerate(srtfromURIs):
            nsRenaming = versReport.namespaceRenameFrom[fromURI]
            self.treeView.insert(nsRenamingsNode, "end", nsRenaming.objectId('ns'),
                        text=nsRenaming.viewText(),
                        tags=("even" if i & 1 else "odd",))

        roleChangesNode = self.treeView.insert("", "end", "node_{0}".format(self.id),
                    text=_("role changes"),
                    tags=("odd",))
        self.id += 1
        srtfromURIs = list(versReport.roleChanges.keys())
        srtfromURIs.sort()
        for i, fromRole in enumerate(srtfromURIs):
            roleChange = versReport.roleChanges[fromRole]
            self.treeView.insert(roleChangesNode, "end", roleChange.objectId('role'),
                        text=roleChange.viewText(),
                        tags=("odd" if i & 1 else "even",))

        assignmentsNode = self.treeView.insert("", "end", "node_{}".format(self.id),
                    text=_("assignments"),
                    tags=("even",))
        self.id += 1
        srtAssignmentIds = list(versReport.assignments.keys())
        srtAssignmentIds.sort()
        for i, assignmentId in enumerate(srtAssignmentIds):
            assignment = versReport.assignments[assignmentId]
            text = "{0}: {1} {2}".format(assignmentId,
                                         assignment.genLabel(lang=self.lang) or "",
                                         assignment.categoryQName)
            label = assignment.genLabel(lang=self.lang)
            text = (assignmentId + ": " + label) if label else assignmentId
            self.treeView.insert(assignmentsNode, "end", assignment.objectId(),
                                 text=text,
                                 tags=("even" if i & 1 else "odd",))

        actionsNode = self.treeView.insert("", "end", "node_{0}".format(self.id),
                    text=_("actions"),
                    tags=("odd",))
        self.id += 1
        srtActionIds = list(versReport.actions.keys())
        srtActionIds.sort()
        for i, actionId in enumerate(srtActionIds):
            action = versReport.actions[actionId]
            label = action.genLabel(lang=self.lang)
            text = (actionId + ": " + label) if label else actionId
            actionNode = self.treeView.insert(actionsNode, "end", action.objectId(), text=text,
                                              tags=("odd" if i & 1 else "even",))
            for j, event in enumerate(action.events):
                label = event.genLabel(lang=self.lang)
                text = (event.localName + ": " + label) if label else event.localName
                if isinstance(event, ModelRelationshipSetChange):
                    eventNode = self.treeView.insert(actionNode, "end", event.objectId(), text=text,
                                                     tags=("even" if i+j & 1 else "odd",))
                    k = i + j
                    for relationshipSet, name in ((event.fromRelationshipSet, "fromRelationshipSet"),
                                                  (event.toRelationshipSet, "toRelationshipSet")):
                        if relationshipSet is not None:
                            relSetNode = self.treeView.insert(eventNode, "end", relationshipSet.objectId(),
                                                              text=relationshipSet.localName,
                                                              tags=("odd" if k & 1 else "even",))
                            k += 1
                            l = k
                            for relationship in relationshipSet.relationships:
                                self.treeView.insert(relSetNode, "end", relationship.objectId(), text=relationship.localName,
                                                     tags=("odd" if l & 1 else "even",))
                                l += 1
                elif isinstance(event, ModelInstanceAspectsChange):
                    eventNode = self.treeView.insert(actionNode, "end", event.objectId(), text=text)
                    k = i + j
                    for aspects, name in ((event.fromAspects, "fromAspects"),
                                                  (event.toAspects, "toAspects")):
                        if aspects is not None:
                            k += 1
                            aspectsNode = self.treeView.insert(eventNode, "end", aspects.objectId(), text=aspects.localName,
                                                               tags=("even" if k & 1 else "odd",))
                            l = k
                            for aspect in aspects.aspects:
                                l += 1
                                aspectNode = self.treeView.insert(aspectsNode, "end", aspect.objectId(),
                                                                  text=aspect.localName + " " + aspect.elementAttributesStr,
                                                                  tags=("even" if l & 1 else "odd",))
                                m = l
                                for member in getattr(aspect, "relatedConcepts", getattr(aspect, "relatedPeriods", getattr(aspect, "relatedMeasures", []))):
                                    self.treeView.insert(aspectNode, "end", member.objectId(),
                                                         text=member.localName + " " + member.elementAttributesStr,
                                                         tags=("even" if m & 1 else "odd",))
                else:
                    self.treeView.insert(actionNode, "end", event.objectId(),
                                         text=text + " " + event.viewText(self.labelrole, self.lang),
                                         tags=("even" if i+j & 1 else "odd",))

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
                if isinstance(modelObject, ModelRelationship):
                    conceptId = modelObject.toModelObject.objectId()
                elif isinstance(modelObject, ModelFact):
                    conceptId = self.modelXbrl.qnameConcepts[modelObject.qname].objectId()
                else:
                    conceptId = modelObject.objectId()
                    '''
                items = self.treeView.tag_has(conceptId)
                    '''
                items = self.tag_has.get(conceptId)
                if items is not None and self.treeView.exists(items[0]):
                    self.treeView.see(items[0])
                    self.treeView.selection_set(items[0])
            except KeyError:
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1
