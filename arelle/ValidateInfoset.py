"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from lxml import etree

from arelle.ModelDocument import Type
from arelle.ModelValue import qname, dateTime, DateTime
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
                    if fact is not None:
                        fact.isVEqualTo(instFact, deemP0Equal=True)
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
                    if ptvDecimals and ptvDecimals != str(inferredDecimals(fact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred decimals mismatch %(concept)s expected %(expectedDecimals)s found %(inferredDecimals)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedDecimals=ptvDecimals,
                                        inferredDecimals=str(inferredDecimals(fact)))
                    if ptvPrecision and ptvPrecision != str(inferredPrecision(fact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred precision mismatch %(concept)s expected %(expectedPrecision)s found %(inferredPrecision)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i + 1),
                                        concept=instFact.qname,
                                        expectedPrecisions=ptvPrecision,
                                        inferredPrecision=str(inferredPrecision(fact)))

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
                        _("Arc not found: from %(fromPath)s, to %(toPath)s, role %(arcRole)s, linkRole $(extRole)s"),
                        modelObject=arcElt, fromPath=arcElt.get("fromPath"), toPath=arcElt.get("toPath"), arcRole=arcRole, linkRole=extRole)
                    continue
        # validate dimensions of each fact
        factElts = XmlUtil.children(modelXbrl.modelDocument.xmlRootElement, None, "*")  # type: ignore[union-attr]
        for itemElt in XmlUtil.children(infoset.xmlRootElement, None, "item"):  # type: ignore[union-attr]
            try:
                qnElt = XmlUtil.child(itemElt, None, "qnElement")
                factQname = qname(qnElt, XmlUtil.text(qnElt))  # type: ignore[arg-type]
                sPointer = int(XmlUtil.child(itemElt, None, "sPointer").text)  # type: ignore[arg-type,union-attr]
                factElt = factElts[sPointer - 1]  # 1-based xpath indexing
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
                                _("Fact %(sPointer)s (qnElt)s dimension mismatch %(qnDim)s"),
                                modelObject=(itemElt, factElt, context), sPointer=sPointer, qnElt=factQname, qnDim=qnDim)
                    if numNonDefaults != len(context.qnameDims):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(sPointer)s (qnElt)s dimensions count mismatch"),
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


def stripTime(periodAspect: Iterable[str | None]) -> tuple[DateTime | None, ...]:
    a = [t for t in periodAspect if t]
    p = []
    if len(a) > 1:
        p.append(dateTime(a[0].replace("Z","")))
    if len(a) > 0:
        p.append(dateTime(a[-1].replace("Z", ""), addOneDay=True))
    return tuple(p)


