"""
See XbrlModel/COPYRIGHT.md for copyright information.

## Overview

The saveOIMFacts plugin saves an OIM Taxonomy (XbrlModel) fact set from Inline XBRL or other XBRL
documents. It can alternatively save an xBRL-JSON report (see the `--oimJSON` option below).

## Key Features

- Preserves Inline source value mapping, scaling and transformation.
- Output is written as JSON.

## Usage Instructions

### Command Line Usage

- **Single-Instance Mode**:
  Save a file in single-instance mode by specifying the file path and extension:
  ```bash
  python arelleCmdLine.py --plugins saveOIMFacts --file filing-documents.zip --SaveOIMFactspace example.json
  ```

- **Test Case Operation**:
  Save an OIM file alongside each validated test-case variation, named by appending the given suffix to
  the variation instance's file name:
  ```bash
  python arelleCmdLine.py --plugins saveOIMFacts --file testcases-index.xml --saveTestcaseOIM -savedOim.json
  ```

- **Deduplicate facts**
  Deduplication does not make sense for inline XBRL source documents as it would block saving of
  the inline value sources for the duplicate entries.

- **Text block options**
  Default is to record each fact's own element id and any ix:continuation element ids in its value
  source (they concatenate to form the value).
  Option is to also capture the inner text in the value property.

  To request inner text values for text blocks:
      in GUI operation provide a formula parameter named inlineText containing true
      in command line mode specify --inlineText
  
  To request xBRL-JSON instead of the OIM Taxonomy (XbrlModel) fact set
      in GUI operation provide a formula parameter named oimJSON containing true
      in command line mode specify --oimJSON

  To save an OIM instance with duplicate fact removed use the `--deduplicateOimFacts` argument with either `complete`,
  `consistent-pairs`, or `consistent-sets` as the value.
  For details on what eaxctly consitutes a duplicate fact and why there are multiple options read the
  [Fact Deduplication][fact-deduplication] documentation.
  ```bash
  python arelleCmdLine.py --plugins saveOIMFacts --file filing-documents.zip --SaveOIMFactspace example.json --deduplicateOimFacts complete
  ```

[fact-deduplication]: project:/user_guides/fact_deduplication.md

### GUI Usage

- **Save Re-Loadable Output**:
  1. Load the desired report in Arelle.
  2. Go to `Tools` > `Save OIM Factspace`.
  3. Specify a filename (the output is written as JSON).

## Additional Notes

If the loaded report refers to a taxonomy on the local file system, the OIM instance needs to be saved in the same
directory to maintain the validity of the relative file system path to the taxonomy.
"""

from __future__ import annotations

import csv
import io
import json
import operator
import os
import threading
import zipfile
from collections.abc import Iterable
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from lxml import etree
from math import isinf, isnan
from numbers import Number
from optparse import OptionParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Callable, Optional, cast

import regex as re
from openpyxl import Workbook
from openpyxl.cell.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Color, PatternFill, fills
from openpyxl.worksheet.dimensions import ColumnDimension

from arelle import ModelDocument, ValidateDuplicateFacts, XbrlConst
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelInlineFact
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import (
    DateTime,
    DayTimeDuration,
    IsoDuration,
    QName,
    Time,
    YearMonthDuration,
    gDay,
    gMonth,
    gMonthDay,
    gYear,
    gYearMonth,
    qname,
    tzinfoStr,
)
from ordered_set import OrderedSet
from arelle.typing import TypeGetText
from arelle.UrlUtil import relativeUri
from arelle.utils.PluginData import PluginData
from arelle.utils.PluginHooks import PluginHooks
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.ValidateFilingText import elementsWithNoContent
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlValidateConst import VALID, NONE, UNVALIDATED

if TYPE_CHECKING:
    from tkinter import Menu

    from arelle.Cntlr import Cntlr
    from arelle.CntlrCmdLine import CntlrCmdLine
    from arelle.CntlrWinMain import CntlrWinMain
    from arelle.ModelXbrl import ModelXbrl
    from arelle.RuntimeOptions import RuntimeOptions

_: TypeGetText

PLUGIN_NAME = "Save OIM FactPositions"

tagsWithNoContent = set(f"{{http://www.w3.org/1999/xhtml}}{t}" for t in elementsWithNoContent)
for t in ("schemaRef", "linkbaseRef", "roleRef", "arcroleRef", "loc", "arc"):
    tagsWithNoContent.add(f"{{http://www.xbrl.org/2003/linkbase}}{t}")
tagsWithNoContent.add("{http://www.xbrl.org/2013/inlineXBRL}relationship")


def uncloseSelfClosedTags(doc):
    doc.parser.set_element_class_lookup(None)  # modelXbrl class features are already closed now, block class lookup
    for e in doc.xmlRootElement.iter():
        # check if no text, no children and not self-closable element for EDGAR
        if (e.text is None and (not e.getchildren())
            and e.tag not in tagsWithNoContent):
            e.text = ""  # prevents self-closing tag with etree.tostring for zip and dissem folders

