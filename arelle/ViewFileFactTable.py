'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ViewFile, ModelDtsObject, XbrlConst, XmlUtil
from arelle.XbrlConst import conceptNameLabelRole, standardLabel, terseLabel, documentationLabel
from arelle.ViewFile import CSV, XLSX, HTML, XML, JSON
import datetime
import regex as re
from collections import defaultdict

stripXmlPattern = re.compile(r"<.*?>")

def viewFacts(modelXbrl, outfile, arcrole=None, linkrole=None, linkqname=None, arcqname=None, ignoreDims=False, showDimDefaults=False, labelrole=None, lang=None, cols=None):
    if not arcrole: arcrole=XbrlConst.parentChild
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFacts(modelXbrl, outfile, arcrole, linkrole, linkqname, arcqname, ignoreDims, showDimDefaults, labelrole, lang, cols)
    view.view(modelXbrl.modelDocument)
    view.close()

COL_WIDTHS = {
    "Concept": 70, # same as label
    "Facts": 24, # one column per fact period/dimension/unit
    "Label": 70, # preferred label
    "Name": 70,
    "LocalName":  40,
    "Namespace": 60,
    "ParentName": 70,
    "ParentLocalName":  40,
    "ParentNamespace": 60,
    "ID": 40,
    "Type": 32,
    "PeriodType": 16,
    "Balance": 16,
    "StandardLabel": 70,
    "TerseLabel": 70,
    "Documentation": 100,
    "LinkRole": 70,
    "LinkDefinition": 100,
    "PreferredLabelRole": 70,
    "Depth": 16,
    "ArcRole": 70,
    }

