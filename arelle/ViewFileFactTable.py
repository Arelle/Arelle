"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING

import regex as re

from arelle import ViewFile, XbrlConst, XmlUtil
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle.XbrlConst import conceptNameLabelRole, standardLabel, terseLabel, documentationLabel
from arelle.ViewFile import CSV, XLSX, HTML, TABULAR_VIEW_TYPES
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelRelationshipSet import ModelRelationshipSet
    from arelle.ModelValue import QName
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText

stripXmlPattern = re.compile(r"<.*?>")


def viewFacts(
        modelXbrl: ModelXbrl,
        outfile: str | FileNamedStringIO | None,
        arcrole: str | tuple[str, ...] | None = None,
        linkrole: str | None = None,
        linkqname: QName | None = None,
        arcqname: QName | None = None,
        ignoreDims: bool = False,
        showDimDefaults: bool = False,
        labelrole: str | None = None,
        lang: str | None = None,
        cols: list[str] | str | None = None,
) -> None:
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
    cols: list[str] | None

    def __init__(
            self,
            modelXbrl: ModelXbrl,
            outfile: str | FileNamedStringIO | None,
            arcrole: str | tuple[str, ...],
            linkrole: str | None,
            linkqname: QName | None,
            arcqname: QName | None,
            ignoreDims: bool,
            showDimDefaults: bool,
            labelrole: str | None,
            lang: str | None,
            cols: list[str] | str | None,
    ) -> None:
        super(ViewFacts, self).__init__(modelXbrl, outfile, "Fact Table", lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname
        self.ignoreDims = ignoreDims
        self.showDimDefaults = showDimDefaults
        self.labelrole = labelrole
        if isinstance(cols, str):
            self.cols = cols.replace(",", " ").split()
        else:
            self.cols = cols

    def view(self, modelDocument: ModelDocument | None) -> bool:
        if self.cols:
            unrecognizedCols = []
            for col in self.cols:
                if col not in COL_WIDTHS:
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedFactListColumn",  # type: ignore[union-attr]
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=",".join(unrecognizedCols))
            if "Period" in self.cols:
                i = self.cols.index("Period")
                self.cols[i:i + 1] = ["Start", "End/Instant"]
        else:
            self.cols = ["Concept", "Facts"]
        col0 = self.cols[0]
        try:
            colIdxFacts = self.cols.index("Facts")
        except ValueError:
            self.modelXbrl.error("arelle:factTableFactsColumn",  # type: ignore[union-attr]
                                 _("A columns entry for Facts is required"),
                                 modelXbrl=self.modelXbrl)
            colIdxFacts = len(self.cols)
            self.cols.append("Facts")
        if col0 not in ("Concept", "Label", "Name", "LocalName"):
            self.modelXbrl.error("arelle:firstFactTableColumn",  # type: ignore[union-attr]
                                 _("First column must be Concept, Label, Name or LocalName: %(col1)s"),
                                 modelXbrl=self.modelXbrl, col1=col0)
        self.isCol0Label = col0 in ("Concept", "Label")
        relationshipSet = self.modelXbrl.relationshipSet(self.arcrole, self.linkrole, self.linkqname, self.arcqname)  # type: ignore[union-attr]
        linkroleUris: list[tuple[str, str]] = []
        if relationshipSet:
            # sort URIs by definition
            for linkroleUri in relationshipSet.linkRoleUris:
                modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)  # type: ignore[union-attr]
                if modelRoleTypes:
                    roledefinition = (modelRoleTypes[0].genLabel(lang=self.lang, strip=True) or modelRoleTypes[0].definition or linkroleUri)
                else:
                    roledefinition = linkroleUri
                linkroleUris.append((roledefinition, linkroleUri))
            linkroleUris.sort()

            for roledefinition, linkroleUri in linkroleUris:
                linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUri, self.linkqname, self.arcqname)  # type: ignore[union-attr]
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.treeDepth(rootConcept, rootConcept, 2, self.arcrole, linkRelationshipSet, set())  # type: ignore[arg-type]
        self.linkRoleDefintions = dict((linkroleUri, roledefinition) for roledefinition, linkroleUri in linkroleUris)

        # allocate facts to table structure for US-GAAP-style filings
        if not self.modelXbrl.hasTableIndexing:  # type: ignore[union-attr]
            from arelle import TableStructure
            TableStructure.evaluateTableIndex(self.modelXbrl, lang=self.lang)  # type: ignore[arg-type]

        # set up facts
        self.conceptFacts = defaultdict(list)
        for fact in self.modelXbrl.facts:  # type: ignore[union-attr]
            self.conceptFacts[fact.qname].append(fact)
        # sort contexts by period
        self.periodContexts: defaultdict[str | datetime.datetime | None, set[str]] = defaultdict(set)
        contextStartDatetimes: dict[str, datetime.datetime] = {}
        for context in self.modelXbrl.contexts.values():  # type: ignore[union-attr]
            contextkey: str | datetime.datetime | None
            if self.type in (CSV, XLSX, HTML):
                if context is None or context.endDatetime is None:
                    contextkey = "missing period"
                elif self.ignoreDims:
                    if context.isForeverPeriod:
                        contextkey = datetime.datetime(datetime.MINYEAR, 1, 1)
                    else:
                        contextkey = context.endDatetime
                else:
                    if context.isForeverPeriod:
                        contextkey = "forever"
                    else:
                        contextkey = (context.endDatetime - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

                    values: list[str] = []
                    dims = context.qnameDims
                    if len(dims) > 0:
                        for dimQname in sorted(dims.keys(), key=lambda d: str(d)):
                            dimvalue = dims[dimQname]
                            if dimvalue.isExplicit:
                                values.append(dimvalue.member.label(self.labelrole, lang=self.lang)  # type: ignore[arg-type]
                                              if dimvalue.member is not None
                                              else str(dimvalue.memberQname))
                            else:
                                values.append(XmlUtil.innerText(dimvalue.typedMember))  # type: ignore[arg-type]

                    nonDimensions = context.nonDimValues("segment") + context.nonDimValues("scenario")  # type: ignore[operator]
                    if len(nonDimensions) > 0:
                        for element in sorted(nonDimensions, key=lambda e: e.localName):
                            values.append(XmlUtil.innerText(element))

                    if len(values) > 0:

                        contextkey += " - " + ", ".join(values)
            else:
                contextkey = context.id

            objectId = context.objectId()
            self.periodContexts[contextkey].add(objectId)
            if context.isStartEndPeriod:
                contextStartDatetimes[objectId] = context.startDatetime  # type: ignore[assignment]
        self.periodKeys = list(self.periodContexts.keys())
        self.periodKeys.sort()

        # set up treeView widget and tabbed pane
        heading: list[str] = self.cols[0:colIdxFacts]
        columnHeadings: list[str | datetime.datetime | None] = []
        self.contextColId: dict[str, int] = {}
        self.startdatetimeColId: dict[datetime.datetime, int] = {}
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
                if colHeading.year == datetime.MINYEAR:  # type: ignore[union-attr]
                    date = "forever"
                else:
                    date = (colHeading - datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # type: ignore[union-attr, operator]
                heading.append(date)
            else:
                heading.append(colHeading)  # type: ignore[arg-type]

        heading += self.cols[colIdxFacts + 1:]
        self.numCols = len(heading)

        self.setColWidths([COL_WIDTHS[col] if col in COL_WIDTHS else COL_WIDTHS["Facts"]
                           for col in heading])
        self.setColWrapText([True for _ in heading])
        self.addRow(heading, asHeader=True) # must do after determining tree depth

        if relationshipSet:
            # for each URI in definition order
            for roledefinition, linkroleUri in linkroleUris:
                attr = {"role": linkroleUri,
                        "definition": roledefinition}
                self.addRow([roledefinition], treeIndent=0, colSpan=len(heading),
                            xmlRowElementName="linkRole", xmlRowEltAttr=attr, xmlCol0skipElt=True)
                linkRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, linkroleUri, self.linkqname, self.arcqname)  # type: ignore[union-attr]
                # set up concepts which apply to linkrole for us-gaap style filings
                self.conceptFacts.clear()
                if linkroleUri and self.modelXbrl.roleTypes[linkroleUri] and hasattr(self.modelXbrl.roleTypes[linkroleUri][0], "_tableFacts"):  # type: ignore[union-attr]
                    for fact in self.modelXbrl.roleTypes[linkroleUri][0]._tableFacts:  # type: ignore[union-attr]
                        self.conceptFacts[fact.qname].append(fact)
                else:
                    for fact in self.modelXbrl.facts:  # type: ignore[union-attr]
                        if linkRelationshipSet.fromModelObject(fact.concept) or linkRelationshipSet.toModelObject(fact.concept):  # type: ignore[arg-type]
                            self.conceptFacts[fact.qname].append(fact)
                # view root and descendant
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.viewConcept(rootConcept, linkroleUri, "", self.labelrole, 1, linkRelationshipSet, set())  # type: ignore[arg-type]
        return True

    def treeDepth(
            self,
            concept: ModelConcept | None,
            modelObject: ModelConcept | ModelRelationship | None,
            indent: int,
            arcrole: str | tuple[str, ...],
            relationshipSet: ModelRelationshipSet,
            visited: set[ModelConcept],
    ) -> None:
        if concept is None:
            return
        if indent > self.treeCols: self.treeCols = indent
        if concept not in visited:
            visited.add(concept)
            for modelRel in relationshipSet.fromModelObject(concept):
                nestedRelationshipSet = relationshipSet
                targetRole: str | tuple[str, ...] | None = modelRel.targetRole
                if targetRole is None or len(targetRole) == 0:
                    targetRole = relationshipSet.linkrole
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(arcrole, targetRole)  # type: ignore[union-attr]
                self.treeDepth(modelRel.toModelObject, modelRel, indent + 1, arcrole, nestedRelationshipSet, visited)  # type: ignore[arg-type]
            visited.remove(concept)

    def viewConcept(
            self,
            concept: ModelConcept,
            modelObject: ModelConcept | ModelRelationship | str | None,
            labelPrefix: str,
            preferredLabel: str | None,
            n: int,
            relationshipSet: ModelRelationshipSet,
            visited: set[ModelConcept],
    ) -> None:
        # bad relationship could identify non-concept or be None
        if (not isinstance(concept, ModelConcept) or
            concept.substitutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
            return
        cols: list[str | int | QName | None] = ["" for _ in range(self.numCols)]
        i = 0
        for col in self.cols:  # type: ignore[union-attr]
            if col == "Facts":
                self.setRowFacts(cols, concept, preferredLabel)
                i = self.numCols - (len(self.cols) - i - 1)  # type: ignore[arg-type] # skip to next concept property column
            else:
                if col in ("Concept", "Label"):
                    cols[i] = labelPrefix + concept.label(preferredLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[operator, arg-type]
                elif col == "Name":
                    cols[i] = concept.qname
                elif col == "LocalName":
                    cols[i] = concept.name
                elif col == "Namespace":
                    cols[i] = concept.qname.namespaceURI  # type: ignore[union-attr]
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
                    cols[i] = concept.label(preferredLabel=standardLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[arg-type]
                elif col == "TerseLabel":
                    cols[i] = concept.label(preferredLabel=terseLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[arg-type]
                elif col == "Documentation":
                    cols[i] = concept.label(preferredLabel=documentationLabel, fallbackToQname=False, lang=self.lang, strip=True, linkroleHint=XbrlConst.defaultLinkRole)
                elif col == "PreferredLabelRole":
                    cols[i] = preferredLabel
                elif col == "LinkRole":
                    if isinstance(modelObject, str):
                        cols[i] = modelObject
                    elif isinstance(modelObject, ModelRelationship):
                        cols[i] = modelObject.linkrole
                elif col == "LinkDefinition":
                    if isinstance(modelObject, str):
                        cols[i] = self.linkRoleDefintions[modelObject]
                    elif isinstance(modelObject, ModelRelationship):
                        cols[i] = self.linkRoleDefintions[modelObject.linkrole]  # type: ignore[index]
                elif col == "ArcRole":
                    if isinstance(modelObject, ModelRelationship):
                        cols[i] = modelObject.arcrole
                elif col == "Depth":
                    cols[i] = n
                elif col == "ParentName":
                    if isinstance(modelObject, ModelRelationship):
                        cols[i] = modelObject.fromModelObject.qname  # type: ignore[union-attr]
                elif col == "ParentLocalName":
                    if isinstance(modelObject, ModelRelationship):
                        cols[i] = modelObject.fromModelObject.name  # type: ignore[union-attr]
                elif col == "ParentNamespace":
                    if isinstance(modelObject, ModelRelationship):
                        cols[i] = modelObject.fromModelObject.qname.namespaceURI  # type: ignore[union-attr]
                i += 1

        attr = {"concept": str(concept.qname)}
        self.addRow(cols, treeIndent=n,
                    xmlRowElementName="facts", xmlRowEltAttr=attr, xmlCol0skipElt=True)
        if concept not in visited:
            visited.add(concept)
            for i, modelRel in enumerate(relationshipSet.fromModelObject(concept)):
                nestedRelationshipSet = relationshipSet
                targetRole: str | tuple[str, ...] | None = modelRel.targetRole
                if self.arcrole in XbrlConst.summationItems:
                    childPrefix = "({:0g}) ".format(modelRel.weight)  # type: ignore[str-format]  # format without .0 on integer weights
                elif targetRole is None or len(targetRole) == 0:
                    childPrefix = ""
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(self.arcrole, targetRole, self.linkqname, self.arcqname)  # type: ignore[union-attr]
                    childPrefix = "(via targetRole) "
                toConcept = modelRel.toModelObject
                if toConcept in visited:
                    childPrefix += "(loop)"
                labelrole = modelRel.preferredLabel
                if not labelrole or self.labelrole == conceptNameLabelRole:
                    labelrole = self.labelrole
                self.viewConcept(toConcept, modelRel, childPrefix, labelrole, n + 1, nestedRelationshipSet, visited)  # type: ignore[arg-type]
            visited.remove(concept)

    def setRowFacts(self, cols: list[str | int | QName | None], concept: ModelConcept, preferredLabel: str | None) -> None:
        for fact in self.conceptFacts[concept.qname]:
            try:
                colId = self.contextColId[fact.context.objectId()]  # type: ignore[union-attr]
                # special case of start date, pick column corresponding
                if self.type in TABULAR_VIEW_TYPES and preferredLabel == XbrlConst.periodStartLabel:
                    date = fact.context.instantDatetime  # type: ignore[union-attr]
                    if date:
                        if date in self.startdatetimeColId:
                            colId = self.startdatetimeColId[date]
                        else:
                            continue # not shown on this row (belongs on end period label row
                cols[colId] = fact.effectiveValue
            except AttributeError:  # not a fact or no concept
                pass
