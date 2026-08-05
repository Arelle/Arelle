"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from arelle import ModelDtsObject, XbrlConst, XmlUtil, ViewFile
from arelle.ModelDtsObject import ModelRelationship
from arelle.ViewFile import CSV, XML, JSON
from arelle.ViewUtil import viewReferences
from arelle.XbrlConst import conceptNameLabelRole, documentationLabel, widerNarrower
from arelle.ModelRenderingObject import DefnMdlRuleDefinitionNode
from arelle.ModelFormulaObject import Aspect
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelObject import ModelObject
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelRelationshipSet import ModelRelationshipSet
    from arelle.ModelValue import QName
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewRelationshipSet(
        modelXbrl: ModelXbrl,
        outfile: str | FileNamedStringIO | None,
        header: str,
        arcrole: str | tuple[str, ...],
        linkrole: str | None = None,
        linkqname: QName | None = None,
        arcqname: QName | None = None,
        labelrole: str | None = None,
        lang: str | None = None,
        cols: list[str] | str | None = None,
) -> None:
    arcroles = (arcrole,) if isinstance(arcrole, str) else arcrole
    arcMessage = (os.path.basename(role) for role in arcroles)
    modelXbrl.modelManager.showStatus(_("viewing relationships {0}").format(", ".join(arcMessage)))
    view = ViewRelationshipSet(modelXbrl, outfile, header, labelrole, lang, cols)
    view.view(arcrole, linkrole, linkqname, arcqname)
    view.close()


COL_WIDTHS = {
    "Presentation Relationships": 80, "Pref. Label": 16, "Type": 16, "References":120,
    "Calculation Relationships": 80, "Weight": 16, "Balance": 16,
    "Dimensions Relationships": 80, "Arcrole": 32, "CntxElt": 12, "Closed": 8, "Usable": 8,
    "Resource Relationships": 80, "Arcrole": 32, "Resource": 50, "ResourceRole": 32, "Language": 20,
    "Table Relationships": 80, "Axis": 28, "Abs": 16, "Mrg": 16, "Header": 50, "Primary Item": 30, "Dimensions": 50,
    "Wider-Narrower": 80, "Wider": 32,
    "Name": 40, "Namespace": 60, "LocalName": 40, "Documentation": 80,
}


def hasCalcArcrole(arcroles: str | tuple[str, ...] | list[str] | tuple[str | tuple[str, ...], ...]) -> bool:
    if isinstance(arcroles, (tuple, list)):
        return any(hasCalcArcrole(arcrole) for arcrole in arcroles)
    return arcroles in XbrlConst.summationItems