def serializeXml(xmlRootElement):
    initialComment = b''  # tostring drops initial comments
    node = xmlRootElement
    while node.getprevious() is not None:
        node = node.getprevious()
        if isinstance(node, etree._Comment):
            initialComment = etree.tostring(node, encoding="UTF-8") + b'\n' + initialComment
    serXml = etree.tostring(xmlRootElement, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    if initialComment and serXml and serXml.startswith(b"<?"):
        i = serXml.find(b"<html")
        if i:
            endElt = serXml.find(b">",i)
            htmlElt = serXml[i:endElt]
            for prefix, ns in xmlRootElement.nsmap.items():
                if ns != "http://www.w3.org/1999/xhtml":
                    bPfx = prefix.encode("utf-8")
                    bNs = ns.encode("utf-8")
                    if prefix:
                        htmlElt = re.sub(b"xmlns:"+bPfx+b"=['\"]"+bNs+b"['\"]\\s*", b"", htmlElt)
                    else:
                        htmlElt = re.sub(b"xmlns=['\"]"+bNs+b"['\"]\\s*", b"", htmlElt)
            serXml = serXml[:i] + initialComment + htmlElt + serXml[endElt:]
    return serXml

reservedUriAliases = {
    XbrlConst.defaultLinkRole: "_",
    XbrlConst.factExplanatoryFact: "explanatoryFact",
    XbrlConst.factFootnote: "footnote",
    XbrlConst.iso4217: "iso4217",
    XbrlConst.utr: "utr",
    XbrlConst.xbrli: "xbrli",
    XbrlConst.xsd: "xs",
}

ONE = Decimal(1)
TEN = Decimal(10)
NILVALUE = "nil"
SCHEMA_LB_REFS = {
    qname("{http://www.xbrl.org/2003/linkbase}schemaRef"),
    # qname("{http://www.xbrl.org/2003/linkbase}linkbaseRef")
}
ROLE_REFS = {
    qname("{http://www.xbrl.org/2003/linkbase}roleRef"),
    qname("{http://www.xbrl.org/2003/linkbase}arcroleRef"),
}
ENTITY_NA_QNAME = ("https://xbrl.org/entities", "NA")

OimFact = dict[str, Any]
oimModel = dict[str, Any]

class NamespacePrefixes:
    def __init__(self, prefixesByNamespace: dict[str, str] | None = None) -> None:
        self._prefixesByNamespace: dict[str, str] = prefixesByNamespace or {}
        self._usedPrefixes: set[str] = set(self._prefixesByNamespace.values())

    @property
    def namespaces(self) -> dict[str, str]:
        return {
            prefix: namespace
            for namespace, prefix in sorted(
                self._prefixesByNamespace.items(),
                key=operator.itemgetter(1)
            )
        }

    def __contains__(self, namespace: str) -> bool:
        return namespace in self._prefixesByNamespace

    def getPrefix(self, namespace: str) -> str | None:
        return self._prefixesByNamespace.get(namespace)

    def addNamespace(self, namespace: str, preferredPrefix: str) -> str:
        prefix = self._prefixesByNamespace.get(namespace)
        if prefix is not None:
            return prefix

        prefix = reservedUriAliases.get(namespace)
        if prefix is None:
            prefix = preferredPrefix
            i = 2
            while prefix in self._usedPrefixes:
                prefix = f"{preferredPrefix}{i}"
                i += 1
        self._prefixesByNamespace[namespace] = prefix
        self._usedPrefixes.add(prefix)
        return prefix


def saveOIMFacts(
    modelXbrl: ModelXbrl,
    oimFile: str,
    outputZip: zipfile.ZipFile | None = None,
    saveInlineTextValue: bool = False,
    saveOimJson: bool = False,
    # arguments to add extension features to OIM document
    extensionPrefixes: dict[str, str] | None = None,
    extensionReportObjects: dict[str, Any] | None = None,
    extensionFactPropertiesMethod: Callable[[ModelFact, OimFact], None] | None = None,
    extensionReportFinalizeMethod: Callable[[oimModel], None] | None = None,
    *args: Any,
    **kwargs: Any,
) -> None:
    isJSON = oimFile.endswith(".json")
    isCBOR = oimFile.endswith(".cbor")
    
    if saveOimJson:
        oimErrorPattern = re.compile("oime|oimce|xbrlje|xbrlce")
        xbrl = "https://xbrl.org/2021"
        reservedUriAliases[xbrl] = "xbrl"
        qnConceptCoreDim = qname("concept", noPrefixIsNoNamespace=True)
        qnLangCoreDim = qname("language", noPrefixIsNoNamespace=True)
        qnPeriodCoreDim = qname("period", noPrefixIsNoNamespace=True)
        qnEntityCoreDim = qname("entity", noPrefixIsNoNamespace=True)
        qnUnitCoreDim = qname("unit", noPrefixIsNoNamespace=True)
    else:
        oimErrorPattern = re.compile("oime|oimce|xbrlje|xbrlce")
        xbrl = "https://xbrl.org/2026"
        reservedUriAliases[xbrl] = "xbrl"
        qnConceptCoreDim = qname(xbrl, "xbrl:concept")
        qnLangCoreDim = qname(xbrl, "xbrl:language")
        qnPeriodCoreDim = qname(xbrl, "xbrl:period")
        qnEntityCoreDim = qname(xbrl, "xbrl:entity")
        qnUnitCoreDim = qname(xbrl, "xbrl:unit")

    # OIM Taxonomy (XbrlModel) fact-source model constants (oim-taxonomy.md §"Fact locator types").
    # Inline value sources are located by the html element id locator; scale/sign/transformation/escape
    # are carried on the fact value object itself.
    htmlElementLocatorType = "xbrl:htmlElementLocatorType"
    htmlElementIdProperty = "xbrl:htmlElementId"

    namespacePrefixes = NamespacePrefixes({xbrl: "xbrl"})
    if extensionPrefixes:
        for extensionPrefix, extensionNamespace in extensionPrefixes.items():
            namespacePrefixes.addNamespace(extensionNamespace, extensionPrefix)
    linkTypeAliases = {}
    groupAliases = {}

    def compileQname(qname: QName) -> None:
        if qname.namespaceURI is not None and qname.namespaceURI not in namespacePrefixes:
            namespacePrefixes.addNamespace(qname.namespaceURI, qname.prefix or "")

    aspectsDefined = {qnConceptCoreDim, qnEntityCoreDim, qnPeriodCoreDim}

    def oimValue(obj: Any) -> Any:
        if isinstance(obj, list):
            # set-valued enumeration fact
            return " ".join([oimValue(o) for o in obj])
        if isinstance(obj, QName) and obj.namespaceURI is not None:
            if obj.namespaceURI not in namespacePrefixes:
                namespacePrefixes.addNamespace(obj.namespaceURI, obj.prefix or "_")
            return f"{namespacePrefixes.getPrefix(obj.namespaceURI)}:{obj.localName}"
        if isinstance(obj, (float, Decimal)):
            try:
                if isinf(obj):
                    return "-INF" if obj < 0 else "INF"
                elif isnan(obj):
                    return "NaN"
                elif isinstance(obj, Decimal):
                    # XML canonical representation of decimal requires a decimal point.
                    # https://www.w3.org/TR/xmlschema-2/#decimal-canonical-representation
                    if obj % 1 == 0:
                        return f"{obj:.1f}"
                    intPart, fracPart = f"{obj:f}".split(".")
                    canonicalFracPart = fracPart.rstrip("0") or "0"
                    return f"{intPart}.{canonicalFracPart}"
                else:
                    return f"{obj}"
            except Exception:
                return str(obj)
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(
            obj,
            (
                DateTime,
                YearMonthDuration,
                DayTimeDuration,
                Time,
                gYearMonth,
                gMonthDay,
                gYear,
                gMonth,
                gDay,
                IsoDuration,
                int,
            ),
        ):
            return str(obj)
        return obj

    def oimPeriodValue(cntx: ModelContext) -> dict[str, str]:
        if cntx.isStartEndPeriod:
            s = cntx.startDatetime
            e = cntx.endDatetime
        else:  # instant
            s = e = cntx.instantDatetime
        assert isinstance(s, datetime) and isinstance(e, datetime)
        return {
            str(qnPeriodCoreDim): (
                f"{s.year:04}-{s.month:02}-{s.day:02}T{s.hour:02}:{s.minute:02}:{s.second:02}{tzinfoStr(s)}/"
                if cntx.isStartEndPeriod
                else ""
            )
            + f"{e.year:04}-{e.month:02}-{e.day:02}T{e.hour:02}:{e.minute:02}:{e.second:02}{tzinfoStr(e)}"
        }

    hasTuple = False
    hasLang = False
    hasUnits = False
    hasNumeric = False
    inlineFactDocBasenames = OrderedSet()  # inline (html) documents that carry fact value sources

    footnotesRelationshipSet = ModelRelationshipSet(modelXbrl, "XBRL-footnotes")

    # compile QNames in instance for OIM
    for fact in modelXbrl.factsInInstance:
        concept = fact.concept
        if concept is not None:
            if concept.isNumeric:
                hasNumeric = True
            if concept.baseXbrliType in ("string", "normalizedString", "token") and fact.xmlLang:
                hasLang = True
        compileQname(fact.qname)
        if hasattr(fact, "xValue") and isinstance(fact.xValue, QName):
            compileQname(fact.xValue)
        unit = fact.unit
        if unit is not None:
            hasUnits = True
        if fact.modelTupleFacts:
            hasTuple = True
        if isinstance(fact, ModelInlineFact) and not any(True for e in fact.iterancestors("{http://www.xbrl.org/2013/inlineXBRL}hidden")):
            inlineFactDocBasenames.add(fact.modelDocument.basename)
            if fact.format:
                namespacePrefixes.addNamespace(fact.format.namespaceURI, fact.format.prefix)
    if hasTuple:
        modelXbrl.error(
            "arelleOIMsaver:tuplesNotAllowed", "Tuples are not allowed in an OIM document", modelObject=modelXbrl
        )
        return

    entitySchemePrefixes = {}
    for cntx in modelXbrl.contexts.values():
        if cntx.entityIdentifierElement is not None:
            scheme = cntx.entityIdentifier[0]
            if scheme not in entitySchemePrefixes:
                if not entitySchemePrefixes:  # first one is just scheme
                    if scheme == "http://www.sec.gov/CIK":
                        _schemePrefix = "cik"
                    elif scheme == "http://standard.iso.org/iso/17442":
                        _schemePrefix = "lei"
                    else:
                        _schemePrefix = "scheme"
                else:
                    _schemePrefix = f"scheme{len(entitySchemePrefixes) + 1}"
                namespacePrefixes.addNamespace(scheme, _schemePrefix)
                entitySchemePrefixes[scheme] = namespacePrefixes.getPrefix(scheme)
        for dim in cntx.qnameDims.values():
            compileQname(dim.dimensionQname)
            aspectsDefined.add(dim.dimensionQname)
            if dim.isExplicit:
                compileQname(dim.memberQname)

    for unit in modelXbrl.units.values():
        if unit is not None:
            for measures in unit.measures:
                for measure in measures:
                    compileQname(measure)

    if hasLang:
        aspectsDefined.add(qnLangCoreDim)
    if hasUnits:
        aspectsDefined.add(qnUnitCoreDim)

    for footnoteRel in footnotesRelationshipSet.modelRelationships:
        if footnoteRel.arcrole not in linkTypeAliases:
            typePrefix = reservedUriAliases.get(footnoteRel.arcrole, f"ftTyp_{os.path.basename(footnoteRel.arcrole)}")
            linkTypeAliases[footnoteRel.arcrole] = typePrefix
        if footnoteRel.linkrole not in groupAliases:
            groupPrefix = reservedUriAliases.get(footnoteRel.linkrole, f"ftGrp_{os.path.basename(footnoteRel.linkrole)}")
            groupAliases[footnoteRel.linkrole] = groupPrefix

    dtsReferences = set()
    assert modelXbrl.modelDocument is not None
    baseUrl = modelXbrl.modelDocument.uri.partition("#")[0]
    for doc, ref in sorted(modelXbrl.modelDocument.referencesDocument.items(), key=lambda _item: _item[0].uri):
        if ref.referringModelObject.qname in SCHEMA_LB_REFS:
            dtsReferences.add(relativeUri(baseUrl, doc.uri))
    for refType in ("role", "arcrole"):
        for refElt in sorted(
            modelXbrl.modelDocument.xmlRootElement.iterchildren(f"{{http://www.xbrl.org/2003/linkbase}}{refType}Ref"),
            key=lambda elt: elt.get(refType + "URI"),
        ):
            dtsReferences.add(refElt.get("{http://www.w3.org/1999/xlink}href").partition("#")[0])
    dtsReferences = sorted(dtsReferences)  # turn into list

    extensionPrefix = ""
    importedTaxonomies = OrderedSet()
    if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET, ModelDocument.Type.LINKBASE):
        for doc, docReference in modelXbrl.modelDocument.referencesDocument.items():
            if ("href" in docReference.referenceTypes and doc.targetNamespace in namespacePrefixes and
                os.path.isabs(modelXbrl.modelDocument.uri) == os.path.isabs(doc.uri) and os.path.commonpath((modelXbrl.modelDocument.uri, doc.uri))):
                extensionPrefix = namespacePrefixes.getPrefix(doc.targetNamespace)
                if doc.type == ModelDocument.Type.SCHEMA:
                    importedTaxonomies.add(doc.basename)
                break

    # Report (extension) prefix used to name the model, fact sources and fact maps; when the extension
    # schema was not identified, fall back to the prefix of the report's primary referenced taxonomy so
    # these names use a declared namespace prefix (consistent with the prefix used for the fact names).
    reportPrefix = extensionPrefix
    if not reportPrefix:
        for refDoc in modelXbrl.modelDocument.referencesDocument:
            refPrefix = namespacePrefixes.getPrefix(refDoc.targetNamespace) if refDoc.targetNamespace else None
            if refPrefix:
                reportPrefix = refPrefix
                break
    reportPrefix = reportPrefix or "report"
    # Each inline source document becomes a factSourceMapping (documentInfo.sourceMappings) whose
    # sourceName is referenced by the factSource/factMap that declares the html element locator type.
    sourceNameByBasename = OrderedDict(
        (basename, f"{reportPrefix}:{os.path.splitext(basename)[0]}Source")
        for basename in inlineFactDocBasenames
    )
    hasInlineSources = bool(sourceNameByBasename)
    multiSource = len(sourceNameByBasename) > 1

    footnoteObjects = {} # OIM Taxonomy objects
    factFootnoteRels = set()
    factFactFootnoteRels = set()
    footnoteNetworkNamePrefixes = [None, None]
    footnoteFacts = set() # xBRL-JSON
    
    def getPrefix(obj: XbrlObject) -> str:
        prefix = None
        for refDoc in obj.modelDocument.referencesDocument.keys():
            if refDoc.targetNamespace:
                prefix = namespacePrefixes.getPrefix(refDoc.targetNamespace)
                break
        return prefix

    def factFootnotes(
        fact: ModelFact,
        newFact: dict[str, Any] | None = None,
    ):
        footnotes = []
        oimLinks = {}
        if saveOimJson:
            for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
                srcId = fact.id if fact.id else f"f{fact.objectIndex}"
                toObj = footnoteRel.toModelObject
                # json
                typePrefix = linkTypeAliases[footnoteRel.arcrole]
                groupPrefix = groupAliases[footnoteRel.linkrole]
                if typePrefix not in oimLinks:
                    oimLinks[typePrefix] = {}
                _link = oimLinks[typePrefix]
                if groupPrefix not in _link:
                    if isJSON:
                        _link[groupPrefix] = []
                    elif isCSVorXL:
                        _link[groupPrefix] = {}
                tgtId = toObj.id if toObj.id else f"f{toObj.objectIndex}"
                if isJSON:
                    tgtIdList = _link[groupPrefix]
                    tgtIdList.append(tgtId)
                elif isCSVorXL:
                    # Footnote links in xBRL-CSV include the CSV table identifier.
                    tgtIdList = _link[groupPrefix].setdefault(f"facts.r_{srcId}.value", [])
                    tgtIdList.append(f"footnotes.r_{tgtId}.footnote")
                footnote = {
                    "group": footnoteRel.linkrole,
                    "footnoteType": footnoteRel.arcrole,
                }
                if isinstance(toObj, ModelFact):
                    footnote["factRef"] = tgtId
                else:  # text footnotes
                    footnote["id"] = tgtId
                    footnote["footnote"] = toObj.viewText()
                    if toObj.xmlLang:
                        footnote["language"] = toObj.xmlLang
                    footnoteFacts.add(toObj)
                    footnotes.append(footnote)
            if oimLinks:
                _links = {
                    typePrefix: {groupPrefix: idList for groupPrefix, idList in sorted(groups.items())}
                    for typePrefix, groups in sorted(oimLinks.items())
                }
                if isJSON and newFact is not None:
                    newFact["links"] = _links
        else:
            for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
                srcPrefix = getPrefix(fact)
                toObj = footnoteRel.toModelObject
                tgtPrefix = getPrefix(toObj)
                srcName = f"{srcPrefix}:{fact.id}" if fact.id else f"{srcPrefix}:f{fact.objectIndex}"
                tgtName = f"{tgtPrefix}:{toObj.id}" if toObj.id else f"{tgtPrefix}:f{toObj.objectIndex}"
                relQns = (srcName, tgtName)
                if isinstance(toObj, ModelFact): # fact-fact relationship
                    factFactFootnoteRels.add(relQns)
                    if srcPrefix and not footnoteNetworkNamePrefixes[1]:
                        footnoteNetworkNamePrefixes[0] = srcPrefix
                else: # text footnotes
                    footnote = {
                        "name": tgtName,
                        "content": toObj.viewText()
                        }
                    if toObj.xmlLang:
                        footnote["language"] = toObj.xmlLang
                    footnoteObjects[tgtName] = footnote
                    factFootnoteRels.add(relQns)
                    if srcPrefix and not footnoteNetworkNamePrefixes[0]:
                        footnoteNetworkNamePrefixes[0] = srcPrefix
        return footnotes

    def factDimensions(fact: ModelFact, factPositions, factspacesByDims) -> dict[str, Any]:
        factDims = {}
        concept = fact.concept
        if concept is not None:
            factDims[str(qnConceptCoreDim)] = oimValue(concept.qname)
            if concept.type is not None and concept.type.isOimTextFactType and fact.xmlLang:
                factDims[str(qnLangCoreDim)] = fact.xmlLang
        cntx = fact.context
        if cntx is not None:
            if cntx.entityIdentifierElement is not None and cntx.entityIdentifier != ENTITY_NA_QNAME:
                factDims[str(qnEntityCoreDim)] = oimValue(qname(*cntx.entityIdentifier))
            if cntx.period is not None and not cntx.isForeverPeriod:
                factDims.update(oimPeriodValue(cntx))
            for _qn, dim in sorted(cntx.qnameDims.items(), key=lambda item: item[0]):
                if dim.isExplicit:
                    dimVal = oimValue(dim.memberQname)
                else:  # typed
                    if dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1"):
                        dimVal = None
                    else:
                        dimVal = dim.typedMember.stringValue
                factDims[str(dim.dimensionQname)] = dimVal
        unit = fact.unit
        if unit is not None:
            _mMul, _mDiv = unit.measures
            _sMul = "*".join(oimValue(m) for m in sorted(_mMul, key=lambda m: oimValue(m)))
            if _mDiv:
                _sDiv = "*".join(oimValue(m) for m in sorted(_mDiv, key=lambda m: oimValue(m)))
                if len(_mDiv) > 1:
                    _sUnit = f"({_sMul})/({_sDiv})" if len(_mMul) > 1 else f"{_sMul}/({_sDiv})"
                else:
                    _sUnit = f"({_sMul})/{_sDiv}" if len(_mMul) > 1 else f"{_sMul}/{_sDiv}"
            else:
                _sUnit = _sMul
            if _sUnit != "xbrli:pure":
                factDims[str(qnUnitCoreDim)] = _sUnit
        if saveOimJson:
            factPositions[f"{fact.id or fact.objectIndex}"] = newFact = {}
            newFact["dimensions"] = factDims
        else:
            # group facts that share identical dimensions into a single factSet (fs_) object,
            # each contributing a fact value object to its factValues array
            dimsKey = tuple(sorted(factDims.items(), key=lambda k: k[0]))
            newFact = factspacesByDims.get(dimsKey)
            if newFact is None:
                newFact = {
                    "name": f"{getPrefix(fact)}:fs_{fact.id or f'f{fact.objectIndex}'}",
                    "factDimensions": factDims,
                    "factValues": [],
                }
                factspacesByDims[dimsKey] = newFact
                factPositions.append(newFact)
        return newFact
    
    def appendFactToFactspace(fact: ModelFact, newFact: dict[str, Any]) -> None:
        factValue = None
        # only items with a resolved concept yield a fact value (skip tuples and, e.g. when the
        # taxonomy did not load, facts with an unresolved concept)
        if fact.concept is not None and fact.isItem:
            if saveOimJson:
                factValue = newFact
                factValue["name"] = f"{getPrefix(fact)}:{fact.id or f'f{fact.objectIndex}'}"
            else:
                factValue = {"name": f"{getPrefix(fact)}:{fact.id or f'f{fact.objectIndex}'}_val"}
            isInlineSource = (
                isinstance(fact, ModelInlineFact)
                and not any(True for e in fact.iterancestors("{http://www.xbrl.org/2013/inlineXBRL}hidden"))
            )
            if isInlineSource and saveOimJson:
                # xBRL-JSON: value sources as href/medium (unchanged)
                factValue["valueSources"] = valueSources = []
                vs = {
                    "href": f"{fact.modelDocument.basename}#{fact.id if fact.id else fact.objectIndex}",
                    "medium": "html"
                }
                if fact.format:
                    vs["transformation"] = str(fact.format)
                if fact.scaleInt:
                    vs["scale"] = fact.scaleInt
                if fact.sign:
                    vs["sign"] = fact.sign
                if fact.get("escape"):
                    vs["escape"] = True
                valueSources.append(vs)
                if fact.concept.isTextBlock and saveInlineTextValue:
                    stringValues = [super(ModelFact, fact).stringValue]
                contElt = getattr(fact, "_continuationElement", None)
                while contElt is not None:
                    vs = {"href": f"{fact.modelDocument.basename}#{contElt.id}"}
                    valueSources.append(vs)
                    if fact.concept.isTextBlock and saveInlineTextValue:
                        stringValues.append(contElt.stringValue)
                    contElt = getattr(contElt, "_continuationElement", None)
                if fact.concept.isTextBlock and saveInlineTextValue:
                    factValue["value"] = "".join(stringValues)
                    del stringValues  # dereference big chunks of text
            elif isInlineSource:
                # OIM Taxonomy (XbrlModel): a single fact value source object whose html element id
                # locator lists the fact element followed by any ix:continuation element ids (the
                # locator concatenates them). Transformation/scale/sign/escape are fact value properties.
                elementIds = [fact.id if fact.id else f"{fact.objectIndex}"]
                if fact.concept.isTextBlock and saveInlineTextValue:
                    stringValues = [super(ModelFact, fact).stringValue]
                contElt = getattr(fact, "_continuationElement", None)
                while contElt is not None:
                    elementIds.append(contElt.id)
                    if fact.concept.isTextBlock and saveInlineTextValue:
                        stringValues.append(contElt.stringValue)
                    contElt = getattr(contElt, "_continuationElement", None)
                factValue["valueSources"] = [
                    {"properties": [{"property": htmlElementIdProperty, "value": elementIds}]}
                ]
                if multiSource:
                    factValue["source"] = sourceNameByBasename.get(fact.modelDocument.basename)
                if fact.format:
                    factValue["transformation"] = oimValue(fact.format)
                if fact.scaleInt:
                    factValue["scale"] = fact.scaleInt
                if fact.sign:
                    factValue["sign"] = fact.sign
                if fact.get("escape") in ("true", "1"):
                    factValue["escape"] = True
                if fact.concept.isTextBlock and saveInlineTextValue:
                    factValue["value"] = "".join(stringValues)
                    del stringValues  # dereference big chunks of text
            else:  # non-inline fact: literal value
                if not fact.isNil:
                    factValue["value"] = str(oimValue(fact.xValue))
            if fact.concept.isNumeric and not fact.isNil:
                _inferredDecimals = inferredDecimals(fact)
                if not isinf(_inferredDecimals):  # accuracy omitted if infinite
                    factValue["decimals"] = _inferredDecimals
        if not saveOimJson and factValue is not None:
            newFact["factValues"].append(factValue)

    ixDocs = {}
    editedIxDocs = {}
    editedModelXbrls = set()
    # add missing IDs to inline documents
    for ixdsHtmlRootElt in getattr(modelXbrl, "ixdsHtmlElements", ()):
        doc = ixdsHtmlRootElt.modelDocument
        hasIdAssignedFact = False
        for e in ixdsHtmlRootElt.iter(doc.ixNStag + "nonNumeric", doc.ixNStag + "nonFraction", doc.ixNStag + "fraction"):
            if getattr(e, "xValid", 0) >= VALID and not e.id:  # id is optional on facts but required for ixviewer-plus and arelle inline viewers
                id = f"ixv-{e.objectIndex}"
                if id in doc.idObjects or id in modelXbrl.ixdsEltById:
                    for i in range(1000):
                        uid = f"{id}_{i}"
                        if uid not in doc.idObjects and uid not in modelXbrl.ixdsEltById:
                            id = uid
                            break
                e.set("id", id)
                doc.idObjects[id] = e
                modelXbrl.ixdsEltById[id] = e
                hasIdAssignedFact = True
        if hasIdAssignedFact:
            editedIxDocs[doc.basename] = doc  # causes it to be rewritten out
            editedModelXbrls.add(modelXbrl)
        ixDocs[doc.basename] = doc

    # common metadata
    oimModel = {}  # top level of oim json output
    oimModel["documentInfo"] = oimDocInfo = {}
    if saveOimJson:
        oimDocInfo["documentType"] = "https://xbrl.org/2021/xbrl-json"
    else:
        oimDocInfo["documentType"] = "https://xbrl.org/2026/module"
        oimDocInfo["documentNamespacePrefix"] = reportPrefix
        oimModel["xbrlModel"] = xbrlModelObject = {
            "name": f"{reportPrefix}:{os.path.splitext(modelXbrl.modelDocument.basename)[0]}"
            }
        if importedTaxonomies:
            oimDocInfo["importMapping"] = OrderedDict()
            xbrlModelObject["importedTaxonomies"] = []
        for txmyBasename in importedTaxonomies:
            xbrlModelName = f"{reportPrefix}:{os.path.splitext(txmyBasename)[0]}"
            oimDocInfo["importMapping"][xbrlModelName] = txmyBasename
            xbrlModelObject["importedTaxonomies"].append({"xbrlModelName": xbrlModelName})
        if hasInlineSources:
            # documentInfo.sourceMappings locates the source document(s); the factSource/factMap
            # declare the html element locator type used by the fact value source objects.
            oimDocInfo["sourceMappings"] = [
                {"sourceName": sourceName, "url": basename}
                for basename, sourceName in sourceNameByBasename.items()
            ]
            factMapName = f"{reportPrefix}:htmlElementFactMap"
            xbrlModelObject["factSources"] = [
                {"name": sourceName, "factMapName": factMapName}
                for sourceName in sourceNameByBasename.values()
            ]
            xbrlModelObject["factMaps"] = [
                {"name": factMapName, "factLocatorType": htmlElementLocatorType}
            ]
    if saveOimJson:
        if linkTypeAliases:
            oimDocInfo["linkTypes"] = {a: u for u, a in sorted(linkTypeAliases.items(), key=operator.itemgetter(1))}
        if groupAliases:
            oimDocInfo["linkGroups"] = {a: u for u, a in sorted(groupAliases.items(), key=operator.itemgetter(1))}
        oimDocInfo["xbrlModel"] = dtsReferences
        oimDocInfo["features"] = {"xbrl:canonicalValues": True}
    oimDocInfo["namespaces"] = namespacePrefixes.namespaces
    # oimDocInfo["xbrlModel"] = dtsReferences

    factsToSave = modelXbrl.facts
    pluginData = modelXbrl.modelManager.cntlr.getPluginData(PLUGIN_NAME)
    if isinstance(pluginData, SaveOIMFactspacePluginData) and pluginData.deduplicateFactsType is not None:
        deduplicatedFacts = frozenset(ValidateDuplicateFacts.getDeduplicatedFacts(modelXbrl, pluginData.deduplicateFactsType))
        duplicateFacts = frozenset(f for f in modelXbrl.facts if f not in deduplicatedFacts)
        if duplicateFacts:
            for fact in duplicateFacts:
                ValidateDuplicateFacts.logDeduplicatedFact(modelXbrl, fact)
            factsToSave = [f for f in factsToSave if f not in duplicateFacts]

    # save JSON
    if saveOimJson:
        oimModel["facts"] = newFacts = {}
    else:
        oimModel["xbrlModel"]["facts"] = newFacts = []
    newFactsByDims = {} # unique entry for mutli-valued newFact
    # add in report level extension objects
    if extensionReportObjects:
        for extObjQName, extObj in extensionReportObjects.items():
            oimModel[extObjQName] = extObj

    def saveJsonFacts(facts: list[ModelFact]) -> None:
        for fact in facts:
            if fact.concept is None or not fact.isItem:
                # concept could not be resolved (e.g. its taxonomy did not load) so the fact cannot be
                # represented as a factSet with an xbrl:concept dimension; skip it (already logged by load)
                continue
            newFact = factDimensions(fact, newFacts, newFactsByDims)
            appendFactToFactspace(fact, newFact)
            # add in fact level extension objects
            if extensionFactPropertiesMethod:
                extensionFactPropertiesMethod(fact, newFact)
            factFootnotes(fact, newFact)

    saveJsonFacts(factsToSave)

    # add footnotes
    if saveOimJson and footnoteFacts:
        # add footnotes as pseudo facts
        for ftObj in footnoteFacts:
            ftId = ftObj.id if ftObj.id else f"f{ftObj.objectIndex}"
            newFacts[ftId] = fact = {}
            fact["value"] = ftObj.viewText()
            fact["dimensions"] = {
                "concept": "xbrl:note",
                "noteId": ftId,
            }
            if ftObj.xmlLang:
                fact["dimensions"]["language"] = ftObj.xmlLang.lower()
    elif footnoteObjects:
        # Text footnotes become footnote objects; the facts they annotate are listed in forObjects.
        footnotesOut = []
        for tgtName, footnote in footnoteObjects.items():
            entry = {"name": footnote["name"]}
            forObjects = [r[0] for r in sorted(factFootnoteRels) if r[1] == tgtName]
            if forObjects:
                entry["forObjects"] = forObjects
            entry["content"] = footnote["content"]
            if "language" in footnote:
                entry["language"] = footnote["language"]
            footnotesOut.append(entry)
        oimModel["xbrlModel"]["footnotes"] = footnotesOut
        # Fact-to-fact footnote relationships become a network.
        if factFactFootnoteRels:
            networkPrefix = footnoteNetworkNamePrefixes[0] or reportPrefix
            oimModel["xbrlModel"]["networks"] = [{
                "name": f"{networkPrefix}:FactFactFootnoteNetwork",
                "relationshipTypeName": "xbrl:fact-fact",
                "relationships": [{"source": r[0], "target": r[1]} for r in sorted(factFactFootnoteRels)]
                }]

    # allow extension report final editing before writing json structure
    # (possible example, reorganize facts into array vs object)
    if extensionReportFinalizeMethod:
        extensionReportFinalizeMethod(oimModel)

    # strip ix: elements from modelDocuments
    for ixDoc in ixDocs.values():
        # remove ix:header
        ixElts = [e for e in ixDoc.xmlRootElement.getroottree().iterfind(".//{http://www.xbrl.org/2013/inlineXBRL}header")]
        for e in ixElts:
            e.getparent().remove(e)

        # convert remaining ix elements into spans
        ixElts = [e for e in ixDoc.xmlRootElement.getroottree().iterfind(".//{http://www.xbrl.org/2013/inlineXBRL}*")]
        for e in ixElts:
            # is there a div child?
            if any(True for f in e.iter("{http://www.w3.org/1999/xhtml}div")):
                e.tag = "{http://www.w3.org/1999/xhtml}div" # must be div if any child div
            else:
                e.tag = "{http://www.w3.org/1999/xhtml}span"
            unwantedAttributes = [a for a in e.attrib.keys() if a not in {"class","id","style"}]
            for a in unwantedAttributes:
                e.attrib.pop(a)

        editedIxDocs[ixDoc.basename] = ixDoc
        editedModelXbrls.add(modelXbrl)

    with io.StringIO() if outputZip else open(oimFile, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(oimModel, indent=1))
        if outputZip:
            fh.seek(0)
            outputZip.writestr(os.path.basename(oimFile), fh.read())
    if not outputZip:
        modelXbrl.modelManager.cntlr.showStatus(_("Saved JSON OIM file {}").format(oimFile))

    # resave edited documents
    for reportedFile, doc in editedIxDocs.items():
        uncloseSelfClosedTags(doc)
        outPath = os.path.join(os.path.dirname(oimFile),
                               f"{os.path.splitext(reportedFile)[0]}-edited{os.path.splitext(reportedFile)[1]}")
        ix = serializeXml(doc.xmlRootElement)
        with io.open(outPath, "wb") as fh:
            fh.write(ix)


