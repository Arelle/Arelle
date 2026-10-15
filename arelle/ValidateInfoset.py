"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from lxml import etree

from arelle.ModelDocument import Type
from arelle.ModelValue import DATETIME, dateTime, qname
from arelle.UrlUtil import ensureUrl
from arelle import XmlUtil, XbrlConst
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelObject import ModelObject
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ValidateXbrl import ValidateXbrl

_: TypeGetText


def validate(val: ValidateXbrl, modelXbrl: ModelXbrl, infosetModelXbrl: ModelXbrl) -> None:
    infoset = infosetModelXbrl.modelDocument
    if infoset.type == Type.INSTANCE:  # type: ignore[union-attr]
        # compare facts (assumed out of order)
        infosetFacts = defaultdict(list)
        for fact in infosetModelXbrl.facts:
            infosetFacts[fact.qname].append(fact)
        if len(modelXbrl.factsInInstance) != len(infosetModelXbrl.factsInInstance):
            modelXbrl.error("arelle:infosetTest",
                _("Fact counts mismatch, testcase instance %(foundFactCount)s, infoset instance %(expectedFactCount)s"),
                modelObject=(modelXbrl.modelDocument, infosetModelXbrl.modelDocument),
                            foundFactCount=len(modelXbrl.factsInInstance),
                            expectedFactCount=len(infosetModelXbrl.factsInInstance))
        else:
            for i, instFact in enumerate(modelXbrl.facts):
                infosetFact = None
                for fact in infosetFacts[instFact.qname]:
                    if fact.isTuple and fact.isDuplicateOf(instFact, deemP0Equal=True):
                        infosetFact = fact
                        break
                    elif fact.isItem and fact.isVEqualTo(instFact, deemP0Equal=True):
                        infosetFact = fact
                        break
                if infosetFact is None:  # takes precision/decimals into account
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(factNumber)s mismatch %(concept)s"),
                        modelObject=instFact,
                                    factNumber=(i + 1),
                                    concept=instFact.qname)
                else:
                    ptvPeriodType = infosetFact.get("{http://www.xbrl.org/2003/ptv}periodType")
                    ptvBalance = infosetFact.get("{http://www.xbrl.org/2003/ptv}balance")
                    ptvDecimals = infosetFact.get("{http://www.xbrl.org/2003/ptv}decimals")
                    ptvPrecision = infosetFact.get("{http://www.xbrl.org/2003/ptv}precision")
                    if ptvPeriodType and ptvPeriodType != instFact.concept.periodType:  # type: ignore[union-attr]
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s periodType mismatch %(concept)s expected %(expectedPeriodType)s found %(foundPeriodType)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedPeriodType=ptvPeriodType,
                                        foundPeriodType=instFact.concept.periodType)  # type: ignore[union-attr]
                    if ptvBalance and ptvBalance != instFact.concept.balance:  # type: ignore[union-attr]
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s balance mismatch %(concept)s expected %(expectedBalance)s found %(foundBalance)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedBalance=ptvBalance,
                                        foundBalance=instFact.concept.balance)  # type: ignore[union-attr]
                    if ptvDecimals and ptvDecimals != str(inferredDecimals(instFact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred decimals mismatch %(concept)s expected %(expectedDecimals)s found %(inferredDecimals)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedDecimals=ptvDecimals,
                                        inferredDecimals=str(inferredDecimals(instFact)))
                    if ptvPrecision and ptvPrecision != str(inferredPrecision(instFact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred precision mismatch %(concept)s expected %(expectedPrecision)s found %(inferredPrecision)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedPrecision=ptvPrecision,
                                        inferredPrecision=str(inferredPrecision(instFact)))

    elif infoset.type == Type.ARCSINFOSET:  # type: ignore[union-attr]
        # compare arcs
        for arcElt in XmlUtil.children(infoset.xmlRootElement, "http://www.xbrl.org/2003/ptv", "arc"):  # type: ignore[union-attr]
            linkType = arcElt.get("linkType")
            arcRole = arcElt.get("arcRole")
            extRole = arcElt.get("extRole")
            fromObj = resolvePath(modelXbrl, arcElt.get("fromPath"))
            if fromObj is None:
                modelXbrl.error("arelle:infosetTest",
                    _("Arc fromPath not found: %(fromPath)s"),
                    modelObject=arcElt, fromPath=arcElt.get("fromPath"))
                continue
            if linkType in ("label", "reference"):
                resRole = arcElt.get("resRole")
                if linkType == "label":
                    expectedLabel = XmlUtil.text(arcElt)
                    foundLabel = fromObj.label(  # type: ignore[attr-defined]
                        preferredLabel=resRole,
                        fallbackToQname=False,
                        lang=None,
                        strip=True,
                        linkrole=extRole,
                    )
                    if foundLabel != expectedLabel:
                        modelXbrl.error("arelle:infosetTest",
                            _("Label expected='%(expectedLabel)s', found='%(foundLabel)s'"),
                            modelObject=arcElt, expectedLabel=expectedLabel, foundLabel=foundLabel)
                    continue
                elif linkType == "reference":
                    expectedRef = XmlUtil.innerText(arcElt)
                    referenceFound = False
                    for refrel in modelXbrl.relationshipSet(XbrlConst.conceptReference,extRole).fromModelObject(fromObj):
                        ref = refrel.toModelObject
                        if resRole == ref.role:  # type: ignore[union-attr]
                            foundRef = XmlUtil.innerText(ref)  # type: ignore[arg-type]
                            if foundRef != expectedRef:
                                modelXbrl.error("arelle:infosetTest",
                                    _("Reference inner text expected='%(expectedRef)s, found='%(foundRef)s'"),
                                    modelObject=arcElt, expectedRef=expectedRef, foundRef=foundRef)
                            referenceFound = True
                            break
                    if referenceFound:
                        continue
                modelXbrl.error("arelle:infosetTest",
                    _("%(linkType)s not found containing '%(text)s' linkRole %(linkRole)s"),
                    modelObject=arcElt, linkType=linkType.title(), text=XmlUtil.innerText(arcElt), linkRole=extRole)
            else:
                toObj = resolvePath(modelXbrl, arcElt.get("toPath"))
                if toObj is None:
                    modelXbrl.error("arelle:infosetTest",
                        _("Arc toPath not found: %(toPath)s"),
                        modelObject=arcElt, toPath=arcElt.get("toPath"))
                    continue
                weight = arcElt.get("weight")
                if weight is not None:
                    weight = float(weight)  # type: ignore[assignment]
                order = arcElt.get("order")
                if order is not None:
                    order = float(order)  # type: ignore[assignment]
                found = False
                for rel in modelXbrl.relationshipSet(arcRole, extRole).fromModelObject(fromObj):  # type: ignore[arg-type]
                    if (rel.toModelObject == toObj and
                        (weight is None or rel.weight == weight) and  # type: ignore[comparison-overlap]
                        (order is None or rel.order == order)):  # type: ignore[comparison-overlap]
                        found = True
                if not found:
                    modelXbrl.error("arelle:infosetTest",
                        _("Arc not found: from %(fromPath)s, to %(toPath)s, role %(arcRole)s, linkRole %(linkRole)s"),
                        modelObject=arcElt, fromPath=arcElt.get("fromPath"), toPath=arcElt.get("toPath"), arcRole=arcRole, linkRole=extRole)
                    continue
    elif infoset.type == Type.FACTDIMSINFOSET:  # type: ignore[union-attr]
        # validate dimensions of each fact
        for itemElt in XmlUtil.children(infoset.xmlRootElement, None, "item"):  # type: ignore[union-attr]
            try:
                qnElt = XmlUtil.child(itemElt, None, "qnElement")
                factQname = qname(qnElt, XmlUtil.text(qnElt))  # type: ignore[arg-type]
                sPointer = XmlUtil.text(XmlUtil.child(itemElt, None, "sPointer"))  # type: ignore[arg-type]
                factElt: ModelObject = modelXbrl.modelDocument.xmlRootElement  # type: ignore[union-attr]
                for step in sPointer.split("/"):  # xpointer child sequence, 1-based, nested for tuple facts
                    factElt = XmlUtil.children(factElt, None, "*")[int(step) - 1]
                if factElt.qname != factQname:
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(sPointer)s mismatch Qname, expected %(qnElt)s, observed %(factQname)s"),
                        modelObject=itemElt, sPointer=sPointer, qnElt=factQname, factQname=factElt.qname)
                elif not factElt.isItem or factElt.context is None:  # type: ignore[attr-defined]
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(sPointer)s has no context: %(qnElt)s"),
                        modelObject=(itemElt,factElt), sPointer=sPointer, qnElt=factQname)
                else:
                    context = factElt.context  # type: ignore[attr-defined]
                    memberElts = XmlUtil.children(itemElt, None, "member")
                    numNonDefaults = 0
                    for memberElt in memberElts:
                        dimElt = XmlUtil.child(memberElt, None, "qnDimension")
                        qnDim = qname(dimElt, XmlUtil.text(dimElt))  # type: ignore[arg-type]
                        isDefault = XmlUtil.text(XmlUtil.child(memberElt, None, "bDefaulted")) == "true"  # type: ignore[arg-type]
                        if not isDefault:
                            numNonDefaults += 1
                        if not ((qnDim in context.qnameDims and not isDefault) or
                                (qnDim in factElt.modelXbrl.qnameDimensionDefaults and isDefault)):  # type: ignore[union-attr]
                            modelXbrl.error("arelle:infosetTest",
                                _("Fact %(sPointer)s %(qnElt)s dimension mismatch %(qnDim)s"),
                                modelObject=(itemElt, factElt, context), sPointer=sPointer, qnElt=factQname, qnDim=qnDim)
                    if numNonDefaults != len(context.qnameDims):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(sPointer)s %(qnElt)s dimensions count mismatch"),
                            modelObject=(itemElt, factElt, context), sPointer=sPointer, qnElt=factQname)
            except (IndexError, ValueError, AttributeError) as err:
                modelXbrl.error("arelle:infosetTest",
                    _("Invalid entity fact dimensions infoset sPointer: %(test)s, error details: %(error)s"),
                    modelObject=itemElt, test=XmlUtil.innerTextList(itemElt), error=str(err))