class ViewRelationshipSet(ViewFile.View):
    def __init__(
            self,
            modelXbrl: ModelXbrl,
            outfile: str | FileNamedStringIO | None,
            header: str,
            labelrole: str | None,
            lang: str | None,
            cols: list[str] | str | None,
    ) -> None:
        super(ViewRelationshipSet, self).__init__(modelXbrl, outfile, header, lang)
        self.labelrole = labelrole
        self.isResourceArcrole = False
        self.cols = cols

    def view(
            self,
            arcrole: str | tuple[str, ...] | list[str],
            linkrole: str | None = None,
            linkqname: QName | None = None,
            arcqname: QName | None = None,
    ) -> None:
        # determine relationships indent depth for dimensions linkbases
        # set up treeView widget and tabbed pane
        if arcrole == XbrlConst.parentChild: # extra columns
            heading = ["Presentation Relationships", "Pref. Label", "Type", "References"]
        elif hasCalcArcrole(arcrole):    # add columns for calculation relationships
            heading = ["Calculation Relationships", "Weight", "Balance"]
        elif arcrole == "XBRL-dimensions":    # add columns for dimensional information
            heading = ["Dimensions Relationships", "Arcrole", "CntxElt", "Closed", "Usable"]
        elif arcrole == "Table-rendering":
            heading = ["Table Relationships", "Axis", "Abs", "Mrg", "Header", "Primary Item", "Dimensions"]
        elif arcrole == XbrlConst.widerNarrower:
            heading = ["Wider-Narrower", "Wider"]
        elif isinstance(arcrole, (list, tuple)) or XbrlConst.isResourceArcrole(arcrole):
            self.isResourceArcrole = True
            self.showReferences = isinstance(arcrole, str) and arcrole.endswith("-reference")
            heading = ["Resource Relationships", "Arcrole", "Resource", "ResourceRole", "Language"]
        else:
            heading = [os.path.basename(arcrole).title() + " Relationships"]

        if self.cols:
            if isinstance(self.cols, str):
                self.cols = self.cols.replace(",", " ").split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Name", "LocalName", "Namespace", "Documentation", "References"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedRelationshipSetColumn",  # type: ignore[union-attr]
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=",".join(unrecognizedCols))
                for col in unrecognizedCols:
                    self.cols.remove(col)
            heading += self.cols
        # relationship set based on linkrole parameter, to determine applicable linkroles
        relationshipSet = self.modelXbrl.relationshipSet(arcrole, linkrole, linkqname, arcqname)  # type: ignore[arg-type,union-attr]

        self.arcrole = arcrole
        self.maxNumDims = 1

        if relationshipSet:
            # sort URIs by definition
            linkroleUris: list[tuple[str, str]] = []
            for linkroleUri in relationshipSet.linkRoleUris:
                modelRoleTypes = self.modelXbrl.roleTypes.get(linkroleUri)  # type: ignore[union-attr]
                if modelRoleTypes:
                    roledefinition = modelRoleTypes[0].genLabel(lang=self.lang, strip=True) or modelRoleTypes[0].definition or linkroleUri
                else:
                    roledefinition = linkroleUri
                linkroleUris.append((roledefinition, linkroleUri))
            linkroleUris.sort()

            for roledefinition, linkroleUri in linkroleUris:
                linkRelationshipSet = self.modelXbrl.relationshipSet(arcrole, linkroleUri, linkqname, arcqname)  # type: ignore[arg-type,union-attr]
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.treeDepth(rootConcept, rootConcept, 2, arcrole, linkRelationshipSet, set())  # type: ignore[arg-type]

        # avoid use of lastColSpan, html and excel do not use multiple cols for dimensions for now
        # if "Dimensions" == heading[-1]:
        #    lastColSpan = self.maxNumDims
        # else:
        lastColSpan = None

        self.addRow(heading, asHeader=True, lastColSpan=lastColSpan) # must do after determining tree depth
        self.setColWidths([COL_WIDTHS.get(hdg, 80 if hdg.endswith("  Relationships") else 8) for hdg in heading])

        if relationshipSet:
            # for each URI in definition order
            for roledefinition, linkroleUri in linkroleUris:
                attr = {"role": linkroleUri, "definition": roledefinition}
                self.addRow([roledefinition], treeIndent=0, colSpan=len(heading),
                            xmlRowElementName="linkRole", xmlRowEltAttr=attr, xmlCol0skipElt=True)
                linkRelationshipSet = self.modelXbrl.relationshipSet(arcrole, linkroleUri, linkqname, arcqname)  # type: ignore[arg-type,union-attr]
                for rootConcept in linkRelationshipSet.rootConcepts:
                    self.viewConcept(rootConcept, rootConcept, "", self.labelrole, 1, arcrole, linkRelationshipSet, set())  # type: ignore[arg-type]

    def treeDepth(
            self,
            concept: ModelObject | None,
            modelObject: ModelObject | None,
            indent: int,
            arcrole: str | tuple[str, ...],
            relationshipSet: ModelRelationshipSet,
            visited: set[ModelObject],
    ) -> None:
        if concept is None:
            return
        if indent > self.treeCols: self.treeCols = indent
        if concept not in visited:
            visited.add(concept)
            childRelationshipSet = relationshipSet
            if isinstance(modelObject, ModelRelationship):
                if arcrole == "XBRL-dimensions":
                    childRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.consecutiveArcrole.get(modelObject.arcrole, "XBRL-dimensions"),  # type: ignore[arg-type,union-attr]
                                                                          modelObject.linkrole)
                elif self.arcrole == "Table-rendering" and isinstance(concept, DefnMdlRuleDefinitionNode):
                    numDims = len(concept.aspectValue(None, Aspect.DIMENSIONS, inherit=False) or ()) * 2
                    if numDims > self.maxNumDims: self.maxNumDims = numDims
            for modelRel in childRelationshipSet.fromModelObject(concept):
                targetRole = modelRel.targetRole
                if targetRole is None or len(targetRole) == 0:
                    nestedRelationshipSet = relationshipSet
                else:
                    nestedRelationshipSet = self.modelXbrl.relationshipSet(childRelationshipSet.arcrole, targetRole)  # type: ignore[union-attr]
                self.treeDepth(modelRel.toModelObject, modelRel, indent + 1, arcrole, nestedRelationshipSet, visited)
            visited.remove(concept)

    def viewConcept(
            self,
            concept: ModelObject | None,
            modelObject: ModelRelationship | None,
            labelPrefix: str,
            preferredLabel: str | None,
            indent: int,
            arcrole: str | tuple[str, ...],
            relationshipSet: ModelRelationshipSet,
            visited: set[ModelObject],
    ) -> None:
        try:
            if concept is None:
                return
            isRelation = isinstance(modelObject, ModelRelationship)
            childRelationshipSet = relationshipSet
            text: str
            attr: dict[str, str]
            xmlRowElementName: str
            if isinstance(concept, ModelDtsObject.ModelConcept):
                text = labelPrefix + concept.label(preferredLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole)  # type: ignore[arg-type,operator]
                if (self.arcrole in ("XBRL-dimensions", XbrlConst.hypercubeDimension) and
                    concept.isTypedDimension and
                    concept.typedDomainElement is not None):
                    text += " (typedDomain={0})".format(concept.typedDomainElement.qname)
                xmlRowElementName = "concept"
                attr = {"name": str(concept.qname)}
                if preferredLabel != XbrlConst.conceptNameLabelRole:
                    attr["label"] = text
            elif self.arcrole == "Table-rendering":
                text = concept.localName
                xmlRowElementName = "element"
                attr = {"label": concept.xlinkLabel}
            elif isinstance(concept, ModelDtsObject.ModelResource):
                if self.showReferences:
                    text = (concept.viewText().strip() or concept.localName)
                    attr = {"text": text,
                            "innerXml": XmlUtil.xmlstring(concept, stripXmlns=True, prettyPrint=False, contentsOnly=True)}
                else:
                    text = (concept.textValue.strip() or concept.localName)
                    attr = {"text": text}
                xmlRowElementName = "resource"
            else:   # just a resource
                text = concept.localName
                xmlRowElementName = text
                attr = {}
            cols: list[str | None] = [text]
            if arcrole == "XBRL-dimensions":
                if isRelation:
                    relArcrole = modelObject.arcrole  # type: ignore[union-attr]
                    cols.append(os.path.basename(relArcrole))  # type: ignore[arg-type]
                    if relArcrole in (XbrlConst.all, XbrlConst.notAll):
                        cols.append(modelObject.contextElement)  # type: ignore[union-attr]
                        cols.append(modelObject.closed)  # type: ignore[union-attr]
                    else:
                        cols.append(None)
                        cols.append(None)
                    if relArcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember):
                        cols.append(modelObject.usable)  # type: ignore[union-attr]
                    else:
                        cols.append(None)
                    childRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.consecutiveArcrole.get(relArcrole, "XBRL-dimensions"),  # type: ignore[arg-type,union-attr]
                                                                        modelObject.consecutiveLinkrole)  # type: ignore[union-attr]
                else:
                    cols.append(None)
                    cols.append(None)
                    cols.append(None)
                    cols.append(None)
            if self.arcrole == XbrlConst.parentChild: # extra columns
                if isRelation:
                    preferredLabel = modelObject.preferredLabel  # type: ignore[union-attr]
                    if preferredLabel and preferredLabel.startswith("http://"):
                        preferredLabel = os.path.basename(preferredLabel)
                else:
                    preferredLabel = None
                cols.append(preferredLabel)
                cols.append(concept.niceType)  # type: ignore[attr-defined]
                cols.append(viewReferences(concept))  # type: ignore[arg-type]
            elif hasCalcArcrole(arcrole):
                if isRelation:
                    cols.append("{:0g} ".format(modelObject.weight))  # type: ignore[str-format,union-attr]
                else:
                    cols.append("") # no weight on roots
                cols.append(concept.balance)
            elif self.isResourceArcrole: # resource columns
                if isRelation:
                    cols.append(modelObject.arcrole)  # type: ignore[union-attr]
                else:
                    cols.append("") # no weight on roots
                if isinstance(concept, ModelDtsObject.ModelResource):
                    cols.append(concept.localName)
                    cols.append(concept.role or "")
                    cols.append(concept.xmlLang)
            elif self.arcrole == "Table-rendering":
                header: str | None
                try:
                    header = concept.header(lang=self.lang,strip=True,evaluate=False)  # type: ignore[attr-defined]
                except AttributeError:
                    header = None # could be a filter
                if isRelation:
                    cols.append(modelObject.axis)  # type: ignore[union-attr]
                else:
                    cols.append("")
                if isRelation and header is None:
                    header = "{0} {1}".format(os.path.basename(modelObject.arcrole), concept.xlinkLabel)  # type: ignore[arg-type,union-attr]
                if concept.get("abstract") == "true":
                    cols.append("\u2713")
                else:
                    cols.append("")
                if concept.get("merge") == "true":
                    cols.append("\u2713")
                else:
                    cols.append("")
                cols.append(header)
                if isRelation and isinstance(concept, DefnMdlRuleDefinitionNode):
                    cols.append(concept.aspectValue(None, Aspect.CONCEPT))
                    if self.type in (CSV, XML, JSON): # separate dimension fields
                        for dim in (concept.aspectValue(None, Aspect.DIMENSIONS, inherit=False) or ()):
                            cols.append(dim)
                            cols.append(concept.aspectValue(None, dim))
                    else: # combined dimension fields
                        cols.append(" ".join(("{0},{1}".format(dim, concept.aspectValue(None, dim))
                                              for dim in (concept.aspectValue(None, Aspect.DIMENSIONS, inherit=False) or ()))))
                else:
                    cols.append("")
            elif self.arcrole == widerNarrower:
                if isRelation:
                    otherWider = [modelRel.fromModelObject
                                  for modelRel in childRelationshipSet.toModelObject(concept)
                                  if modelRel.fromModelObject != modelObject.fromModelObject]  # type: ignore[union-attr]
                    cols.append(", ".join(w.label(preferredLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole) for w in otherWider))  # type: ignore[union-attr]
                else:
                    cols.append("")
            if self.cols:
                for col in self.cols:
                    if col == "Name":
                        cols.append((concept.qname or concept.prefixedName))  # type: ignore[arg-type]
                    elif col == "LocalName":
                        cols.append(concept.qname.localName)
                    elif col == "Namespace":
                        cols.append(concept.qname.namespaceURI)
                    elif col == "Documentation":
                        cols.append(concept.label(documentationLabel, lang=self.lang, linkroleHint=relationshipSet.linkrole, fallbackToQname=False))  # type: ignore[attr-defined]
                    elif col == "References":
                        cols.append(viewReferences(concept))  # type: ignore[arg-type]
            self.addRow(cols, treeIndent=indent, xmlRowElementName=xmlRowElementName, xmlRowEltAttr=attr, xmlCol0skipElt=True, arcRole=self.arcrole)  # type: ignore[arg-type]
            if concept not in visited:
                visited.add(concept)
                for modelRel in childRelationshipSet.fromModelObject(concept):
                    nestedRelationshipSet = relationshipSet
                    targetRole = modelRel.targetRole
                    childPrefix: str
                    if hasCalcArcrole(arcrole):
                        childPrefix = "({:+0g}) ".format(modelRel.weight)  # type: ignore[str-format] # format without .0 on integer weights
                    elif targetRole is None or len(targetRole) == 0:
                        childPrefix = ""
                    else:
                        nestedRelationshipSet = self.modelXbrl.relationshipSet(childRelationshipSet.arcrole, targetRole)  # type: ignore[union-attr]
                        childPrefix = "(via targetRole) "
                    toConcept = modelRel.toModelObject
                    if toConcept in visited:
                        childPrefix += "(loop) "
                    labelrole = modelRel.preferredLabel
                    if not labelrole or self.labelrole == conceptNameLabelRole:
                        labelrole = self.labelrole
                    self.viewConcept(toConcept, modelRel, childPrefix, labelrole, indent + 1, arcrole, nestedRelationshipSet, visited)
                visited.remove(concept)
        except AttributeError:  #  bad relationship
            return
