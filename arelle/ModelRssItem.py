'''
Created on Nov 11, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XmlUtil
from arelle.ModelObject import ModelObject

edgr = "http://www.sec.gov/Archives/edgar"
edgrDescription = "{http://www.sec.gov/Archives/edgar}description"
edgrFile = "{http://www.sec.gov/Archives/edgar}file"
edgrSequence = "{http://www.sec.gov/Archives/edgar}sequence"
edgrType = "{http://www.sec.gov/Archives/edgar}type"
edgrUrl = "{http://www.sec.gov/Archives/edgar}url"

newRssWatchOptions = {
    "feedSource": "",
    "feedSourceUri": None,
    "matchTextExpr": "",
    "formulaFileUri": "",
    "logFileUri": "",
    "emailAddress": "",
    "validateXbrlRules": False,
    "validateDisclosureSystemRules": False,
    "validateCalcLinkbase": False,
    "validateFormulaAssertions": False,
    "alertMatchedFactText": False,
    "alertAssertionUnsuccessful": False,
    "alertValiditionError": False,
    "latestPubDate": None,
}
        
        # Note: if adding to this list keep DialogRssWatch in sync
class ModelRssItem(ModelObject):
    def init(self, modelDocument):
        super(ModelRssItem, self).init(modelDocument)
        try:
            if (self.modelXbrl.modelManager.rssWatchOptions.latestPubDate and 
                self.pubDate <= self.modelXbrl.modelManager.rssWatchOptions.latestPubDate):
                self.status = _("tested")
            else:
                self.status = _("not tested")
        except AttributeError:
            self.status = _("not tested")
        self.results = None
        self.assertions = None
        
    @property
    def cikNumber(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "cikNumber"))
    
    @property
    def accessionNumber(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "accessionNumber"))
    
    @property
    def fileNumber(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "fileNumber"))
    
    @property
    def companyName(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "companyName"))
    
    @property
    def formType(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "formType"))
    
    @property
    def pubDate(self):
        try:
            return self._pubDate
        except AttributeError:
            from arelle.UrlUtil import parseRfcDatetime
            self._pubDate = parseRfcDatetime(XmlUtil.text(XmlUtil.descendant(self, None, "pubDate")))
            return self._pubDate
    @property
    def filingDate(self):
        try:
            return self._filingDate
        except AttributeError:
            import datetime
            self._filingDate = None
            date = XmlUtil.text(XmlUtil.descendant(self, edgr, "filingDate"))
            d = date.split("/") 
            if d and len(d) == 3:
                self._filingDate = datetime.date(_INT(d[2]),_INT(d[0]),_INT(d[1]))
            return self._filingDate
    
    @property
    def period(self):
        per = XmlUtil.text(XmlUtil.descendant(self, edgr, "period"))
        if per and len(per) == 8:
            return "{0}-{1}-{2}".format(per[0:4],per[4:6],per[6:8])
        return None
    
    @property
    def assignedSic(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "assignedSic"))
    
    @property
    def acceptanceDatetime(self):
        try:
            return self._acceptanceDatetime
        except AttributeError:
            import datetime
            self._acceptanceDatetime = None
            date = XmlUtil.text(XmlUtil.descendant(self, edgr, "acceptanceDatetime"))
            if date and len(date) == 14:
                self._acceptanceDatetime = datetime.datetime(_INT(date[0:4]),_INT(date[4:6]),_INT(date[6:8]),_INT(date[8:10]),_INT(date[10:12]),_INT(date[12:14]))
            return self._acceptanceDatetime
    
    @property
    def fiscalYearEnd(self):
        yrEnd = XmlUtil.text(XmlUtil.descendant(self, edgr, "fiscalYearEnd"))
        if yrEnd and len(yrEnd) == 4:
            return "{0}-{1}".format(yrEnd[0:2],yrEnd[2:4])
        return None
    
    @property
    def htmlUrl(self):  # main filing document
        htmlDocElt = XmlUtil.descendant(self, edgr, "xbrlFile", attrName=edgrSequence, attrValue="1")
        if htmlDocElt is not None:
            return htmlDocElt.get(edgrUrl)
        return None

    @property
    def url(self):
        try:
            return self._url
        except AttributeError:
            self._url = None
            for instDocElt in XmlUtil.descendants(self, edgr, "xbrlFile"):
                if instDocElt.get(edgrType).endswith(".INS"):
                    self._url = instDocElt.get(edgrUrl)
                    break
            return self._url
        
    @property
    def zippedUrl(self):
        enclosure = XmlUtil.childAttr(self, None, "enclosure", "url")
        if enclosure:
            # modify url to use zip file
            path, sep, file = self.url.rpartition("/")
            # return path + sep + self.accessionNumber + "-xbrl.zip" + sep + file
            return enclosure + sep + file
        else: # no zipped enclosure, just use unzipped file
            return self.url
        
        
    @property
    def htmURLs(self):
        try:
            return self._htmURLs
        except AttributeError:
            self._htmURLs = [
                (instDocElt.get(edgrDescription),instDocElt.get(edgrUrl))
                  for instDocElt in XmlUtil.descendants(self, edgr, "xbrlFile")
                    if instDocElt.get(edgrFile).endswith(".htm")]
            return self._htmURLs
        
    @property
    def primaryDocumentURL(self):
        try:
            return self._primaryDocumentURL
        except AttributeError:
            formType = self.formType
            self._primaryDocumentURL = None
            for instDocElt in XmlUtil.descendants(self, edgr, "xbrlFile"):
                if instDocElt.get(edgrType) == formType:
                    self._primaryDocumentURL = instDocElt.get(edgrUrl)
                    break
            return self._primaryDocumentURL
        
    def setResults(self, modelXbrl):
        self.results = []
        self.assertionUnsuccessful = False
        # put error codes first, sorted, then assertion result (dict's)
        self.status = "pass"
        for error in modelXbrl.errors:
            if isinstance(error,dict):  # assertion results
                self.assertions = error
                for countSuccessful, countNotsuccessful in error.items():
                    if countNotsuccessful > 0:
                        self.assertionUnsuccessful = True
                        self.status = "unsuccessful"
            else:   # error code results
                self.results.append(error)
                self.status = "fail" # error code
        self.results.sort()
    
    @property
    def propertyView(self):
        return (("CIK", self.cikNumber),
                ("company", self.companyName),
                ("published", self.pubDate),
                ("form type", self.formType),
                ("filing date", self.filingDate),
                ("period", self.period),
                ("year end", self.fiscalYearEnd),
                ("status", self.status),
                ("instance", os.path.basename(self.url)),
                )
    def __repr__(self):
        return ("rssItem[{0}]{1})".format(self.objectId(),self.propertyView))