def resolvePath(modelXbrl: ModelXbrl, namespaceId: str | None) -> ModelObject | None:
    ns, sep, id = (namespaceId or "#").partition("#")
    docs = modelXbrl.namespaceDocs.get(ns)
    if docs: # a list of schema modelDocs with this namespace
        doc = docs[0]
        if id in doc.idObjects:
            return doc.idObjects[id]
    return None


TABLE_MODEL_CELL = f"{{{XbrlConst.tableModel}}}cell"
TABLE_MODEL_CONSTRAINT = f"{{{XbrlConst.tableModel}}}constraint"
TABLE_MODEL_FACT = f"{{{XbrlConst.tableModel}}}fact"
TABLE_MODEL_HEADERS = f"{{{XbrlConst.tableModel}}}headers"
TABLE_MODEL_TABLE = f"{{{XbrlConst.tableModel}}}table"
PERIOD_DATE_TAGS = {XbrlConst.qnXbrliStartDate.clarkNotation, XbrlConst.qnXbrliEndDate.clarkNotation, XbrlConst.qnXbrliInstant.clarkNotation}
# Concept and explicit dimension values and unit measures hold QNames. Other text, such as an entity identifier, is literal.
QNAME_VALUE_TAGS = {f"{{{XbrlConst.tableModel}}}value", f"{{{XbrlConst.xbrli}}}measure"}
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
IGNORED_LAYOUT_ATTRIBUTES = {XML_BASE}