def compareRenderingInfosetElts(
        modelXbrl: ModelXbrl,
        sourceElt: etree._Element | None,
        comparisonElt: etree._Element | None
    ) -> None:
    sourceEltTag = sourceElt.tag if sourceElt is not None else "(no more elements)"
    comparisonEltTag = comparisonElt.tag if comparisonElt is not None else "(no more elements)"
    if sourceEltTag != comparisonEltTag:
        modelXbrl.error("arelle:tableModelElementMismatch",
            _("Table layout model expecting %(elt1)s found %(elt2)s source path %(elt1path)s comparison line %(elt2line)s path %(elt2path)s, srcElt %(elt1xml)s cmpElt %(elt2xml)s"),
            modelObject=modelXbrl, elt1=sourceEltTag, elt2=comparisonEltTag,
            elt1path=sourceElt.getroottree().getpath(sourceElt), elt2path=comparisonElt.getroottree().getpath(comparisonElt),  # type: ignore[arg-type,union-attr]
            elt2line=comparisonElt.sourceline,  # type: ignore[union-attr]
            elt1xml=etree.tostring(sourceElt),elt2xml=etree.tostring(comparisonElt))  # type: ignore[arg-type]
    elif sourceEltTag == "{http://xbrl.org/2014/table/model}cell":
        ceSrcIter = sourceElt.iter("{http://xbrl.org/2014/table/model}fact",  # type: ignore[union-attr]
                                   "{http://xbrl.org/2014/table/model}label")
        ceCmpIter = comparisonElt.iter("{http://xbrl.org/2014/table/model}fact",  # type: ignore[union-attr]
                                       "{http://xbrl.org/2014/table/model}label")
        ceSrcElt = next(ceSrcIter, None)
        ceCmpElt = next(ceCmpIter, None)
        while ceSrcElt is not None and ceCmpElt is not None:
            compareRenderingInfosetElts(modelXbrl, ceSrcElt, ceCmpElt)
            ceSrcElt = next(ceSrcIter, None)
            ceCmpElt = next(ceCmpIter, None)
        srcConstraints: dict[tuple[str, str], tuple[str, ...]] = {}
        cmpConstraints: dict[tuple[str, str], tuple[str, ...]] = {}
        for srcE, cstrts in ((sourceElt, srcConstraints), (comparisonElt, cmpConstraints)):
            for e in srcE.iter("{http://xbrl.org/2014/table/model}constraint"):  # type: ignore[union-attr]
                cstrtTag = e.get("tag", "")
                cstrtAspect = e.findtext("{http://xbrl.org/2014/table/model}aspect")
                if cstrtAspect:
                    if e.find("{http://xbrl.org/2014/table/model}value") is None:
                        cstrts[cstrtAspect, cstrtTag] = ()
                    else:
                        cstrts[cstrtAspect, cstrtTag] = tuple((f.text or "").strip() for f in e.find("{http://xbrl.org/2014/table/model}value") for f in e.iter())  # type: ignore[union-attr]
        for c in (srcConstraints, cmpConstraints):
            for k, v in c.items():
                if isinstance(k, tuple) and k[0] == "period":
                    # remove end dates time parts if zero (because not consistently reported in conf suite expected outputs)
                    c[k] = stripTime(c[k])  # type: ignore[assignment]
        if srcConstraints != cmpConstraints:
            modelXbrl.error("arelle:tableModelConstraintsMismatch",
                _("Table layout model constraints %(src)s expecting %(cmp)s source path %(elt1path)s comparison line %(elt2line)s path %(elt2path)s"),
                modelObject=modelXbrl, src=",".join(str(s) for s in sorted(srcConstraints.items())), cmp=",".join(str(s) for s in sorted(cmpConstraints.items())),
                elt1path=sourceElt.getroottree().getpath(sourceElt), elt2path=comparisonElt.getroottree().getpath(comparisonElt),  # type: ignore[arg-type,union-attr]
                elt2line=comparisonElt.sourceline)  # type: ignore[union-attr]
    else:
        text1 = (sourceElt.text or "").strip() or "(none)"  # type: ignore[union-attr]
        text2 = (comparisonElt.text or "").strip() or "(none)"  # type: ignore[union-attr]
        if text1 != text2:
            modelXbrl.error("arelle:tableModelTextMismatch",
                _("Table layout model comparison element %(elt)s expecting text %(text1)s found %(text2)s source line %(elt1line)s comparison line %(elt2line)s"),
                modelObject=modelXbrl, elt=sourceElt.tag, text1=text1, text2=text2,  # type: ignore[union-attr]
                elt1line=sourceElt.sourceline, elt2line=comparisonElt.sourceline)  # type: ignore[union-attr]
        attrs1 = dict(sourceElt.items())  # type: ignore[union-attr]
        attrs2 = dict(comparisonElt.items())  # type: ignore[union-attr]
        # remove attributes not to be compared
        for attr in ("{http://www.w3.org/XML/1998/namespace}base",):
            if attr in attrs1: del attrs1[attr]
            if attr in attrs2: del attrs2[attr]
        if attrs1 != attrs2:
            modelXbrl.error("arelle:tableModelAttributesMismatch",
                _("Table layout model comparison element %(elt)s expecting attributes %(attrs1)s found %(attrs2)s source line %(elt1line)s comparison line %(elt2line)s"),
                modelObject=modelXbrl, elt=sourceElt.tag,  # type: ignore[union-attr]
                attrs1=", ".join('{0}="{1}"'.format(k, v) for k, v in sorted(attrs1.items())),
                attrs2=", ".join('{0}="{1}"'.format(k, v) for k, v in sorted(attrs2.items())),
                elt1line=sourceElt.sourceline, elt2line=comparisonElt.sourceline)  # type: ignore[union-attr]


