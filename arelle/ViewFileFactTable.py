'''
Created on Jan 24, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile, ModelDtsObject, XbrlConst, XmlUtil
from arelle.XbrlConst import conceptNameLabelRole
from arelle.ViewFile import CSV, HTML, XML, JSON
import datetime, re
from collections import defaultdict

stripXmlPattern = re.compile(r"<.*?>")

def viewFacts(modelXbrl, outfile, arcrole=None, linkrole=None, linkqname=None, arcqname=None, ignoreDims=False, showDimDefaults=False, labelrole=None, lang=None):
    if not arcrole: arcrole=XbrlConst.parentChild
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, outfile, arcrole, linkrole, linkqname, arcqname, ignoreDims, showDimDefaults, labelrole, lang)
    view.view(modelXbrl.modelDocument)
    view.close()
    
class ViewFacts(ViewFile.View):
    def __init__(self, modelXbrl, outfile, arcrole, linkrole, linkqname, arcqname, ignoreDims, showDimDefaults, labelrole, lang):
        super(ViewFacts, self).__init__(modelXbrl, outfile, "Fact Table", lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.ignoreDims = ignoreDims
        self.showDimDefaults = showDimDefaults
        self.labelrole = labelrole

    def view(self, modelDocument):
        relationshipSet = self.modelXbrl.relationshipSet(self.arcrole, self.linkrole, self.linkqname, self.arcqname)
        if relationshipSet:
            # sort URIs by definition
            linkroleUris = []
            for linkroleUri in relationshipSet.linkRoleUris:
                modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)
                if modelRoleTypes:
                    roledefinition = (modelRoleTypes[0].genLabel(lang=self.lang, strip=True) or modelRoleTypes[0].definition or linkroleUri)                    
                else:
                    roledefinition = linkroleUri
                linkroleUris.append((roledefinition, linkroleUri))
            linkroleUris.sort()
    
            for roledefinition, linkroleUri in linkroleUris:
                linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUri, self.linkqname, self.arcqname)
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.treeDepth(rootConcept, rootConcept, 2, self.arcrole, linkRelationshipSet, set())
        
        # set up facts
        self.conceptFacts = defaultdict(list)
        for fact in self.modelXbrl.facts:
            self.conceptFacts[fact.qname].append(fact)
        # sort contexts by period
        self.periodContexts = defaultdict(set)
        contextStartDatetimes = {}
        for context in self.modelXbrl.contexts.values():
            if self.type in (CSV, HTML):
                if self.ignoreDims:
                    if context.isForeverPeriod:
                        contextkey = datetime.datetime(datetime.MINYEAR,1,1)
                    else:
                        contextkey = context.endDatetime
                else:
                    if context.isForeverPeriod:
                        contextkey = "forever"
                    else:
                        contextkey = (context.endDatetime - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    values = []
                    dims = context.qnameDims
                    if len(dims) > 0:
                        for dimQname in sorted(dims.keys(), key=lambda d: str(d)):
                            dimvalue = dims[dimQname]
                            if dimvalue.isExplicit:
                                values.append(dimvalue.member.label(self.labelrole,lang=self.lang)
                                              if dimvalue.member is not None 
                                              else str(dimvalue.memberQname))
                            else:
                                values.append(XmlUtil.innerText(dimvalue.typedMember))
                                
                    nonDimensions = context.nonDimValues("segment") + context.nonDimValues("scenario")
                    if len(nonDimensions) > 0:
                        for element in sorted(nonDimensions, key=lambda e: e.localName):
                            values.append(XmlUtil.innerText(element))
    
                    if len(values) > 0:
        
                        contextkey += " - " + ', '.join(values)
            else:
                contextkey = context.id

            objectId = context.objectId()
            self.periodContexts[contextkey].add(objectId)
            if context.isStartEndPeriod:
                contextStartDatetimes[objectId] = context.startDatetime
        self.periodKeys = list(self.periodContexts.keys())
        self.periodKeys.sort()
        
        # set up treeView widget and tabbed pane
        heading = ["Concept"]
        columnHeadings = []
        self.contextColId = {}
        self.startdatetimeColId = {}
        self.numCols = 1
        for periodKey in self.periodKeys:
            columnHeadings.append(periodKey)
            for contextId in self.periodContexts[periodKey]:
                self.contextColId[contextId] = self.numCols
                if contextId in contextStartDatetimes:
                    self.startdatetimeColId[contextStartDatetimes[contextId]] = self.numCols
            self.numCols += 1

        for colHeading in columnHeadings:
            if self.ignoreDims:
                if colHeading.year == datetime.MINYEAR:
                    date = "forever"
                else:
                    date = (colHeading - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                heading.append(date)
            else:
                heading.append(colHeading)

                    
        self.addRow(heading, asHeader=True) # must do after determining tree depth

        if relationshipSet:
            # for each URI in definition order
            for roledefinition, linkroleUri in linkroleUris:
                attr = {"role": linkroleUri}
                self.addRow([roledefinition], treeIndent=0, colSpan=len(heading), 
                            xmlRowElementName="linkRole", xmlRowEltAttr=attr, xmlCol0skipElt=True)
                linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUri, self.linkqname, self.arcqname)
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.viewConcept(rootConcept, rootConcept, "", self.labelrole, 1, linkRelationshipSet, set())
    
        return True

    def treeDepth(self, concept, modelObject, indent, arcrole, relationshipSet, visited):
        if concept is None:
            return
        if indent > self.treeCols: self.treeCols = indent
        if concept not in visited:
            visited.add(concept)
            for modelRel in relationshipSet.fromModelObject(concept):
                nestedRelationshipSet = relationshipSet
                targetRole = modelRel.targetRole
                if targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(arcrole, targetRole)
                self.treeDepth(modelRel.toModelObject, modelRel, indent + 1, arcrole, nestedRelationshipSet, visited)
            visited.remove(concept)
            
    def viewConcept(self, concept, modelObject, labelPrefix, preferredLabel, n, relationshipSet, visited):
        # bad relationship could identify non-concept or be None
        if (not isinstance(concept, ModelDtsObject.ModelConcept) or 
            concept.substitutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
            return
        cols = ['' for i in range(self.numCols)]
        cols[0] = labelPrefix + concept.label(preferredLabel,lang=self.lang,linkroleHint=relationshipSet.linkrole)
        self.setRowFacts(cols,concept,preferredLabel)
        attr = {"concept": str(concept.qname)}
        self.addRow(cols, treeIndent=n, 
                    xmlRowElementName="facts", xmlRowEltAttr=attr, xmlCol0skipElt=True)
        if concept not in visited:
            visited.add(concept)
            for i, modelRel in enumerate(relationshipSet.fromModelObject(concept)):
                nestedRelationshipSet = relationshipSet
                targetRole = modelRel.targetRole
                if self.arcrole == XbrlConst.summationItem:
                    childPrefix = "({:0g}) ".format(modelRel.weight) # format without .0 on integer weights
                elif targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                    childPrefix = ""
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, targetRole, self.linkqname, self.arcqname)
                    childPrefix = "(via targetRole) "
                toConcept = modelRel.toModelObject
                if toConcept in visited:
                    childPrefix += "(loop)"
                labelrole = modelRel.preferredLabel
                if not labelrole or self.labelrole == conceptNameLabelRole: 
                    labelrole = self.labelrole
                self.viewConcept(toConcept, modelRel, childPrefix, labelrole, n + 1, nestedRelationshipSet, visited)
            visited.remove(concept)
            
    def setRowFacts(self, cols, concept, preferredLabel):
        for fact in self.conceptFacts[concept.qname]:
            try:
                colId = self.contextColId[fact.context.objectId()]
                # special case of start date, pick column corresponding
                if preferredLabel == XbrlConst.periodStartLabel:
                    date = fact.context.instantDatetime
                    if date:
                        if date in self.startdatetimeColId:
                            colId = self.startdatetimeColId[date]
                        else:
                            continue # not shown on this row (belongs on end period label row
                cols[colId] = fact.effectiveValue
                # cols[colId] = stripXmlPattern.sub(" ", fact.effectiveValue).replace("  "," ").strip()
            except AttributeError:  # not a fact or no concept
                pass