@dataclass(frozen=True)
class CanonicalElement:
    tag: str
    attributes: tuple[tuple[str, str], ...]
    text: str
    children: tuple[CanonicalElement, ...]


@dataclass(frozen=True)
class CanonicalConstraint:
    aspect: str
    tag: str
    value: CanonicalElement | None


def _childElements(elt: etree._Element) -> list[etree._Element]:
    return list(elt.iterchildren(etree.Element))


def _qnameOrText(elt: etree._Element, text: str) -> str:
    qn = qname(text, elt.nsmap, noPrefixIsNoNamespace=True)
    return text if qn is None else qn.clarkNotation


def _periodDateTime(elt: etree._Element, text: str) -> str:
    # Date only end dates and instants mean the end of that day. Expected outputs mix Z and no time zone.
    value = dateTime(text.replace("Z", ""), addOneDay=elt.tag != XbrlConst.qnXbrliStartDate.clarkNotation, type=DATETIME)
    return text if value is None else datetime.datetime.isoformat(value)


def _factLocation(factElt: etree._Element, documentUri: str) -> str:
    uri = ensureUrl(documentUri)
    for elt in [*reversed(list(factElt.iterancestors())), factElt]:
        if xmlBase := elt.get(XML_BASE):
            uri = urljoin(uri, xmlBase)
    return urljoin(uri, (factElt.text or "").strip())


