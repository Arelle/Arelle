'''
Created on Oct 6, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import os
from arelle import ViewWinTree, ModelDtsObject, XbrlConst, XmlUtil, Locale
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelFormulaObject import ModelFilter
from arelle.ViewUtil import viewReferences, groupRelationshipSet, groupRelationshipLabel

def viewRelationshipSet(modelXbrl, tabWin, arcrole, linkrole=None, linkqname=None, arcqname=None, lang=None, treeColHdr=None):
    arcroleName = groupRelationshipLabel(arcrole)
    relationshipSet = groupRelationshipSet(modelXbrl, arcrole, linkrole, linkqname, arcqname)
    if not relationshipSet:
        modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcroleName))
        return False
    modelXbrl.modelManager.showStatus(_("viewing relationships {0}").format(arcroleName))
    view = ViewRelationshipSet(modelXbrl, tabWin, arcrole, linkrole, linkqname, arcqname, lang, treeColHdr)
    view.view(firstTime=True, relationshipSet=relationshipSet)
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, '+')
    view.treeView.bind("<Enter>", view.treeviewEnter, '+')
    view.treeView.bind("<Leave>", view.treeviewLeave, '+')
    
    # pop up menu
    menu = view.contextMenu()
    view.menuAddExpandCollapse()
    view.menuAddClipboard()
    view.menuAddLangs()
    view.menuAddLabelRoles(includeConceptName=True)
    view.menuAddViews()

    
class ViewRelationshipSet(ViewWinTree.ViewTree):
    def __init__(self, modelXbrl, tabWin, arcrole, linkrole=None, linkqname=None, arcqname=None, lang=None, treeColHdr=None):
        if isinstance(arcrole, (list,tuple)):
            tabName = arcrole[0]
        else:
            tabName = XbrlConst.baseSetArcroleLabel(arcrole)[1:]
        super(ViewRelationshipSet, self).__init__(modelXbrl, tabWin, tabName, True, lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.treeColHdr = treeColHdr
        self.isResourceArcrole = False
        
    def view(self, firstTime=False, relationshipSet=None):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6
        # relationship set based on linkrole parameter, to determine applicable linkroles
        if relationshipSet is None:
            relationshipSet = groupRelationshipSet(self.modelXbrl, self.arcrole, self.linkrole, self.linkqname, self.arcqname)
        if not relationshipSet:
            self.modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(groupRelationshipLabel(self.arcrole)))
            return False
        
        if firstTime:
            self.showReferences = False
            # set up treeView widget and tabbed pane
            hdr = self.treeColHdr if self.treeColHdr else _("{0} Relationships").format(groupRelationshipLabel(self.arcrole))
            self.treeView.heading("#0", text=hdr)
            if self.arcrole == XbrlConst.parentChild: # extra columns
                self.treeView.column("#0", width=300, anchor="w")
                self.treeView["columns"] = ("type", "references")
                self.treeView.column("type", width=100, anchor="w", stretch=False)
                self.treeView.heading("type", text=_("Type"))
                self.treeView.column("references", width=200, anchor="w", stretch=False)
                self.treeView.heading("references", text=_("References"))
            elif self.arcrole == XbrlConst.summationItem: # extra columns
                self.treeView.column("#0", width=300, anchor="w")
                self.treeView["columns"] = ("weight", "balance")
                self.treeView.column("weight", width=48, anchor="w", stretch=False)
                self.treeView.heading("weight", text=_("Weight"))
                self.treeView.column("balance", width=70, anchor="w", stretch=False)
                self.treeView.heading("balance", text=_("Balance"))
            elif self.arcrole == "XBRL-dimensions":    # add columns for dimensional information
                self.treeView.column("#0", width=300, anchor="w")
                self.treeView["columns"] = ("arcrole", "contextElement", "closed", "usable")
                self.treeView.column("arcrole", width=100, anchor="w", stretch=False)
                self.treeView.heading("arcrole", text="Arcrole")
                self.treeView.column("contextElement", width=50, anchor="center", stretch=False)
                self.treeView.heading("contextElement", text="Context")
                self.treeView.column("closed", width=40, anchor="center", stretch=False)
                self.treeView.heading("closed", text="Closed")
                self.treeView.column("usable", width=40, anchor="center", stretch=False)
                self.treeView.heading("usable", text="Usable")
            elif self.arcrole == "Table-rendering":    # add columns for dimensional information
                self.treeView.column("#0", width=160, anchor="w")
                self.treeView["columns"] = ("axis", "abstract", "header", "priItem", "dims")
                self.treeView.column("axis", width=28, anchor="center", stretch=False)
                self.treeView.heading("axis", text="Axis")
                self.treeView.column("abstract", width=24, anchor="center", stretch=False)
                self.treeView.heading("abstract", text="Abs")
                self.treeView.column("header", width=160, anchor="w", stretch=False)
                self.treeView.heading("header", text="Header")
                self.treeView.column("priItem", width=100, anchor="w", stretch=False)
                self.treeView.heading("priItem", text="Primary Item")
                self.treeView.column("dims", width=150, anchor="w", stretch=False)
                self.treeView.heading("dims", text=_("Dimensions"))
            elif isinstance(self.arcrole, (list,tuple)) or XbrlConst.isResourceArcrole(self.arcrole):
                self.isResourceArcrole = True
                self.showReferences = isinstance(self.arcrole, _STR_BASE) and self.arcrole.endswith("-reference")
                self.treeView.column("#0", width=160, anchor="w")
                self.treeView["columns"] = ("arcrole", "resource", "resourcerole", "lang")
                self.treeView.column("arcrole", width=100, anchor="w", stretch=False)
                self.treeView.heading("arcrole", text="Arcrole")
                self.treeView.column("resource", width=60, anchor="w", stretch=False)
                self.treeView.heading("resource", text="Resource")
                self.treeView.column("resourcerole", width=100, anchor="w", stretch=False)
                self.treeView.heading("resourcerole", text="Resource Role")
                self.treeView.column("lang", width=36, anchor="w", stretch=False)
                self.treeView.heading("lang", text="Lang")
        self.id = 1
        for previousNode in self.treeView.get_children(""): 
            self.treeView.delete(previousNode)
        # sort URIs by definition
        linkroleUris = []
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
            if modelRoleTypes:
                roledefinition = (modelRoleTypes[0].definition or linkroleUri)
                roleId = modelRoleTypes[0].objectId(self.id)
            else:
                roledefinition = linkroleUri
                roleId = "node{0}".format(self.id)
            self.id += 1
            linkroleUris.append((roledefinition, linkroleUri, roleId))
        linkroleUris.sort()
        # for each URI in definition order
        for roledefinition, linkroleUri, roleId in linkroleUris:
            linknode = self.treeView.insert("", "end", roleId, text=roledefinition, tags=("ELR",))
            linkRelationshipSet = groupRelationshipSet(self.modelXbrl, self.arcrole, linkroleUri, self.linkqname, self.arcqname)
            for rootConcept in linkRelationshipSet.rootConcepts:
                self.viewConcept(rootConcept, rootConcept, "", self.labelrole, linknode, 1, linkRelationshipSet, set())
                self.tag_has[linkroleUri].append(linknode)


    def viewConcept(self, concept, modelObject, labelPrefix, preferredLabel, parentnode, n, relationshipSet, visited):
        if concept is None:
            return
        isRelation = isinstance(modelObject, ModelDtsObject.ModelRelationship)
        if isinstance(concept, ModelDtsObject.ModelConcept):
            text = labelPrefix + concept.label(preferredLabel,lang=self.lang,linkroleHint=relationshipSet.linkrole)
            if (self.arcrole in ("XBRL-dimensions", XbrlConst.hypercubeDimension) and
                concept.isTypedDimension and 
                concept.typedDomainElement is not None):
                text += " (typedDomain={0})".format(concept.typedDomainElement.qname)  
        elif self.arcrole == "Table-rendering":
            text = concept.localName
        elif isinstance(concept, ModelDtsObject.ModelResource):
            if self.showReferences:
                text = (concept.viewText() or concept.localName)
            else:
                text = (Locale.rtlString(concept.elementText.strip(), lang=concept.xmlLang) or concept.localName)
        else:   # just a resource
            text = concept.localName
        childnode = self.treeView.insert(parentnode, "end", modelObject.objectId(self.id), text=text, tags=("odd" if n & 1 else "even",))
        if self.arcrole == XbrlConst.parentChild: # extra columns
            self.treeView.set(childnode, "type", concept.niceType)
            self.treeView.set(childnode, "references", viewReferences(concept))
        elif self.arcrole == XbrlConst.summationItem:
            if isRelation:
                self.treeView.set(childnode, "weight", "{:0g} ".format(modelObject.weight))
            self.treeView.set(childnode, "balance", concept.balance)
        elif self.arcrole == "XBRL-dimensions" and isRelation: # extra columns
            relArcrole = modelObject.arcrole
            self.treeView.set(childnode, "arcrole", os.path.basename(relArcrole))
            if relArcrole in (XbrlConst.all, XbrlConst.notAll):
                self.treeView.set(childnode, "contextElement", modelObject.contextElement)
                self.treeView.set(childnode, "closed", modelObject.closed)
            elif relArcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                self.treeView.set(childnode, "usable", modelObject.usable)
        elif self.arcrole == "Table-rendering": # extra columns
            try:
                header = concept.header(lang=self.lang,strip=True,evaluate=False)
            except AttributeError:
                header = None # could be a filter
            if isRelation and header is None:
                header = "{0} {1}".format(os.path.basename(modelObject.arcrole), concept.xlinkLabel)
            self.treeView.set(childnode, "header", header)
            if concept.get("abstract") == "true":
                self.treeView.set(childnode, "abstract", '\u2713') # checkmark unicode character
            if isRelation:
                self.treeView.set(childnode, "axis", modelObject.axisDisposition)
                if isinstance(concept, (ModelEuAxisCoord,ModelRuleAxisNode)):
                    self.treeView.set(childnode, "priItem", concept.aspectValue(None, Aspect.CONCEPT))
                    self.treeView.set(childnode, "dims", ' '.join(("{0},{1}".format(dim, concept.aspectValue(None, dim)) 
                                                                   for dim in (concept.aspectValue(None, Aspect.DIMENSIONS, inherit=False) or []))))
        elif self.isResourceArcrole: # resource columns
            if isRelation:
                self.treeView.set(childnode, "arcrole", os.path.basename(modelObject.arcrole))
            if isinstance(concept, ModelDtsObject.ModelResource):
                self.treeView.set(childnode, "resource", concept.localName)
                self.treeView.set(childnode, "resourcerole", os.path.basename(concept.role or ''))
                self.treeView.set(childnode, "lang", concept.xmlLang)
        self.id += 1
        self.tag_has[modelObject.objectId()].append(childnode)
        if isRelation:
            self.tag_has[modelObject.toModelObject.objectId()].append(childnode)
        if concept not in visited:
            visited.add(concept)
            for modelRel in relationshipSet.fromModelObject(concept):
                nestedRelationshipSet = relationshipSet
                targetRole = modelRel.targetRole
                if self.arcrole == XbrlConst.summationItem:
                    childPrefix = "({:0g}) ".format(modelRel.weight) # format without .0 on integer weights
                elif targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                    childPrefix = ""
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, targetRole)
                    childPrefix = "(via targetRole) "
                toConcept = modelRel.toModelObject
                if toConcept in visited:
                    childPrefix += "(loop)"
                labelrole = modelRel.preferredLabel
                if not labelrole: labelrole = self.labelrole
                n += 1 # child has opposite row style of parent
                self.viewConcept(toConcept, modelRel, childPrefix, labelrole, childnode, n, nestedRelationshipSet, visited)
            visited.remove(concept)
            
    def getToolTip(self, tvRowId, tvColId):
        # override tool tip when appropriate
        if self.arcrole == "Table-rendering" and tvColId == "#0":
            try:
                modelObject = self.modelXbrl.modelObject(tvRowId) # this is a relationship object
                return modelObject.toModelObject.ordinateView
            except (AttributeError, KeyError):
                try: # rendering filter relationships
                    filterObj = modelObject.toModelObject
                    return "{0}: {1}\ncomplement: {2}\ncover: {3}\n{4}".format(
                            filterObj.localName, filterObj.viewExpression,
                            str(modelObject.isComplemented).lower(),
                            str(modelObject.isCovered).lower(),
                            '\n'.join("{0}: {1}".format(label, value) for label,value in filterObj.propertyView))
                except (AttributeError, KeyError):
                    pass
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
                if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                    linkroleId = self.tag_has.get(modelObject.linkrole)
                    if linkroleId: 
                        linkroleId = linkroleId[0]
                    else:
                        linkroleId = None
                else:
                    linkroleId = None
                # get concept of fact or toConcept of relationship, role obj if roleType
                conceptId = modelObject.viewConcept.objectId()
                items = self.tag_has.get(conceptId)
                if items:
                    for item in items:
                        if self.treeView.exists(item):
                            if linkroleId is None or self.hasAncestor(item, linkroleId):
                                self.treeView.see(item)
                                self.treeView.selection_set(item)
                                break
            except (AttributeError, KeyError):
                    self.treeView.selection_set(())
            self.blockViewModelObject -= 1

    def hasAncestor(self, node, ancestor):
        if node == ancestor:
            return True
        elif node:
            return self.hasAncestor(self.treeView.parent(node), ancestor)
        return False
    
from arelle.ModelRenderingObject import ModelEuAxisCoord, ModelRuleAxisNode
from arelle.ModelFormulaObject import Aspect