def SaveOIMFactspaceMenuCommand(cntlr: CntlrWinMain) -> None:
    # save DTS menu item has been invoked
    if (
        cntlr.config is None
        or cntlr.modelManager is None
        or cntlr.modelManager.modelXbrl is None
        or cntlr.modelManager.modelXbrl.modelDocument is None
        or cntlr.modelManager.modelXbrl.modelDocument.type
        not in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
    ):
        cntlr.addToLog(
            messageCode="arelleOIMsaver",
            message=_("No supported XBRL instance documents loaded that can be saved to OIM format."),
        )
        return
        # get file name into which to save log file while in foreground thread
    oimFile = cntlr.uiFileDialog(
        "save",
        title=_("arelle - Save OIM FactPositions"),
        initialdir=cntlr.config.setdefault("loadableOIMFactspaceDir", "."),
        filetypes=[(_("JSON file .json"), "*.json"), (_("CBOR file .cbor"), "*.cbor")],
        defaultextension=".json",
    )  # type: ignore[no-untyped-call]
    if not isinstance(oimFile, str):
        # User cancelled file dialog.
        return

    cntlr.config["loadableOIMFactspaceDir"] = os.path.dirname(oimFile)
    cntlr.saveConfig()

    # options
    saveInlineTextValue = saveOimJson = False
    if "inlineText" in cntlr.modelManager.formulaOptions.parameterValues and cntlr.modelManager.formulaOptions.parameterValues["inlineText"][1]:
        saveInlineTextValue = True
    if "oimJSON" in cntlr.modelManager.formulaOptions.parameterValues and cntlr.modelManager.formulaOptions.parameterValues["oimJSON"][1]:
        saveOimJson = True

    thread = threading.Thread(
        target=lambda _modelXbrl=cntlr.modelManager.modelXbrl, _oimFile=oimFile: saveOIMFacts(
            _modelXbrl, _oimFile, None, saveInlineTextValue, saveOimJson
        )
    )
    thread.daemon = True
    thread.start()