def _canonicalValue(elt: etree._Element) -> CanonicalElement:
    text = (elt.text or "").strip()
    if elt.tag in PERIOD_DATE_TAGS:
        text = _periodDateTime(elt, text)
    elif elt.tag in QNAME_VALUE_TAGS:
        text = _qnameOrText(elt, text)
    attrs = tuple(sorted((str(k), str(v)) for k, v in elt.items()))
    return CanonicalElement(str(elt.tag), attrs, text, tuple(_canonicalValue(child) for child in _childElements(elt)))


def _canonicalConstraint(constraintElt: etree._Element) -> CanonicalConstraint:
    aspectElt = constraintElt.find(f"{{{XbrlConst.tableModel}}}aspect")
    valueElt = constraintElt.find(f"{{{XbrlConst.tableModel}}}value")
    aspect = "" if aspectElt is None else _qnameOrText(aspectElt, (aspectElt.text or "").strip())
    value = None if valueElt is None else _canonicalValue(valueElt)
    return CanonicalConstraint(aspect, constraintElt.get("tag", ""), value)


def _layoutChildren(elt: etree._Element) -> list[etree._Element]:
    children = _childElements(elt)
    if elt.tag == TABLE_MODEL_TABLE:
        # Header order across axes is not significant.
        headers = sorted((child for child in children if child.tag == TABLE_MODEL_HEADERS), key=lambda child: child.get("axis", ""))
        others = [child for child in children if child.tag != TABLE_MODEL_HEADERS]
        children = headers + others
    elif elt.tag == TABLE_MODEL_CELL:
        children = [child for child in children if child.tag != TABLE_MODEL_CONSTRAINT]
    return children


def _layoutAttributes(elt: etree._Element) -> dict[str, str]:
    attrs = {k: v for k, v in elt.items() if k not in IGNORED_LAYOUT_ATTRIBUTES}
    if elt.tag == TABLE_MODEL_CELL:
        # The layout model schema defaults span to 1 and rollup to false, and Arelle omits both defaults.
        span = attrs.get("span", "1").strip()
        attrs["span"] = str(int(span)) if span.lstrip("+").isdigit() else span
        rollup = attrs.get("rollup", "false").strip()
        attrs["rollup"] = {"1": "true", "0": "false"}.get(rollup, rollup)
    return attrs


