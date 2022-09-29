'''
See COPYRIGHT.md for copyright information.

Represents modelFacts in an (SEC) filing primary document
'''
import os, re
from lxml import html, etree
from arelle import ModelDocument
from arelle.ModelValue import qname

# part, item, element
SEC10Kparts = {
            ('I', '1'): 'Business',
            ('I', '1A'): 'RiskFactors',
            ('I', '1B'): 'UnresolvedStaffComments',
            ('I', '2'): 'Properties',
            ('I', '3'): 'LegalProceedings',
            ('I', '4'): 'MineSafetyDisclosures',
            ('II', '5'): 'MarketForEquityAndSecurities',
            ('II', '6'): 'SelectedFinancialData',
            ('II', '7'): 'ManagementDiscussionAndAnalysis',
            ('II', '7A'): 'MarketRiskDisclosures',
            ('II', '8'): 'FinancialStatements',
            ('II', '9'): 'ChangesDisagreementsOnDisclosure',
            ('II', '9A'): 'ControlsAndProcedures',
            ('II', '9B'): 'OtherInformation',
            ('III', '10'): 'Governance',
            ('III', '11'): 'ExecutiveCompensation',
            ('III', '12'): 'SecurityOwnership',
            ('III', '13'): 'RelationshipsAndDirectorIndependence',
            ('III', '14'): 'PrincipalAccountingFeesAndServices',
            ('IV', '15'): 'Exhibits'}
SEC10Qparts = {
            ('II', '1A'): 'RiskFactors',
            ('II', '1'): 'LegalProceedings',
            ('II', '4'): 'MineSafetyDisclosures',
            ('II', '2'): 'MarketForEquityAndSecurities',
            ('I', '2'): 'ManagementDiscussionAndAnalysis',
            ('I', '3'): 'MarketRiskDisclosures',
            ('I', '1'): 'FinancialStatements',
            ('I', '4'): 'ControlsAndProcedures',
            ('II', '5'): 'OtherInformation',
            ('II', '6'): 'Exhibits',
            ('II', '3'): 'Defaults'}

# single-line matches, the match starts at newline and ends at end of each line
partPattern = re.compile(r"^\W*part\W+([ivx]+)(\W|$)", re.IGNORECASE + re.MULTILINE)
itemPattern = re.compile(r"^\W*item\W+([1-9][0-9]*[A-Za-z]?)(\W|$)", re.IGNORECASE + re.MULTILINE)
signaturesPattern = re.compile(r"^\W*signatures(\W|$)", re.IGNORECASE + re.MULTILINE)
assetsPattern = re.compile(r"assets(\W|$)", re.IGNORECASE + re.MULTILINE)

def loadPrimaryDocumentFacts(dts, rssItem, entityInformation):
    # identify tables
    disclosureSystem = dts.modelManager.disclosureSystem
    if disclosureSystem.validationType != "EFM":
        return
    if rssItem is not None:
        formType = rssItem.formType
        fileUrl = rssItem.primaryDocumentURL
        reloadCache = getattr(rssItem.modelXbrl, "reloadCache", False)
    else:
        formType = entityInformation.get("form-type")
        fileUrl = entityInformation.get("primary-document-url")
        reloadCache = False
    if fileUrl and formType and (formType.startswith('10-K') or formType.startswith('10-Q')):
        if fileUrl.endswith(".txt") or fileUrl.endswith(".htm"):
            if formType.startswith('10-K'):
                parts = SEC10Kparts
            elif formType.startswith('10-Q'):
                parts = SEC10Qparts
            # try to load and use it
            normalizedUrl = dts.modelManager.cntlr.webCache.normalizeUrl(fileUrl)
            text = ''
            try:
                filePath = dts.modelManager.cntlr.webCache.getfilename(normalizedUrl, reload=reloadCache)
                if filePath:
                    if filePath.endswith('.txt'):
                        with open(filePath, encoding='utf-8') as fh:
                            text = fh.read()
                    elif filePath.endswith('.htm'):
                        doc = html.parse(filePath)
                        textParts = []
                        def iterTextParts(parent):
                            for node in parent.iterchildren():
                                if isinstance(node, etree._Element):
                                    if node.tag in ('p', 'P', 'br', 'BR', 'div', 'DIV'):
                                        textParts.append('\n')
                                    textParts.append(node.text or '')
                                    iterTextParts(node)
                                if node.tail: # use tail whether element, comment, or processing instruction
                                    textParts.append(node.tail)
                        iterTextParts(doc.getroot())
                        text = ' '.join(textParts)
            except  (IOError, EnvironmentError, AttributeError) as err: # attribute err if html has no root element
                dts.info("xpDB:primaryDocumentLoadingError",
                                    _("Loading XBRL DB: primary document loading error: %(error)s"),
                                    modelObject=dts, error=err)
            #with open("/Users/hermf/temp/test.txt", "w", encoding='utf-8') as fh:
            #    fh.write(text)

            class Span:
                def __init__(self, start):
                    self.start = start
                    self.end = -1

            # find the parts
            partSpan = {}
            partPrev = None
            missing2ndPart1 = False
            for partMatch in partPattern.finditer(text):
                part = partMatch.group(1).upper()
                if partPrev is not None:
                    if part != 'I' and part == partPrev:
                        # two of these parts without second part 1, use signature or first item for 2nd part 1
                        missing2ndPart1 = True
                    partSpan[partPrev].end = partMatch.start(0)
                partSpan[part] = Span(partMatch.end(1))
                partPrev = part
            if partPrev is not None:
                partSpan[partPrev].end = len(text)

            if missing2ndPart1:
                # signatures
                signaturesStarts = []
                for signaturesMatch in signaturesPattern.finditer(text):
                    signaturesStarts.append(signaturesMatch.start(0))

                #check if PART I missing then use first signatures
                if 'I' in partSpan and 'II' in partSpan:
                    if len(signaturesStarts) == 2 and signaturesStarts[0] > partSpan['I'].start:
                        partSpan['I'].start = signaturesStarts[0]
                        partSpan['I'].end = partSpan['II'].start
                    else:
                        # use ASSETS as start of part 1
                        for assetsMatch in assetsPattern.finditer(text):
                            partSpan['I'].start = assetsMatch.end(0)
                            partSpan['I'].end = partSpan['II'].start
                            break


            # find the items
            itemSpan = {}
            for part, span in partSpan.items():
                item = None
                for itemMatch in itemPattern.finditer(text, span.start, span.end):
                    if item is not None:
                        itemSpan[(part, item)].end = itemMatch.start(0)
                    item = itemMatch.group(1)
                    itemSpan[(part, item)] = Span(itemMatch.end(1))
                if item is not None:
                    itemSpan[(part, item)].end = span.end

            if any(itemKey in parts for itemKey in itemSpan.keys()):
                # find default context
                for cntx in dts.contexts.values():
                    if cntx.isStartEndPeriod:
                        if not cntx.hasSegment:
                            # use c as default context
                            # load extra datapoints taxonomy but not as discovered in DTS
                            ModelDocument.load(dts, "http://arelle.org/2014/doc-2014-01-31.xsd", )
                            # add the facts
                            for itemKey, itemSpan in itemSpan.items():
                                if itemKey in parts:
                                    dts.createFact(qname("{http://arelle.org/doc/2014-01-31}doc:" + parts[itemKey]),
                                                   attributes=[("contextRef", cntx.id)],
                                                   text=text[itemSpan.start:itemSpan.end])
                            break