def validateRenderingInfoset(modelXbrl: ModelXbrl, comparisonFile: str, sourceDoc: etree._ElementTree) -> None:
    try:
        # etree.parse does not successfully parse files within archives
        if modelXbrl.fileSource.isInArchive(comparisonFile):
            file, encoding = modelXbrl.fileSource.file(comparisonFile)  # type: ignore[misc]
            comparisonDoc = etree.parse(file)
        else:
            comparisonDoc = etree.parse(comparisonFile)
        # uncomment to debug when layout model corrupted after creation
        # with open("/Users/hermf/temp/temp2.xml", "wb") as fh:
        #     fh.write(etree.tostring(sourceDoc, pretty_print=True))
        numSrcTblElts = len(sourceDoc.findall(".//{http://xbrl.org/2014/table/model}table"))
        numCmpTblElts = len(comparisonDoc.findall(".//{http://xbrl.org/2014/table/model}table"))
        if numSrcTblElts != numCmpTblElts:
            modelXbrl.error("arelle:tableModelNumberOfTables",
                _("Table layout model comparison expects %(numCmpTblElts)s table elements, layout has %(numSrcTblElts)s table elements"),
                modelObject=modelXbrl, numSrcTblElts=numSrcTblElts, numCmpTblElts=numCmpTblElts)
        if False: # numCmpTblElts > 1 and comparisonFile.endswith("linkrole-parameter.xml"):
            # reverse tables for this test case
            tblElts = sourceDoc.findall(".//{http://xbrl.org/2014/table/model}table")
            tblElts[0].addprevious(tblElts[1])
        # order comparison document headers in z - y - x order
        headerElts = comparisonDoc.findall(".//{http://xbrl.org/2014/table/model}headers")
        if len(headerElts) == 3:
            if headerElts[0].get("axis") == "y" and headerElts[2].get("axis") == "z":
                headerElts[0].addprevious(headerElts[2])
        sourceIter = sourceDoc.iter()
        comparisonIter = comparisonDoc.iter()
        sourceElt = next(sourceIter, None)
        comparisonElt = next(comparisonIter, None)
        # skip over nsmap elements used to create output trees
        while sourceElt is not None and sourceElt.tag == "nsmap":
            sourceElt = next(sourceIter, None)
        while comparisonElt is not None and sourceElt.tag == "nsmap":  # type: ignore[union-attr]
            comparisonElt = next(comparisonIter, None)
        while sourceElt is not None and comparisonElt is not None:
            while isinstance(sourceElt, etree._Comment):
                sourceElt = next(sourceIter, None)
            while isinstance(comparisonElt, etree._Comment):
                comparisonElt = next(comparisonIter, None)
            if sourceElt is None or not any(e is not None for e in sourceElt.iterancestors("{http://xbrl.org/2014/table/model}cell")):
                compareRenderingInfosetElts(modelXbrl, sourceElt, comparisonElt)
            sourceElt = next(sourceIter, None)
            comparisonElt = next(comparisonIter, None)
        # option to save sourceDoc when errors detected
        # numErrorsAtStart = len(modelXbrl.errors)
        # if len(modelXbrl.errors) > numErrorsAtStart:
        #     with io.open("/Users/hermf/temp/temp/" + os.path.basename(comparisonFile), "wb") as fh:
        #         fh.write(etree.tostring(sourceDoc, encoding="utf-8", pretty_print=True))
    except (IOError, etree.LxmlError) as err:
        modelXbrl.error("arelle:tableModelFileError",
            _("Table layout model comparison file %(xmlfile)s error %(error)s"),
            modelObject=modelXbrl, xmlfile=comparisonFile, error=str(err))
