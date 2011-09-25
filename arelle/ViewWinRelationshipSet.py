'''
Created on Oct 6, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import os
from arelle import (ViewWinTree, ModelDtsObject, XbrlConst, XmlUtil)
from arelle.ViewUtil import viewReferences

def viewRelationshipSet(modelXbrl, tabWin, arcrole, linkrole=None, linkqname=None, arcqname=None, lang=None, treeColHdr=None):
    relationshipSet =  modelXbrl.relationshipSet(arcrole, linkrole, linkqname, arcqname)
    if relationshipSet is None or len(relationshipSet.modelRelationships) == 0:
        modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcrole))
        return False
    modelXbrl.modelManager.showStatus(_("viewing relationships {0}").format(os.path.basename(arcrole)))
    view = ViewRelationshipSet(modelXbrl, tabWin, arcrole, linkrole, linkqname, arcqname, lang, treeColHdr)
    view.view(firstTime=True)
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
        super().__init__(modelXbrl, tabWin, XbrlConst.baseSetArcroleLabel(arcrole)[1:], True, lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.treeColHdr = treeColHdr
        
    def view(self, firstTime=False):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6
        # relationship set based on linkrole parameter, to determine applicable linkroles
        relationshipSet = self.modelXbrl.relationshipSet(self.arcrole, self.linkrole, self.linkqname, self.arcqname)
        if not relationshipSet:
            self.modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(self.arcrole))
            return False
        
        if firstTime:
            # set up treeView widget and tabbed pane
            hdr = self.treeColHdr if self.treeColHdr else _("{0} Relationships").format(XbrlConst.baseSetArcroleLabel(self.arcrole)[1:])
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
                self.treeView.column("axis", width=50, anchor="center", stretch=False)
                self.treeView.heading("axis", text="Axis")
                self.treeView.column("abstract", width=24, anchor="center", stretch=False)
                self.treeView.heading("abstract", text="Abs")
                self.treeView.column("header", width=160, anchor="w", stretch=False)
                self.treeView.heading("header", text="Header")
                self.treeView.column("priItem", width=100, anchor="w", stretch=False)
                self.treeView.heading("priItem", text="Primary Item")
                self.treeView.column("dims", width=150, anchor="w", stretch=False)
                self.treeView.heading("dims", text=_("Dimensions"))
        self.id = 1
        for previousNode in self.treeView.get_children(""): 
            self.treeView.delete(previousNode)
        # sort URIs by definition
        linkroleUris = []
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
            if modelRoleTypes:
                roledefinition = modelRoleTypes[0].definition
                if not roledefinition:
                    roledefinition = linkroleUri                    
                roleId = modelRoleTypes[0].objectId(self.id)
            else:
                roledefinition = linkroleUri
                roleId = "node{0}".format(self.id)
            self.id += 1
            linkroleUris.append((roledefinition, linkroleUri, roleId))
        linkroleUris.sort()
        # for each URI in definition order
        for linkroleUriTuple in linkroleUris:
            linknode = self.treeView.insert("", "end", linkroleUriTuple[2], text=linkroleUriTuple[0], tags=("ELR",))
            linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUriTuple[1], self.linkqname, self.arcqname)
            for rootConcept in linkRelationshipSet.rootConcepts:
                self.viewConcept(rootConcept, rootConcept, "", self.labelrole, linknode, 1, linkRelationshipSet, set())
                self.tag_has[linkroleUriTuple[1]].append(linknode)


    def viewConcept(self, concept, modelObject, labelPrefix, preferredLabel, parentnode, n, relationshipSet, visited):
        if concept is None:
            return
        isRelation = isinstance(modelObject, ModelDtsObject.ModelRelationship)
        if isinstance(concept, ModelDtsObject.ModelConcept):
            text = labelPrefix + concept.label(preferredLabel,lang=self.lang)
            if (self.arcrole in ("XBRL-dimensions", XbrlConst.hypercubeDimension) and
                concept.isTypedDimension and 
                concept.typedDomainElement is not None):
                text += " (typedDomain={0})".format(concept.typedDomainElement.qname)  
        elif self.arcrole == "Table-rendering":
            text = concept.localName
        elif isinstance(concept, ModelDtsObject.ModelResource):
            text = concept.text
            if text is None:
                text = concept.localName
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
            header = concept.genLabel(lang=self.lang,strip=True)
            if isRelation and header is None:
                header = "{0} {1}".format(os.path.basename(modelObject.arcrole), concept.xlinkLabel)
            self.treeView.set(childnode, "header", header)
            if concept.get("abstract") == "true":
                self.treeView.set(childnode, "abstract", '\u2713') # checkmark unicode character
            if isRelation:
                self.treeView.set(childnode, "axis", modelObject.get("axisType"))
                if isinstance(concept, (ModelAxisCoord,ModelExplicitAxisMember)):
                    self.treeView.set(childnode, "priItem", concept.primaryItemQname)
                    self.treeView.set(childnode, "dims", ' '.join(("{0},{1}".format(dim[0],dim[1]) for dim in concept.explicitDims)))
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
    
from arelle.ModelRenderingObject import ModelAxisCoord, ModelExplicitAxisMember