class ViewFacts(ViewFile.View):
    def __init__(self, modelXbrl, outfile, arcrole, linkrole, linkqname, arcqname, ignoreDims, showDimDefaults, labelrole, lang, cols):
        super(ViewFacts, self).__init__(modelXbrl, outfile, "Fact Table", lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.ignoreDims = ignoreDims
        self.showDimDefaults = showDimDefaults
        self.labelrole = labelrole
        self.cols = cols

    def view(self, modelDocument):
        if self.cols:
            if isinstance(self.cols,str): self.cols = self.cols.replace(',',' ').split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in COL_WIDTHS:
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedFactListColumn",
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
            if "Period" in self.cols:
                i = self.cols.index("Period")
                self.cols[i:i+1] = ["Start", "End/Instant"]
        else:
            self.cols = ["Concept", "Facts"]
        col0 = self.cols[0]
        try:
            colIdxFacts = self.cols.index("Facts")
        except ValueError:
            self.modelXbrl.error("arelle:factTableFactsColumn",
                                 _("A columns entry for Facts is required"),
                                 modelXbrl=self.modelXbrl)
            colIdxFacts = len(self.cols)
            self.cols.append("Facts")
        if col0 not in ("Concept", "Label", "Name", "LocalName"):
            self.modelXbrl.error("arelle:firstFactTableColumn",
                                 _("First column must be Concept, Label, Name or LocalName: %(col1)s"),
                                 modelXbrl=self.modelXbrl, col1=col0)
        self.isCol0Label = col0 in ("Concept", "Label")
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
        self.linkRoleDefintions = dict((linkroleUri,roledefinition) for roledefinition, linkroleUri in linkroleUris)

        # allocate facts to table structure for US-GAAP-style filings
        if not self.modelXbrl.hasTableIndexing:
            from arelle import TableStructure
            TableStructure.evaluateTableIndex(self.modelXbrl, lang=self.lang)

        # set up facts
        self.conceptFacts = defaultdict(list)
        for fact in self.modelXbrl.facts:
            self.conceptFacts[fact.qname].append(fact)
        # sort contexts by period
        self.periodContexts = defaultdict(set)
        contextStartDatetimes = {}
        for context in self.modelXbrl.contexts.values():
            if self.type in (CSV, XLSX, HTML):
                if context is None or context.endDatetime is None:
                    contextkey = "missing period"
                elif self.ignoreDims:
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
        heading = self.cols[0:colIdxFacts]
        columnHeadings = []
        self.contextColId = {}
        self.startdatetimeColId = {}
        self.numCols = len(heading)
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

        heading += self.cols[colIdxFacts+1:]
        self.numCols = len(heading)

        self.setColWidths([COL_WIDTHS[col] if col in COL_WIDTHS else COL_WIDTHS["Facts"]
                           for col in enumerate(heading)])
        self.setColWrapText([True for col in heading])
        self.addRow(heading, asHeader=True) # must do after determining tree depth

        if relationshipSet:
            # for each URI in definition order
            for roledefinition, linkroleUri in linkroleUris:
                attr = {"role": linkroleUri,
                        "definition": roledefinition}
                self.addRow([roledefinition], treeIndent=0, colSpan=len(heading),
                            xmlRowElementName="linkRole", xmlRowEltAttr=attr, xmlCol0skipElt=True)
                linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUri, self.linkqname, self.arcqname)
                # set up concepts which apply to linkrole for us-gaap style filings
                self.conceptFacts.clear()
                if linkroleUri and self.modelXbrl.roleTypes[linkroleUri] and hasattr(self.modelXbrl.roleTypes[linkroleUri][0], "_tableFacts"):
                    for fact in self.modelXbrl.roleTypes[linkroleUri][0]._tableFacts:
                        self.conceptFacts[fact.qname].append(fact)
                else:
                    for fact in self.modelXbrl.facts:
                        if linkRelationshipSet.fromModelObject(fact.concept) or linkRelationshipSet.toModelObject(fact.concept):
                            self.conceptFacts[fact.qname].append(fact)
                # view root and descendant
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.viewConcept(rootConcept, linkroleUri, "", self.labelrole, 1, linkRelationshipSet, set())

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
        i = 0
        for col in self.cols:
            if col == "Facts":
                self.setRowFacts(cols,concept,preferredLabel)
                i = self.numCols - (len(self.cols) - i - 1) # skip to next concept property column
            else:
                if col in ("Concept", "Label"):
                    cols[i] = labelPrefix + concept.label(preferredLabel,lang=self.lang,linkroleHint=relationshipSet.linkrole)
                elif col == "Name":
                    cols[i] = concept.qname
                elif col == "LocalName":
                    cols[i] = concept.name
                elif col == "Namespace":
                    cols[i] = concept.qname.namespaceURI
                elif col == "ID":
                    cols[i] = concept.id
                elif col == "Substitution Group":
                    cols[i] = concept.substitutionGroupQname
                elif col == "Type":
                    cols[i] = concept.typeQname
                elif col == "Period Type":
                    cols[i] = concept.periodType
                elif col == "Balance":
                    cols[i] = concept.balance
                elif col == "StandardLabel":
                    cols[i] = concept.label(preferredLabel=standardLabel,lang=self.lang,linkroleHint=relationshipSet.linkrole)
                elif col == "TerseLabel":
                    cols[i] = concept.label(preferredLabel=terseLabel,lang=self.lang,linkroleHint=relationshipSet.linkrole)
                elif col == "Documentation":
                    cols[i] = concept.label(preferredLabel=documentationLabel, fallbackToQname=False, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole)
                elif col == "PreferredLabelRole":
                    cols[i] = preferredLabel
                elif col == "LinkRole":
                    if isinstance(modelObject, str):
                        cols[i] = modelObject
                    elif isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = modelObject.linkrole
                elif col == "LinkDefinition":
                    if isinstance(modelObject, str):
                        cols[i] = self.linkRoleDefintions[modelObject]
                    elif isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = self.linkRoleDefintions[modelObject.linkrole]
                elif col == "ArcRole":
                    if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = modelObject.arcrole
                elif col == "Depth":
                    cols[i] = n
                elif col == "ParentName":
                    if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = modelObject.fromModelObject.qname
                elif col == "ParentLocalName":
                    if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = modelObject.fromModelObject.name
                elif col == "ParentNamespace":
                    if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                        cols[i] = modelObject.fromModelObject.qname.namespaceURI
                i += 1

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
