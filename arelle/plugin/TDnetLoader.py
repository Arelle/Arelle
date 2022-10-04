# -*- coding: utf-8 -*-

'''
TDnetLoader is a plug-in to both GUI menu and command line/web service
that loads a TDnet html index file.  TDnet is Tokyo Stock Exchange's
Timely Disclosure Network.

See COPYRIGHT.md for copyright information.
'''
from lxml import html
import datetime, re, os
from arelle import FileSource
from arelle.ModelRssObject import ModelRssObject
from arelle.Version import authorLabel, copyrightLabel

class TDnetItem:
    def __init__(self, modelXbrl, date, dateTime, filingCode, companyName,
                 title, htmlUrl, entryUrl, stockExchange):
        self.cikNumber = None
        self.accessionNumber = filingCode
        self.fileNumber = None
        self.companyName = companyName
        self.formType = stockExchange
        self.pubDate = dateTime
        self.filingDate = date
        self.period = None
        self.assignedSic = None
        self.acceptanceDatetime = dateTime
        self.fiscalYearEnd = None
        self.htmlUrl = htmlUrl
        self.url = entryUrl
        self.zippedUrl = entryUrl
        self.htmURLs = ((title, htmlUrl),)
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

datePattern = re.compile(r"\s*([0-9]+)年([0-9]+)月([0-9]+)日")
timePattern = re.compile(r"\s*([0-9]+):([0-9]+)")
nextLocationPattern = re.compile(r"location='(.+)'")

def intCol(elt, attrName, default=None):
    try:
        return int(elt.get(attrName, default))
    except (TypeError, ValueError):
        return default

def descendantAttr(elt, descendantName, attrName, default=None):
    for descendant in elt.iterdescendants(tag=descendantName):
        if descendant.get(attrName):
            return descendant.get(attrName).strip()
    return default

def tdNetLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if not (mappedUri.startswith("https://www.release.tdnet.info/inbs/I_") and
            mappedUri.endswith(".html")):
        return None # not a td net info file

    rssObject = ModelRssObject(modelXbrl, uri=mappedUri, filepath=filepath)

    hasMoreSections = True
    while hasMoreSections:
        # treat tdnet as an RSS feed object
        try:
            tdInfoDoc = html.parse(filepath)
        except (IOError, EnvironmentError):
            return None # give up, use ordinary loader

        # find date
        date = None
        for elt in tdInfoDoc.iter():
            if elt.tag == "table":
                break # no date portion, probably wrong document
            if elt.text and datePattern.match(elt.text):
                g = datePattern.match(elt.text).groups()
                date = datetime.date(int(g[0]), int(g[1]), int(g[2]))
                break
        if not date:
            return None # give up, not a TDnet index document

        urlDir = os.path.dirname(mappedUri)

        # find <table> with <a>Download in it
        for tableElt in tdInfoDoc.iter(tag="table"):
            useThisTableElt = False
            for aElt in tableElt.iterdescendants(tag="a"):
                if "download" in aElt.text.lower():
                    useThisTableElt = True
                    break
            if useThisTableElt:
                cols = {}
                for trElt in tableElt.iter(tag="tr"):
                    col = 0
                    rowData = {}
                    for tdElt in trElt.iter(tag="td"):
                        text = ''.join(t.strip() for t in tdElt.itertext())
                        if tdElt.get("class") == "tableh": #header
                            type = {"時刻": "time",
                                    "コード": "code",
                                    "会社名": "companyName",
                                    "表題": "title",
                                    "XBRL": "zipUrl",
                                    "上場取引所": "stockExchange",
                                    "更新履歴": "changeLog"
                                    }.get(text, None)
                            if type:
                                cols[col] = type
                                cols[type] = col
                        elif col == cols["title"]:
                            rowData["title"] = text
                            rowData["pdfUrl"] = descendantAttr(tdElt, "a", "href")
                        elif col == cols["zipUrl"]:
                            rowData["zipUrl"] = descendantAttr(tdElt, "a", "href")
                        elif col in cols: # body
                            rowData[cols[col]] = text
                        col += int(tdElt.get("colspan", 1))
                    if rowData:
                        time = rowData.get("time", "")
                        if timePattern.match(time):
                            g = timePattern.match(time).groups()
                            dateTime = datetime.datetime(date.year, date.month, date.day,
                                                         int(g[0]), int(g[1]))
                        else:
                            dateTime = datetime.datetime.now()
                        filingCode = rowData.get("code")
                        companyName = rowData.get("companyName")
                        stockExchange = rowData.get("stockExchange")
                        title = rowData.get("title")
                        pdfUrl = rowData.get("pdfUrl")
                        if pdfUrl:
                            pdfUrl = urlDir + "/" + pdfUrl
                        zipUrl = rowData.get("zipUrl")
                        if zipUrl:
                            zipUrl = urlDir + "/" + zipUrl
                        changeLog = rowData.get("changeLog")
                        # find instance doc in file
                        instanceUrls = []
                        if zipUrl:
                            try:
                                normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(zipUrl)
                                filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
                                filesource = FileSource.FileSource(filepath)
                                dir = filesource.dir
                                filesource.close()
                                if dir:
                                    for file in dir:
                                        if "ixbrl" in file or file.endswith(".xbrl") or "instance" in file:
                                            instanceUrls.append(zipUrl + "/" + file)
                            except:
                                continue # forget this filing
                        for instanceUrl in instanceUrls:
                            rssObject.rssItems.append(
                                TDnetItem(modelXbrl, date, dateTime, filingCode, companyName,
                                          title, pdfUrl, instanceUrl, stockExchange))
        # next screen if continuation
        hasMoreSections = False
        for elt in tdInfoDoc.iter(tag="input"):
            if elt.value == "次画面":  # next screen button
                nextLocation = elt.get("onclick")
                if nextLocation and nextLocationPattern.match(nextLocation):
                    hasMoreSections = True
                    nextUrl = urlDir + "/" + nextLocationPattern.match(nextLocation).groups()[0]
                    mappedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(nextUrl)
                    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUri)
    return rssObject



__pluginInfo__ = {
    'name': 'TDnet Loader',
    'version': '0.9',
    'description': "This plug-in loads Tokyo Stock Exchange Timely Disclosure Network XBRL documents.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    # take out for now: 'CntlrCmdLine.Options': streamingOptionsExtender,
    'ModelDocument.PullLoader': tdNetLoader,
}
