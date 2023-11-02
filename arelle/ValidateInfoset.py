'''
See COPYRIGHT.md for copyright information.
'''
from collections import defaultdict
from arelle.ModelDocument import Type
from arelle.ModelValue import qname
from arelle import XmlUtil, XbrlConst
from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals

def validate(val, modelXbrl, infosetModelXbrl):
    infoset = infosetModelXbrl.modelDocument
    if infoset.type == Type.INSTANCE:
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
                if infosetFact is None: # takes precision/decimals into account
                    if fact is not None:
                        fact.isVEqualTo(instFact, deemP0Equal=True)
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(factNumber)s mismatch %(concept)s"),
                        modelObject=instFact,
                                    factNumber=(i+1),
                                    concept=instFact.qname)
                else:
                    ptvPeriodType = infosetFact.get("{http://www.xbrl.org/2003/ptv}periodType")
                    ptvBalance = infosetFact.get("{http://www.xbrl.org/2003/ptv}balance")
                    ptvDecimals = infosetFact.get("{http://www.xbrl.org/2003/ptv}decimals")
                    ptvPrecision = infosetFact.get("{http://www.xbrl.org/2003/ptv}precision")
                    if ptvPeriodType and ptvPeriodType != instFact.concept.periodType:
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s periodType mismatch %(concept)s expected %(expectedPeriodType)s found %(foundPeriodType)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i+1),
                                        concept=instFact.qname,
                                        expectedPeriodType=ptvPeriodType,
                                        foundPeriodType=instFact.concept.periodType)
                    if ptvBalance and ptvBalance != instFact.concept.balance:
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s balance mismatch %(concept)s expected %(expectedBalance)s found %(foundBalance)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i+1),
                                        concept=instFact.qname,
                                        expectedBalance=ptvBalance,
                                        foundBalance=instFact.concept.balance)
                    if ptvDecimals and ptvDecimals != str(inferredDecimals(fact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred decimals mismatch %(concept)s expected %(expectedDecimals)s found %(inferredDecimals)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i+1),
                                        concept=instFact.qname,
                                        expectedDecimals=ptvDecimals,
                                        inferredDecimals=str(inferredDecimals(fact)))
                    if ptvPrecision and ptvPrecision != str(inferredPrecision(fact)):
                        modelXbrl.error("arelle:infosetTest",
                            _("Fact %(factNumber)s inferred precision mismatch %(concept)s expected %(expectedPrecision)s found %(inferredPrecision)s"),
                            modelObject=(instFact, infosetFact),
                                        factNumber=(i+1),
                                        concept=instFact.qname,
                                        expectedPrecisions=ptvPrecision,
                                        inferredPrecision=str(inferredPrecision(fact)))

    elif infoset.type == Type.ARCSINFOSET:
        # compare arcs
        for arcElt in XmlUtil.children(infoset.xmlRootElement, "http://www.xbrl.org/2003/ptv", "arc"):
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
                labelLang = arcElt.get("labelLang")
                resRole = arcElt.get("resRole")
                if linkType == "label":
                    expectedLabel = XmlUtil.text(arcElt)
                    foundLabel = fromObj.label(preferredLabel=resRole,fallbackToQname=False,lang=None,strip=True,linkrole=extRole)
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
                        if resRole == ref.role:
                            foundRef = XmlUtil.innerText(ref)
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
                    weight = float(weight)
                order = arcElt.get("order")
                if order is not None:
                    order = float(order)
                preferredLabel = arcElt.get("preferredLabel")
                found = False
                for rel in modelXbrl.relationshipSet(arcRole, extRole).fromModelObject(fromObj):
                    if (rel.toModelObject == toObj and
                        (weight is None or rel.weight == weight) and
                        (order is None or rel.order == order)):
                        found = True
                if not found:
                    modelXbrl.error("arelle:infosetTest",
                        _("Arc not found: from %(fromPath)s, to %(toPath)s, role %(arcRole)s, linkRole $(extRole)s"),
                        modelObject=arcElt, fromPath=arcElt.get("fromPath"), toPath=arcElt.get("toPath"), arcRole=arcRole, linkRole=extRole)
                    continue
        # validate dimensions of each fact
        factElts = XmlUtil.children(modelXbrl.modelDocument.xmlRootElement, None, "*")
        for itemElt in XmlUtil.children(infoset.xmlRootElement, None, "item"):
            try:
                qnElt = XmlUtil.child(itemElt,None,"qnElement")
                factQname = qname(qnElt, XmlUtil.text(qnElt))
                sPointer = int(XmlUtil.child(itemElt,None,"sPointer").text)
                factElt = factElts[sPointer - 1] # 1-based xpath indexing
                if factElt.qname != factQname:
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(sPointer)s mismatch Qname, expected %(qnElt)s, observed %(factQname)s"),
                        modelObject=itemElt, sPointer=sPointer, qnElt=factQname, factQname=factElt.qname)
                elif not factElt.isItem or factElt.context is None:
                    modelXbrl.error("arelle:infosetTest",
                        _("Fact %(sPointer)s has no context: %(qnElt)s"),
                        modelObject=(itemElt,factElt), sPointer=sPointer, qnElt=factQname)
                else:
                    context = factElt.context
                    memberElts = XmlUtil.children(itemElt,None,"member")
                    numNonDefaults = 0
                    for memberElt in memberElts:
                        dimElt = XmlUtil.child(memberElt, None, "qnDimension")
                        qnDim = qname(dimElt, XmlUtil.text(dimElt))
                        isDefault = XmlUtil.text(XmlUtil.child(memberElt, None, "bDefaulted")) == "true"
                        if not isDefault:
                            numNonDefaults += 1
                        if not ((qnDim in context.qnameDims and not isDefault) or
                                (qnDim in factElt.modelXbrl.qnameDimensionDefaults and isDefault)):
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

