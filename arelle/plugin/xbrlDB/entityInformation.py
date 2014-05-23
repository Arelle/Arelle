'''
Created on May 18, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.

Provides entity information for an (SEC) filing including supplemental SGML document

acceptance-datetime, accession-number, type, public-document-count, period (date),
filing-date, date-of-filing-date-change, conformed-name, cik, assigned-sic
irs-number, state-of-incorporation, fiscal-year-end (month-day), form-type,
act, file-number, film-number, business-address.{street1,street2,city,state,zip,phone},
mail-address.{street1,street2,city,state,zip},
former-name-{1..}.{former-conformed-name,date-changed}

filer-category, public-float, trading-symbol, fiscal-year-focus, fiscal-period-focus
'''
import os, re, datetime
from lxml import html, etree
from arelle import ModelDocument
from arelle.ModelValue import qname
from arelle.ValidateXbrlCalcs import roundValue


def loadEntityInformation(dts, rssItem):
    entityInformation = {}
    # identify tables
    disclosureSystem = dts.modelManager.disclosureSystem
    if disclosureSystem.EFM:
        if rssItem is not None:
            accession = rssItem.url.split('/')[-2]
            fileUrl = os.path.dirname(rssItem.url) + '/' + accession[0:10] + '-' + accession[10:12] + '-' + accession[12:] + ".hdr.sgml"
        elif dts.uri.startswith("http://www.sec.gov/Archives/edgar/data") and dts.uri.endswith(".xml"):
            accession = dts.uri.split('/')[-2]
            fileUrl = os.path.dirname(dts.uri) + '/' + accession[0:10] + '-' + accession[10:12] + '-' + accession[12:] + ".hdr.sgml"
        else:
            fileUrl = ''
        if fileUrl:
            # try to load and use it
            normalizedUrl = dts.modelManager.cntlr.webCache.normalizeUrl(fileUrl)
            hdrSgml = ''
            try:
                filePath = dts.modelManager.cntlr.webCache.getfilename(normalizedUrl)
                if filePath:
                    with open(filePath) as fh:
                        hdrSgml = fh.read()
                    
            except  (IOError, EnvironmentError) as err:
                dts.info("xpDB:headerSgmlDocumentLoadingError",
                                    _("Loading XBRL DB: header SGML document %(file)s loading error: %(error)s"),
                                    modelObject=dts, file=normalizedUrl, error=err)
                hdrSgml = ''
            record = ''
            formerCompanyNumber = 0
            for match in re.finditer(r"[<]([^>]+)[>]([^<\n\r]*)", hdrSgml, re.MULTILINE):
                tag = match.group(1).lower()
                v = match.group(2).replace("&lt;","<").replace("&gt;",">").replace("&amp;","&")
                if tag in ('business-address','mail-address'):
                    record = tag + '.'
                elif tag == 'former-company':
                    formerCompanyNumber += 1
                    record = "{}-{}.".format(tag, formerCompanyNumber)
                elif tag.startswith('/'):
                    record = ''
                elif v:
                    if tag.endswith("-datetime"):
                        try:
                            v = datetime.datetime(_INT(v[0:4]),_INT(v[4:6]),_INT(v[6:8]),_INT(v[8:10]),_INT(v[10:12]),_INT(v[12:14]))
                        except ValueError:
                            pass
                    elif tag.endswith("-date") or tag.startswith("date-of-"):
                        try:
                            v = datetime.date(_INT(v[0:4]),_INT(v[4:6]),_INT(v[6:8]))
                        except ValueError:
                            pass
                    elif tag.endswith("-year-end") and len(v) == 4:
                        v = "{0}-{1}".format(v[0:2],v[2:4])
                    elif tag in ('assigned-sic',):
                        try:
                            v = _INT(v)
                        except ValueError:
                            v = None

                    entityInformation[record + tag] = v
        # instance information
        for factName, entityField in (("EntityFilerCategory", "filer-category"), 
                                      ("EntityPublicFloat", "public-float"), 
                                      ("TradingSymbol", "trading-symbol"), 
                                      ("DocumentFisalYearFocus", "fiscal-year-focus"),
                                      ("DocumentFisalPeriodFocus", "fiscal-period-focus")):
            try:
                concept = dts.nameConcepts[factName][0] # get qname irrespective of taxonomy year
                facts = dts.factsByQname[concept.qname]
                for fact in facts:
                    if not fact.context.qnameDims: #default context
                        if factName in ("EntityPublicFloat",):
                            entityInformation[entityField] = roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric and not fact.isNil else None
                        else:
                            entityInformation[entityField] = fact.value
                        break
            except IndexError:
                pass
        return entityInformation