def saveOimFiles(
    cntlr: Cntlr,
    modelXbrl: ModelXbrl,
    oimFiles: list[str],
    responseZipStream: BinaryIO | None = None,
    saveInlineTextValue: bool = False,
    saveOimJson: bool = False,
) -> None:
    try:
        if responseZipStream is None:
            for oimFile in oimFiles:
                saveOIMFacts(modelXbrl, oimFile, None, saveInlineTextValue, saveOimJson)
        else:
            with zipfile.ZipFile(responseZipStream, "a", zipfile.ZIP_DEFLATED, True) as _zip:
                for oimFile in oimFiles:
                    saveOIMFacts(modelXbrl, oimFile, _zip, saveInlineTextValue, saveOimJson)
            responseZipStream.seek(0)
    except Exception as ex:
        cntlr.addToLog(f"Exception saving OIM {ex}")


@dataclass
class SaveOIMFactspacePluginData(PluginData):
    deduplicateFactsType: ValidateDuplicateFacts.DeduplicationType | None
    saveTestcaseOimFileSuffix: str | None


class SaveOIMFactspacePlugin(PluginHooks):
    @staticmethod
    def cntlrCmdLineOptions(
        parser: OptionParser,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        parser.add_option(
            "--SaveOIMFactspace",
            action="store",
            dest="saveOIMFacts",
            help=_("Save Loadable OIM file (JSON)"),
        )
        parser.add_option(
            "--SaveOIMFactspaceDirectory",
            action="store",
            dest="saveOIMFactspaceDirectory",
            help=_("Directory into which to save the OIM file (JSON)"),
        )
        parser.add_option(
            "--saveTestcaseOIM",
            action="store",
            dest="saveTestcaseOimFileSuffix",
            help=_("Save Testcase Variation OIM file (argument is the file-name suffix, such as -savedOim.json)"),
        )
        parser.add_option(
            "--deduplicateOimFacts",
            action="store",
            choices=[a.value for a in ValidateDuplicateFacts.DeduplicationType],
            dest="deduplicateOimFacts",
            help=_("Remove duplicate facts when saving the OIM instance"))
        parser.add_option(
            "--inlineText",
            action="store_true",
            dest="inlineText",
            help=_("Option to capture text block inner text content in value property"))
        parser.add_option(
            "--oimJSON",
            action="store_true",
            dest="oimJSON",
            help=_("Option to save in OIM JSON format instead of OIM Taxonomy object format"))

    @staticmethod
    def cntlrCmdLineUtilityRun(
        cntlr: Cntlr,
        options: RuntimeOptions,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        deduplicateOimFacts = cast(Optional[str], getattr(options, "deduplicateOimFacts", None))
        saveTestcaseOimFileSuffix = cast(Optional[str], getattr(options, "saveTestcaseOimFileSuffix", None))
        deduplicateFactsType = None
        if deduplicateOimFacts is not None:
            deduplicateFactsType = ValidateDuplicateFacts.DeduplicationType(deduplicateOimFacts)
        pluginData = SaveOIMFactspacePluginData(PLUGIN_NAME, deduplicateFactsType, saveTestcaseOimFileSuffix)
        cntlr.setPluginData(pluginData)

    @staticmethod
    def cntlrWinMainMenuTools(
        cntlr: CntlrWinMain,
        menu: Menu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        menu.add_command(label="Save OIM Factspace", underline=0, command=lambda: SaveOIMFactspaceMenuCommand(cntlr))

    @staticmethod
    def cntlrCmdLineXbrlRun(
        cntlr: CntlrCmdLine,
        options: RuntimeOptions,
        modelXbrl: ModelXbrl,
        entrypoint: dict[str, str] | None = None,
        sourceZipStream: BinaryIO | None = None,
        responseZipStream: BinaryIO | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # extend XBRL-loaded run processing for this option
        oimFile = cast(Optional[str], getattr(options, "saveOIMFacts", None))
        allOimDirectory = cast(Optional[str], getattr(options, "saveOIMFactspaceDirectory", None))
        if (oimFile or allOimDirectory) and (
            modelXbrl is None
            or modelXbrl.modelDocument is None
            or modelXbrl.modelDocument.type
            not in {
                ModelDocument.Type.INSTANCE,
                ModelDocument.Type.INLINEXBRL,
                ModelDocument.Type.INLINEXBRLDOCUMENTSET,
            }
        ):
            cntlr.addToLog("No XBRL instance has been loaded.")
            return
        if oimFile:
            saveOimFiles(cntlr, modelXbrl, [oimFile], responseZipStream, options.inlineText, options.oimJSON)
        if allOimDirectory:
            oimDir = Path(allOimDirectory)
            try:
                oimDir.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                cntlr.addToLog(
                    _("Unable to save OIM factPosition into requested directory: {}, {}").format(allOimDirectory, err.strerror)
                )
                return
            assert modelXbrl.modelDocument is not None
            basefileStem = None
            if hasattr(modelXbrl, "ixdsTarget"):
                ixdsTarget = modelXbrl.ixdsTarget
                for doc in modelXbrl.modelDocument.referencesDocument:
                    if doc.type in {ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE}:
                        instanceFilename = Path(doc.uri)
                        if ixdsTarget is not None:
                            basefileStem = f"{instanceFilename.stem}.{ixdsTarget}"
                        else:
                            basefileStem = instanceFilename.stem
                        break
            if basefileStem is None:
                basefileStem = Path(modelXbrl.modelDocument.basename).stem
            oimFiles = [str(oimDir.joinpath(basefileStem + ext)) for ext in (".csv", ".json")]
            saveOimFiles(cntlr, modelXbrl, oimFiles, responseZipStream, options.inlineText, options.oimJSON)

    @staticmethod
    def testcaseVariationValidated(
        testcaseDTS: ModelXbrl,
        testInstanceDTS: ModelXbrl,
        extraErrors: list[str],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        pluginData = testcaseDTS.modelManager.cntlr.getPluginData(PLUGIN_NAME)
        oimFileSuffix = (
            pluginData.saveTestcaseOimFileSuffix if isinstance(pluginData, SaveOIMFactspacePluginData) else None
        )
        if (
            oimFileSuffix
            and testInstanceDTS is not None
            and testInstanceDTS.modelDocument is not None
            and testInstanceDTS.modelDocument.type
            in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
            and not any(oimErrorPattern.match(error) for error in testInstanceDTS.errors if error is not None)
        ):  # no OIM errors
            try:
                saveOIMFacts(testInstanceDTS, testInstanceDTS.modelDocument.uri + oimFileSuffix)
            except Exception as ex:
                testcaseDTS.modelManager.cntlr.addToLog(f"Exception saving OIM {ex}")

    @staticmethod
    def saveOIMFactSave(
        modelXbrl: ModelXbrl,
        oimFile: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        return saveOIMFacts(modelXbrl, oimFile, *args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "1.3",
    "description": "This plug-in saves a loaded XBRL instance as an XBRL OIM factPositions.",
    "license": "Apache-2",
    'author': 'Herm Fischer',
    'copyright': 'Exbee Ltd',
    # classes of mount points (required)
    "CntlrWinMain.Menu.Tools": SaveOIMFactspacePlugin.cntlrWinMainMenuTools,
    "CntlrCmdLine.Options": SaveOIMFactspacePlugin.cntlrCmdLineOptions,
    "CntlrCmdLine.Utility.Run": SaveOIMFactspacePlugin.cntlrCmdLineUtilityRun,
    "CntlrCmdLine.Xbrl.Run": SaveOIMFactspacePlugin.cntlrCmdLineXbrlRun,
    "TestcaseVariation.Validated": SaveOIMFactspacePlugin.testcaseVariationValidated,
    "SaveOIMFactspace.Save": SaveOIMFactspacePlugin.saveOIMFactSave,
}