def resolvePath(modelXbrl, namespaceId):
    ns, sep, id = (namespaceId or "#").partition("#")
    docs = modelXbrl.namespaceDocs.get(ns)
    if docs: # a list of schema modelDocs with this namespace
        doc = docs[0]
        if id in doc.idObjects:
            return doc.idObjects[id]
    return None

def validateRenderingInfoset(modelXbrl, comparisonFile, sourceDoc):
    from lxml import etree
    try:
        # etree.parse does not successfully parse files within archives
        if modelXbrl.fileSource.isInArchive(comparisonFile):
            file, encoding = modelXbrl.fileSource.file(comparisonFile)
            comparisonDoc = etree.parse(file)
        else:
            comparisonDoc = etree.parse(comparisonFile)
        sourceIter = sourceDoc.iter()
        comparisonIter = comparisonDoc.iter()
        sourceElt = next(sourceIter, None)
        comparisonElt = next(comparisonIter, None)
        # skip over nsmap elements used to create output trees
        while (sourceElt is not None and sourceElt.tag == "nsmap"):
            sourceElt = next(sourceIter, None)
        while (comparisonElt is not None and sourceElt.tag == "nsmap"):
            comparisonElt = next(comparisonIter, None)
        while (sourceElt is not None and comparisonElt is not None):
            while (isinstance(sourceElt, etree._Comment)):
                sourceElt = next(sourceIter, None)
            while (isinstance(comparisonElt, etree._Comment)):
                comparisonElt = next(comparisonIter, None)
            sourceEltTag = sourceElt.tag if sourceElt is not None else '(no more elements)'
            comparisonEltTag = comparisonElt.tag if comparisonElt is not None else '(no more elements)'
            if sourceEltTag != comparisonEltTag:
                modelXbrl.error("arelle:tableModelElementMismatch",
                    _("Table model expecting %(elt1)s found %(elt2)s source line %(elt1line)s comparison line %(elt2line)s"),
                    modelObject=modelXbrl, elt1=sourceEltTag, elt2=comparisonEltTag,
                    elt1line=sourceElt.sourceline, elt2line=comparisonElt.sourceline)
            else:
                text1 = (sourceElt.text or '').strip() or '(none)'
                text2 = (comparisonElt.text or '').strip() or '(none)'
                if text1 != text2:
                    modelXbrl.error("arelle:tableModelTextMismatch",
                        _("Table model comparison element %(elt)s expecting text %(text1)s found %(text2)s source line %(elt1line)s comparison line %(elt2line)s"),
                        modelObject=modelXbrl, elt=sourceElt.tag, text1=text1, text2=text2,
                        elt1line=sourceElt.sourceline, elt2line=comparisonElt.sourceline)
                attrs1 = dict(sourceElt.items())
                attrs2 = dict(comparisonElt.items())
                # remove attributes not to be compared
                for attr in ("{http://www.w3.org/XML/1998/namespace}base",
                             ):
                    if attr in attrs1: del attrs1[attr]
                    if attr in attrs2: del attrs2[attr]
                if attrs1 != attrs2:
                    modelXbrl.error("arelle:tableModelAttributesMismatch",
                        _("Table model comparison element %(elt)s expecting attributes %(attrs1)s found %(attrs2)s source line %(elt1line)s comparison line %(elt2line)s"),
                        modelObject=modelXbrl, elt=sourceElt.tag,
                        attrs1=', '.join('{0}="{1}"'.format(k,v) for k,v in sorted(attrs1.items())),
                        attrs2=', '.join('{0}="{1}"'.format(k,v) for k,v in sorted(attrs2.items())),
                        elt1line=sourceElt.sourceline, elt2line=comparisonElt.sourceline)
            sourceElt = next(sourceIter, None)
            comparisonElt = next(comparisonIter, None)
    except (IOError, etree.LxmlError) as err:
        modelXbrl.error("arelle:tableModelFileError",
            _("Table model comparison file %(xmlfile)s error %(error)s"),
            modelObject=modelXbrl, xmlfile=comparisonFile, error=str(err))