def compareRenderingInfosetElts(
        modelXbrl: ModelXbrl,
        sourceElt: etree._Element,
        comparisonElt: etree._Element,
        sourceDocumentUri: str,
        comparisonDocumentUri: str
    ) -> None:
    sourcePath = sourceElt.getroottree().getpath(sourceElt)
    if sourceElt.tag != comparisonElt.tag:
        modelXbrl.error("arelle:tableModelElementMismatch",
            _("Table layout model expecting %(elt2)s found %(elt1)s source path %(elt1path)s comparison line %(elt2line)s path %(elt2path)s, srcElt %(elt1xml)s cmpElt %(elt2xml)s"),
            modelObject=modelXbrl, elt1=sourceElt.tag, elt2=comparisonElt.tag,
            elt1path=sourcePath, elt2path=comparisonElt.getroottree().getpath(comparisonElt),
            elt2line=comparisonElt.sourceline,
            elt1xml=etree.tostring(sourceElt),elt2xml=etree.tostring(comparisonElt))
        return
    sourceAttrs = _layoutAttributes(sourceElt)
    comparisonAttrs = _layoutAttributes(comparisonElt)
    if sourceAttrs != comparisonAttrs:
        modelXbrl.error("arelle:tableModelAttributesMismatch",
            _("Table layout model comparison element %(elt)s expecting attributes %(attrs2)s found %(attrs1)s source path %(elt1path)s comparison line %(elt2line)s"),
            modelObject=modelXbrl, elt=sourceElt.tag,
            attrs1=", ".join('{0}="{1}"'.format(k, v) for k, v in sorted(sourceAttrs.items())),
            attrs2=", ".join('{0}="{1}"'.format(k, v) for k, v in sorted(comparisonAttrs.items())),
            elt1path=sourcePath, elt2line=comparisonElt.sourceline)
    if sourceElt.tag == TABLE_MODEL_CELL:
        sourceConstraints = [_canonicalConstraint(c) for c in sourceElt.iterchildren(TABLE_MODEL_CONSTRAINT)]
        comparisonConstraints = [_canonicalConstraint(c) for c in comparisonElt.iterchildren(TABLE_MODEL_CONSTRAINT)]
        if Counter(sourceConstraints) != Counter(comparisonConstraints):
            modelXbrl.error("arelle:tableModelConstraintsMismatch",
                _("Table layout model constraints %(src)s expecting %(cmp)s source path %(elt1path)s comparison line %(elt2line)s path %(elt2path)s"),
                modelObject=modelXbrl, src=",".join(str(s) for s in sourceConstraints), cmp=",".join(str(c) for c in comparisonConstraints),
                elt1path=sourcePath, elt2path=comparisonElt.getroottree().getpath(comparisonElt),
                elt2line=comparisonElt.sourceline)
    sourceChildren = _layoutChildren(sourceElt)
    comparisonChildren = _layoutChildren(comparisonElt)
    if not sourceChildren and not comparisonChildren:
        sourceText = (sourceElt.text or "").strip()
        comparisonText = (comparisonElt.text or "").strip()
        if sourceElt.tag == TABLE_MODEL_FACT:
            sourceText = _factLocation(sourceElt, sourceDocumentUri)
            comparisonText = _factLocation(comparisonElt, comparisonDocumentUri)
        if sourceText != comparisonText:
            modelXbrl.error("arelle:tableModelTextMismatch",
                _("Table layout model comparison element %(elt)s expecting text %(text2)s found %(text1)s source path %(elt1path)s comparison line %(elt2line)s"),
                modelObject=modelXbrl, elt=sourceElt.tag, text1=sourceText or "(none)", text2=comparisonText or "(none)",
                elt1path=sourcePath, elt2line=comparisonElt.sourceline)
    if len(sourceChildren) != len(comparisonChildren):
        modelXbrl.error("arelle:tableModelChildCountMismatch",
            _("Table layout model comparison element %(elt)s expecting %(count2)s child elements found %(count1)s source path %(elt1path)s comparison line %(elt2line)s"),
            modelObject=modelXbrl, elt=sourceElt.tag, count1=len(sourceChildren), count2=len(comparisonChildren),
            elt1path=sourcePath, elt2line=comparisonElt.sourceline)
    for sourceChild, comparisonChild in zip(sourceChildren, comparisonChildren):
        compareRenderingInfosetElts(modelXbrl, sourceChild, comparisonChild, sourceDocumentUri, comparisonDocumentUri)


def validateRenderingInfoset(modelXbrl: ModelXbrl, comparisonFile: str, sourceDoc: etree._ElementTree) -> None:
    try:
        # etree.parse does not successfully parse files within archives
        if modelXbrl.fileSource.isInArchive(comparisonFile):
            file, encoding = modelXbrl.fileSource.file(comparisonFile)  # type: ignore[misc]
            comparisonDoc = etree.parse(file)
        else:
            comparisonDoc = etree.parse(comparisonFile)
        assert modelXbrl.modelDocument is not None
        compareRenderingInfosetElts(modelXbrl, sourceDoc.getroot(), comparisonDoc.getroot(), modelXbrl.modelDocument.uri, comparisonFile)
    except (IOError, etree.LxmlError) as err:
        modelXbrl.error("arelle:tableModelFileError",
            _("Table layout model comparison file %(xmlfile)s error %(error)s"),
            modelObject=modelXbrl, xmlfile=comparisonFile, error=str(err))
