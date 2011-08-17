'''
Created on Oct 6, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelObject, XbrlConst, ViewCsv
from arelle.ModelDtsObject import ModelRelationship
import os

def viewRelationshipSet(modelXbrl, csvfile, header, arcrole, linkrole=None, linkqname=None, arcqname=None, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing relationships {0}").format(os.path.basename(arcrole)))
    view = ViewRelationshipSet(modelXbrl, csvfile, header, lang)
    view.view(arcrole, linkrole, linkqname, arcqname)
    view.close()
    
class ViewRelationshipSet(ViewCsv.View):
    def __init__(self, modelXbrl, csvfile, header, lang):
        super().__init__(modelXbrl, csvfile, header, lang)
        
    def view(self, arcrole, linkrole=None, linkqname=None, arcqname=None):
        # relationship set based on linkrole parameter, to determine applicable linkroles
        relationshipSet = self.modelXbrl.relationshipSet(arcrole, linkrole, linkqname, arcqname)
        if relationshipSet is None or len(relationshipSet.modelRelationships) == 0:
            self.modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(arcrole))
            return
        # sort URIs by definition
        linkroleUris = []
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
            if modelRoleTypes and len(modelRoleTypes) > 0:
                roledefinition = modelRoleTypes[0].definition
                if roledefinition is None or roledefinition == "":
                    roledefinition = linkroleUri                    
            else:
                roledefinition = linkroleUri
            linkroleUris.append((roledefinition, linkroleUri))
        linkroleUris.sort()
        # determine relationships indent depth for dimensions linkbases
        # set up treeView widget and tabbed pane
        heading = ["Relationships"]
        if arcrole == "XBRL-dimensions":    # add columns for dimensional information
            self.treeCols = 0
            for roledefinition, linkroleUri in linkroleUris:
                linkRelationshipSet = self.modelXbrl.relationshipSet(arcrole, linkroleUri, linkqname, arcqname)
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.treeDepth(rootConcept, rootConcept, 1, arcrole, linkRelationshipSet, set())
            for i in range(self.treeCols):
                heading.append(None)
            heading.extend(["Arcrole","CntxElt","Closed","Usable"])
        self.write(heading)
        # root node for tree view
        self.write([os.path.basename(arcrole)])
        # for each URI in definition order
        for roledefinition, linkroleUri in linkroleUris:
            self.write([roledefinition])
            linkRelationshipSet = self.modelXbrl.relationshipSet(arcrole, linkroleUri, linkqname, arcqname)
            for rootConcept in linkRelationshipSet.rootConcepts:
                self.viewConcept(rootConcept, rootConcept, "", None, [None], arcrole, linkRelationshipSet, set())

    def treeDepth(self, concept, modelObject, indentedCol, arcrole, relationshipSet, visited):
        if concept is None:
            return
        if indentedCol > self.treeCols: self.treeCols = indentedCol
        if concept not in visited:
            visited.add(concept)
            for modelRel in relationshipSet.fromModelObject(concept):
                nestedRelationshipSet = relationshipSet
                targetRole = modelRel.targetRole
                if targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(arcrole, targetRole)
                self.treeDepth(modelRel.toModelObject, modelRel, indentedCol + 1, arcrole, nestedRelationshipSet, visited)
            visited.remove(concept)
            
    def viewConcept(self, concept, modelObject, labelPrefix, preferredLabel, indent, arcrole, relationshipSet, visited):
        if concept is None:
            return
        isRelation = isinstance(modelObject, ModelRelationship)
        cols = indent + [labelPrefix + concept.label(preferredLabel,lang=self.lang)]
        if arcrole == "XBRL-dimensions" and isRelation: # extra columns
            for i in range(self.treeCols - len(indent)):
                cols.append(None)
            relArcrole = modelObject.arcrole
            cols.append( os.path.basename( relArcrole ) )
            if relArcrole in (XbrlConst.all, XbrlConst.notAll):
                cols.append( modelObject.contextElement )
                cols.append( modelObject.closed )
            else:
                cols.append(None)
                cols.append(None)
            if relArcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                cols.append( modelObject.usable  )
        self.write(cols)
        if concept not in visited:
            visited.add(concept)
            for modelRel in relationshipSet.fromModelObject(concept):
                nestedRelationshipSet = relationshipSet
                targetRole = modelRel.targetRole
                if arcrole == XbrlConst.summationItem:
                    childPrefix = "({:0g}) ".format(modelRel.weight) # format without .0 on integer weights
                elif targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                    childPrefix = ""
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(arcrole, targetRole)
                    childPrefix = "(via targetRole) "
                toConcept = modelRel.toModelObject
                if toConcept in visited:
                    childPrefix += "(loop) "
                self.viewConcept(toConcept, modelRel, childPrefix, modelRel.preferredLabel, indent + [None], arcrole, nestedRelationshipSet, visited)
            visited.remove(concept)