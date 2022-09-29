# -*- coding: utf-8 -*-

'''
UKCompaniesHouseLoader is a plug-in to both GUI menu and command line/web service
that loads a Companies House zip XBRL instances file.

See COPYRIGHT.md for copyright information.
'''
from lxml import html
import datetime, re, os
from arelle import FileSource
from arelle.ModelRssObject import ModelRssObject
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlValidate import UNVALIDATED, VALID

class CompaniesHouseItem:
    def __init__(self, modelXbrl, fileName, entryUrl):
        self.cikNumber = None
        self.accessionNumber = fileName[4:].partition(".")[0]
        self.fileNumber = None
        self.companyName = None
        self.formType = None
        pubDate = fileName.rpartition("_")[2].partition(".")[0]
        try:
            self.pubDate = datetime.datetime(int(pubDate[0:4]), int(pubDate[4:6]), int(pubDate[6:8]))
            self.acceptanceDatetime = self.pubDate
            self.filingDate = self.pubDate.date()
        except ValueError:
            self.pubDate = self.acceptanceDatetime = self.filingDate = None
        self.period = None
        self.assignedSic = None
        self.fiscalYearEnd = None
        self.htmlUrl = None
        self.url = entryUrl
        self.zippedUrl = entryUrl
        self.htmURLs = ((fileName, entryUrl),)
        self.status = "not tested"
        self.results = None
        self.assertions = None
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)

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

    def objectId(self,refId=""):
        """Returns a string surrogate representing the object index of the model document,
        prepended by the refId string.
        :param refId: A string to prefix the refId for uniqueless (such as to use in tags for tkinter)
        :type refId: str
        """
        return "_{0}_{1}".format(refId, self.objectIndex)

def companiesHouseInstanceLoaded(modelXbrl, rssWatchOptions, rssItem, *args, **kwargs):
    for fact in modelXbrl.factsInInstance:
        name = fact.qname.localName if fact.qname is not None else None
        if name in ("CompaniesHouseRegisteredNumber",
                    "UKCompaniesHouseRegisteredNumber",
                    "EntityCurrentLegalName",
                    "EntityCurrentLegalOrRegisteredName",
                    "EndDateForPeriodCoveredByReport"):
            if name in ("CompaniesHouseRegisteredNumber","UKCompaniesHouseRegisteredNumber"):
                rssItem.cikNumber = fact.value.strip()
            elif name in ("EntityCurrentLegalName", "EntityCurrentLegalOrRegisteredName"):
                rssItem.companyName = fact.value.strip()
            elif name == "EndDateForPeriodCoveredByReport" and getattr(fact, "xValid", UNVALIDATED) == VALID:
                rssItem.period = fact.xValue
                rssItem.fiscalYearEnd = "{:04}-{:02}".format(fact.xValue.year, fact.xValue.month)


def companiesHouseLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if not (mappedUri.startswith("http://download.companieshouse.gov.uk/") and
            mappedUri.endswith(".zip")):
        return None # not a companies houst zip file

    rssObject = ModelRssObject(modelXbrl, uri=mappedUri, filepath=filepath)

    # find <table> with <a>Download in it
    for instanceFile in modelXbrl.fileSource.dir:
        rssObject.rssItems.append(
            CompaniesHouseItem(modelXbrl, instanceFile, mappedUri + '/' + instanceFile))
    return rssObject



__pluginInfo__ = {
    'name': 'UK Companies House Loader',
    'version': '0.9',
    'description': "This plug-in loads UK Companies House XBRL documents.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    # take out for now: 'CntlrCmdLine.Options': streamingOptionsExtender,
    'ModelDocument.PullLoader': companiesHouseLoader,
    'RssItem.Xbrl.Loaded': companiesHouseInstanceLoaded,
}
