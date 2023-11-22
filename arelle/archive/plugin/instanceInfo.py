'''
instanceInfo.py provides information about an XBRL instance

See COPYRIGHT.md for copyright information.

Operation with arelleCmdLine: --plugin instanceInfo -f entryUrl

'''
import sys, os, time, math, logging
import regex as re
from math import isnan
from collections import defaultdict
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue
from arelle import ModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import xhtml
from arelle.XmlUtil import ancestors, xmlstring

memoryAtStartup = 0
timeAtStart = 0
styleIxHiddenPattern = re.compile(r"(.*[^\w]|^)-(sec|esef)-ix-hidden\s*:\s*([\w.-]+).*")

def startup(cntlr, options, *args, **kwargs):
    global memoryAtStartup, timeAtStart
    memoryAtStartup = cntlr.memoryUsed
    timeAtStart = time.time()



def showInfo(cntlr, options, modelXbrl, _entrypoint, *args, **kwargs):
    for url, doc in sorted(modelXbrl.urlDocs.items(), key=lambda i: i[0]):
        if not any(url.startswith(w) for w in ("https://xbrl.sec.gov/", "http://xbrl.sec.gov/", "http://xbrl.fasb.org/", "http://www.xbrl.org/",
                                               "http://xbrl.ifrs.org/", "http://www.esma.europa.eu/")):
            if os.path.exists(doc.filepath): # skip if in an archive or stream
                cntlr.addToLog("File {} size {:,}".format(doc.basename, os.path.getsize(doc.filepath)), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Heap memory before loading {:,}".format(memoryAtStartup), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Heap memory after loading {:,}".format(cntlr.memoryUsed), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Time to load {:.2f} seconds".format(time.time() - timeAtStart), messageCode="info", level=logging.DEBUG)
    isInlineXbrl = modelXbrl.modelDocument.type in (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET)
    if isInlineXbrl:
        instanceType = "inline XBRL, number of documents {}".format(len(modelXbrl.ixdsHtmlElements))
    else:
        instanceType = "xBRL-XML"
    cntlr.addToLog("Instance type {}".format(instanceType), messageCode="info", level=logging.DEBUG)
    numContexts = len(modelXbrl.contexts)
    numLongContexts = 0
    bytesSaveableInline = 0
    bytesSaveableInlineWithCsv = 0
    frequencyOfDims = {}
    sumNumDims = 0
    distinctDurations = set()
    distinctInstants = set()
    shortContextIdLen = int(math.log10(numContexts or 1)) + 2 # if no contexts, use 1 for log function to work
    xbrlQnameCountInline = 0
    xbrlQnameCountInlineWithCsv = 0
    xbrlQnameLengthsInline = 0
    xbrlQnameLengthsInlineWithCsv = 0
    for c in modelXbrl.contexts.values():
        sumNumDims += len(c.qnameDims)
        for d in c.qnameDims.values():
            dimQname = str(d.dimensionQname)
            frequencyOfDims[dimQname] = frequencyOfDims.get(dimQname,0) + 1
            xbrlQnameCountInline += 1
            xbrlQnameCountInlineWithCsv += 1
            xbrlQnameLengthsInline += len(d.dimensionQname.localName)
            xbrlQnameLengthsInlineWithCsv += len(d.dimensionQname.localName)
        if c.isInstantPeriod:
            distinctInstants.add(c.instantDatetime)
        elif c.isStartEndPeriod:
            distinctDurations.add((c.startDatetime, c.endDatetime))
        if len(c.id) > shortContextIdLen:
            bytesSaveableInline += len(c.id) - shortContextIdLen
            bytesSaveableInlineWithCsv += len(c.id) - shortContextIdLen
    cntlr.addToLog("Number of contexts {:,}".format(numContexts), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of distinct durations {:,}".format(len(distinctDurations)), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of distinct instants {:,}".format(len(distinctInstants)), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Avg number dimensions per contexts {:,.2f}".format(sumNumDims/numContexts if numContexts else 0), messageCode="info", level=logging.DEBUG)
    mostPopularDims = sorted(frequencyOfDims.items(), key=lambda i:"{:0>9},{}".format(999999999-i[1],i[0]))
    for dimName, count in mostPopularDims[0:3]:
        cntlr.addToLog("Dimension {} used in {:,} contexts".format(dimName, count), messageCode="info", level=logging.DEBUG)

    # analyze for tables which could be composed from CSV data
    tblFacts = defaultdict(set)
    tblNestedTables = defaultdict(set)
    factSize = {}
    for f in modelXbrl.factsInInstance:
        for tdElt in ancestors(f, xhtml, "td"):
            factSize[f] = len(xmlstring(tdElt,stripXmlns=True))
            break
        childTblElt = None
        for tblElt in ancestors(f, xhtml, "table"):
            tblFacts[tblElt].add(f)
            if childTblElt:
                tblNestedTables[tblElt].add(childTblElt)

    # find tables containing only numeric facts
    def tblNestedFactCount(tbl):
        c = len(tblFacts.get(tbl, ()))
        for nestedTbl in tblNestedTables.get(tbl,()):
            c += tblNestedFactCount(nestedTbl)
        return c

    factsInInstance = len(modelXbrl.factsInInstance)
    factsInTables = len(set.union(*(fset for fset in tblFacts.values())))
    cntlr.addToLog("Facts in instance: {:,}, facts in tables: {:,}".format(factsInInstance,factsInTables), messageCode="info", level=logging.DEBUG)

    numTblsEligible = 0
    numFactsEligible = 0
    bytesCsvSavings = 0
    factsEligibleForCsv = set()
    tablesWithEligibleFacts = set()
    if tblFacts and factSize:
        # find eligible tables, have facts and not nested tables with other facts
        for tbl, facts in tblFacts.items():
            if len(facts) == tblNestedFactCount(tbl):
                s = sum(factSize.get(f,0) for f in facts) - sum(len(str(f.value)) for f in facts)
                if s > 10000:
                    numTblsEligible += 1
                    bytesCsvSavings += s
                    numFactsEligible += len(facts)
                    factsEligibleForCsv |= facts
                    tablesWithEligibleFacts.add(tbl)
    numFacts = 0
    numTableTextBlockFacts = 0
    lenTableTextBlockFacts = 0
    numTextBlockFacts = 0
    lenTextBlockFacts = 0
    distinctElementsInFacts = set()
    factsPerContext = {}
    factForConceptContextUnitHash = defaultdict(list)
    for f in modelXbrl.factsInInstance:
        context = f.context
        concept = f.concept
        distinctElementsInFacts.add(f.qname)
        numFacts += 1
        if f.qname.localName.endswith("TableTextBlock"):
            numTableTextBlockFacts += 1
            lenTableTextBlockFacts += len(f.xValue)
        elif f.qname.localName.endswith("TextBlock"):
            numTextBlockFacts += 1
            lenTextBlockFacts += len(f.xValue)
        if context is not None and concept is not None:
            factsPerContext[context.id] = factsPerContext.get(context.id,0) + 1
            factForConceptContextUnitHash[f.conceptContextUnitHash].append(f)
            bytesSaveableInline += len(context.id) - shortContextIdLen
            if f not in factsEligibleForCsv:
                bytesSaveableInlineWithCsv += len(context.id) - shortContextIdLen


    if numTblsEligible:
        cntlr.addToLog("Tables eligible for facts in CSV: {:,}, facts eligible for CSV: {:,}, bytes saveable by facts in CSV {:,}".format(numTblsEligible, numFactsEligible, bytesCsvSavings), messageCode="info", level=logging.DEBUG)
    else:
        cntlr.addToLog("No tables eligible for facts in CSV", messageCode="info", level=logging.DEBUG)


    mostPopularContexts = sorted(factsPerContext.items(), key=lambda i:"{:0>9},{}".format(999999999-i[1],i[0]))
    cntlr.addToLog("Number of facts {:,}".format(numFacts), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of TableTextBlock facts {:,} avg len {:,.0f}".format(numTableTextBlockFacts, lenTableTextBlockFacts/numTableTextBlockFacts if numTableTextBlockFacts else 0), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of TextBlock facts {:,} avg len {:,.0f}".format(numTextBlockFacts, lenTextBlockFacts/numTableTextBlockFacts if numTableTextBlockFacts else 0), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Max number facts per context {:,}".format(mostPopularContexts[0][1] if mostPopularContexts else 0), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Avg number facts per context {:,.2f}".format(sum([v for v in factsPerContext.values()])/numContexts if numContexts else 0), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Distinct elements in facts {:,}".format(len(distinctElementsInFacts)), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of bytes saveable context id of {} length is {:,}".format(shortContextIdLen, bytesSaveableInline), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Excepting facts eligible for CSV, number of bytes saveable context id of {} length is {:,}".format(shortContextIdLen, bytesSaveableInlineWithCsv), messageCode="info", level=logging.DEBUG)

    aspectEqualFacts = defaultdict(list)
    decVals = {}
    numConsistentDupFacts = numInConsistentDupFacts = 0
    for hashEquivalentFacts in factForConceptContextUnitHash.values():
        if len(hashEquivalentFacts) > 1:
            for f in hashEquivalentFacts:
                aspectEqualFacts[(f.qname,f.contextID,f.unitID,
                                  f.xmlLang.lower() if f.concept.type.isWgnStringFactType else None)].append(f)
            for fList in aspectEqualFacts.values():
                f0 = fList[0]
                if f0.concept.isNumeric:
                    if any(f.isNil for f in fList):
                        _inConsistent = not all(f.isNil for f in fList)
                    else: # not all have same decimals
                        _d = inferredDecimals(f0)
                        _v = f0.xValue
                        _inConsistent = isnan(_v) # NaN is incomparable, always makes dups inconsistent
                        decVals[_d] = _v
                        aMax, bMin, _inclA, _inclB = rangeValue(_v, _d)
                        for f in fList[1:]:
                            _d = inferredDecimals(f)
                            _v = f.xValue
                            if isnan(_v):
                                _inConsistent = True
                                break
                            if _d in decVals:
                                _inConsistent |= _v != decVals[_d]
                            else:
                                decVals[_d] = _v
                            a, b, _inclA, _inclB = rangeValue(_v, _d)
                            if a > aMax: aMax = a
                            if b < bMin: bMin = b
                        if not _inConsistent:
                            _inConsistent = (bMin < aMax)
                        decVals.clear()
                else:
                    _inConsistent = any(not f.isVEqualTo(f0) for f in fList[1:])
                if _inConsistent:
                    numInConsistentDupFacts += 1
                else:
                    numConsistentDupFacts += 1

            aspectEqualFacts.clear()
    cntlr.addToLog("Number of duplicate facts consistent {:,} inconsistent {:,}".format(numConsistentDupFacts, numInConsistentDupFacts), messageCode="info", level=logging.DEBUG)

    styleAttrCountsInline = {}
    styleAttrCountsInlineWithCsv = {}
    totalStyleLenInline = 0
    totalStyleLenInlineWithCsv = 0
    continuationElements = {}
    ixNsPrefix = "{http://www.xbrl.org/2013/inlineXBRL}"
    for ixdsHtmlRootElt in getattr(modelXbrl, "ixdsHtmlElements", ()): # ix root elements if inline
        for ixElt in ixdsHtmlRootElt.iterdescendants():
            inEligibleTableForCsv = any(p in tablesWithEligibleFacts for p in ixElt.iterancestors("{http://www.w3.org/1999/xhtml}table"))
            style = ixElt.get("style")
            ixEltTag = str(ixElt.tag)
            if style:
                styleAttrCountsInline[style] = styleAttrCountsInline.get(style,0) + 1
                if not inEligibleTableForCsv:
                    styleAttrCountsInlineWithCsv[style] = styleAttrCountsInlineWithCsv.get(style,0) + 1
                if styleIxHiddenPattern.match(style) is None:
                    totalStyleLenInline += len(style)
                    if not inEligibleTableForCsv:
                        totalStyleLenInlineWithCsv += len(style)
            if ixEltTag == "{http://www.xbrl.org/2013/inlineXBRL}continuation" and ixElt.id:
                continuationElements[ixElt.id] = ixElt
            if ixEltTag.startswith(ixNsPrefix):
                localName = ixEltTag[len(ixNsPrefix):]
                if localName == "continuation" and ixElt.id:
                    continuationElements[ixElt.id] = ixElt
                elif localName in ("nonFraction", "nonNumeric", "fraction"):
                    xbrlQnameCountInline += 1
                    xbrlQnameLengthsInline += len(ixElt.qname.localName)
                    if not inEligibleTableForCsv:
                        xbrlQnameCountInlineWithCsv += 1
                        xbrlQnameLengthsInlineWithCsv += len(ixElt.qname.localName)
            elif isinstance(ixElt, ModelFact):
                xbrlQnameCountInline += 2
                xbrlQnameLengthsInline += len(ixElt.qname.localName)
                if not inEligibleTableForCsv:
                    xbrlQnameCountInlineWithCsv += 2
                    xbrlQnameLengthsInlineWithCsv += len(ixElt.qname.localName)

    def locateContinuation(element, chain=None):
        contAt = element.get("continuedAt")
        if contAt:
            if contAt in continuationElements:
                if chain is None: chain = [element]
                contElt = continuationElements[contAt]
                if contElt not in chain:
                    chain.append(contElt)
                    element._continuationElement = contElt
                    return locateContinuation(contElt, chain)
        elif chain: # end of chain
            return len(chain)

    numContinuations = 0
    maxLenLen = 0
    maxLenHops = 0
    maxHops = 0
    maxHopsLen = 0
    for f in modelXbrl.factsInInstance:
        if f.get("continuedAt"):
            numContinuations += 1
            _len = len(f.xValue)
            _hops = locateContinuation(f)
            if _hops > maxHops:
                maxHops = _hops
                maxHopsLen = _len
            if _len > maxLenLen:
                maxLenLen = _len
                maxLenHops = _hops

    cntlr.addToLog("Number of continuation facts {:,}".format(numContinuations), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Longest continuation fact {:,} number of hops {:,}".format(maxLenLen, maxLenHops), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Most continuation hops {:,} fact len {:,}".format(maxHops, maxHopsLen), messageCode="info", level=logging.DEBUG)

    numDupStyles = sum(1 for n in styleAttrCountsInline.values() if n > 1)
    bytesSaveableByCssInline = sum(len(s)*(n-1) for s,n in styleAttrCountsInline.items() if n > 1)
    cntlr.addToLog("Number of duplicate styles {:,}, bytes saveable by CSS {:,}, len of all non-ix-hidden @styles {:,}".format(numDupStyles, bytesSaveableByCssInline, totalStyleLenInline), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Number of XBRL QNames {:,}, bytes saveable by EBA-style element names {:,}".format(xbrlQnameCountInline, xbrlQnameLengthsInline - (5*xbrlQnameCountInline)), messageCode="info", level=logging.DEBUG)
    numDupStyles = sum(1 for n in styleAttrCountsInlineWithCsv.values() if n > 1)
    bytesSaveableByCssInlineWithCsv = sum(len(s)*(n-1) for s,n in styleAttrCountsInlineWithCsv.items() if n > 1)
    cntlr.addToLog("Excepting facts eligible for CSV, number of duplicate styles {:,}, bytes saveable by CSS {:,}, len of all non-ix-hidden @styles {:,}".format(numDupStyles, bytesSaveableByCssInlineWithCsv, totalStyleLenInlineWithCsv), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("Excepting facts eligible for CSV, number of XBRL QNames {:,}, bytes saveable by EBA-style element names {:,}".format(xbrlQnameCountInlineWithCsv, xbrlQnameLengthsInlineWithCsv - (5*xbrlQnameCountInlineWithCsv)), messageCode="info", level=logging.DEBUG)



__pluginInfo__ = {
    'name': 'Instance Info',
    'version': '1.0',
    'description': "This plug-in displays instance information for sizing and performance issues.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('inlineXbrlDocumentSet',),
    # classes of mount points (required)
    'CntlrCmdLine.Filing.Start': startup,
    'CntlrCmdLine.Xbrl.Loaded': showInfo
}
