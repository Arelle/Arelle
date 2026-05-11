'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING, Any

from arelle import XmlUtil
from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def _descendantText(
    element: ModelObject,
    namespaceURI: str | None,
    localNames: str,
) -> str | None:
    descendantElt = XmlUtil.descendant(element, namespaceURI, localNames)
    if descendantElt is None:
        return None
    return XmlUtil.text(descendantElt)


newRssWatchOptions: dict[str, str | bool | None] = {
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

    status: str
    results: list[str] | None
    assertions: dict[str, Any] | None
    edgr: str | None
    edgrDescription: str
    edgrFile: str
    edgrInlineXBRL: str
    edgrSequence: str
    edgrType: str
    edgrUrl: str
    assertionUnsuccessful: bool
    _pubDate: datetime.datetime | None
    _filingDate: datetime.date | None
    _acceptanceDatetime: datetime.datetime | None
    _url: str | None
    _htmURLs: list[tuple[str | None, str | None]]
    _primaryDocumentURL: str | None

    def init(self, modelDocument: ModelDocument) -> None:
        super(ModelRssItem, self).init(modelDocument)
        try:
            assert self.modelXbrl is not None
            rssWatchOptions: Any = self.modelXbrl.modelManager.rssWatchOptions  # type: ignore[attr-defined]
            if (rssWatchOptions.latestPubDate and
                self.pubDate is not None and
                self.pubDate <= rssWatchOptions.latestPubDate):
                self.status = _("tested")
            else:
                self.status = _("not tested")
        except AttributeError:
            self.status = _("not tested")
        self.results = None
        self.assertions = None
        # find edgar namespace
        self.edgr = None
        for elt in self.iterdescendants("{*}xbrlFiling"):
            self.edgr = elt.qname.namespaceURI
            break
        if self.edgr:
            edgrPrefix = "{" + self.edgr + "}"
        else:
            edgrPrefix = ""
        self.edgrDescription = edgrPrefix + "description"
        self.edgrFile = edgrPrefix + "file"
        self.edgrInlineXBRL = edgrPrefix + "inlineXBRL"
        self.edgrSequence = edgrPrefix + "sequence"
        self.edgrType = edgrPrefix + "type"
        self.edgrUrl = edgrPrefix + "url"


    @property
    def cikNumber(self) -> str | None:
        return _descendantText(self, self.edgr, "cikNumber")

    @property
    def accessionNumber(self) -> str | None:
        return _descendantText(self, self.edgr, "accessionNumber")

    @property
    def fileNumber(self) -> str | None:
        return _descendantText(self, self.edgr, "fileNumber")

    @property
    def companyName(self) -> str | None:
        return _descendantText(self, self.edgr, "companyName")

    @property
    def formType(self) -> str | None:
        return _descendantText(self, self.edgr, "formType")

    @property
    def pubDate(self) -> datetime.datetime | None:
        try:
            return self._pubDate
        except AttributeError:
            from arelle.UrlUtil import parseRfcDatetime
            pubDateText = _descendantText(self, None, "pubDate")
            self._pubDate = parseRfcDatetime(pubDateText) if pubDateText else None
            return self._pubDate

    @property
    def filingDate(self) -> datetime.date | None:
        try:
            return self._filingDate
        except AttributeError:
            self._filingDate = None
            date = _descendantText(self, self.edgr, "filingDate")
            d = date.split("/") if date else []
            if d and len(d) == 3:
                self._filingDate = datetime.date(int(d[2]), int(d[0]), int(d[1]))
            return self._filingDate

    @property
    def period(self) -> str | None:
        per = _descendantText(self, self.edgr, "period")
        if per and len(per) == 8:
            return "{0}-{1}-{2}".format(per[0:4], per[4:6], per[6:8])
        return None

    @property
    def assignedSic(self) -> str | None:
        return _descendantText(self, self.edgr, "assignedSic")

    @property
    def acceptanceDatetime(self) -> datetime.datetime | None:
        try:
            return self._acceptanceDatetime
        except AttributeError:
            self._acceptanceDatetime = None
            date = _descendantText(self, self.edgr, "acceptanceDatetime")
            if date and len(date) == 14:
                self._acceptanceDatetime = datetime.datetime(
                    int(date[0:4]), int(date[4:6]), int(date[6:8]),
                    int(date[8:10]), int(date[10:12]), int(date[12:14]))
            return self._acceptanceDatetime

    @property
    def fiscalYearEnd(self) -> str | None:
        yrEnd = _descendantText(self, self.edgr, "fiscalYearEnd")
        if yrEnd and len(yrEnd) == 4:
            return "{0}-{1}".format(yrEnd[0:2], yrEnd[2:4])
        return None

    @property
    def htmlUrl(self) -> str | None:  # main filing document
        htmlDocElt = XmlUtil.descendant(self, self.edgr, "xbrlFile", attrName=self.edgrSequence, attrValue="1")
        if htmlDocElt is not None:
            return htmlDocElt.get(self.edgrUrl)
        return None

    @property
    def url(self) -> str | None:
        try:
            return self._url
        except AttributeError:
            self._url = None
            for instDocElt in XmlUtil.descendants(self, self.edgr, "xbrlFile"):
                edgrTypeAttr = instDocElt.get(self.edgrType)
                if (edgrTypeAttr is not None and edgrTypeAttr.endswith(".INS")) or instDocElt.get(self.edgrInlineXBRL) == "true":
                    self._url = instDocElt.get(self.edgrUrl)
                    break
            return self._url

    @property
    def enclosureUrl(self) -> str | None:
        return XmlUtil.childAttr(self, None, "enclosure", "url")

    @property
    def zippedUrl(self) -> str | None:
        enclosure = XmlUtil.childAttr(self, None, "enclosure", "url")
        if enclosure:
            # retrun enclosure which may contain multi-IXDSes and multi-doc primary files
            return enclosure
        else:  # no zipped enclosure, just use unzipped file
            return self.url


    @property
    def htmURLs(self) -> list[tuple[str | None, str | None]]:
        try:
            return self._htmURLs
        except AttributeError:
            self._htmURLs = [
                (instDocElt.get(self.edgrDescription), instDocElt.get(self.edgrUrl))
                for instDocElt in XmlUtil.descendants(self, self.edgr, "xbrlFile")
                if (instDocElt.get(self.edgrFile) or "").endswith(".htm")]
            return self._htmURLs

    @property
    def primaryDocumentURL(self) -> str | None:
        try:
            return self._primaryDocumentURL
        except AttributeError:
            formType = self.formType
            self._primaryDocumentURL = None
            for instDocElt in XmlUtil.descendants(self, self.edgr, "xbrlFile"):
                if instDocElt.get(self.edgrType) == formType:
                    self._primaryDocumentURL = instDocElt.get(self.edgrUrl)
                    break
            return self._primaryDocumentURL

    def setResults(self, modelXbrl: ModelXbrl) -> None:
        self.results = []
        self.assertionUnsuccessful = False
        # put error codes first, sorted, then assertion result (dict's)
        self.status = "pass"
        for error in modelXbrl.errors:
            if isinstance(error, dict):  # assertion results
                self.assertions = error
                for countSuccessful, countNotsuccessful in error.items():
                    if countNotsuccessful > 0:  # type: ignore[operator]
                        self.assertionUnsuccessful = True
                        self.status = "unsuccessful"
            else:   # error code results
                self.results.append(error)
                self.status = "fail"  # error code
        self.results.sort()

    @property
    def propertyView(self) -> tuple[tuple[str, Any], ...]:
        return (("CIK", self.cikNumber),
                ("company", self.companyName),
                ("published", self.pubDate),
                ("form type", self.formType),
                ("filing date", self.filingDate),
                ("period", self.period),
                ("year end", self.fiscalYearEnd),
                ("status", self.status),
                ("instance", os.path.basename(self.url) if self.url else None),
                )

    def __repr__(self) -> str:
        return ("rssItem[{0}]{1})".format(self.objectId(), self.propertyView))
