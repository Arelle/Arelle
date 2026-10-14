"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle import ViewFile
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelRssItem import ModelRssItem
from arelle.ModelRssObject import ModelRssObject
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.FileSource import FileNamedStringIO
    from arelle.ModelDocument import ModelDocument
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewRssFeed(
        modelXbrl: ModelXbrl,
        outfile: str | FileNamedStringIO | None,
        cols: str | list[str] | None,
) -> None:
    modelXbrl.modelManager.showStatus(_("viewing RSS feed"))
    view = ViewRssFeed(modelXbrl, outfile, cols)
    view.viewRssFeed(modelXbrl.modelDocument)  # type: ignore[arg-type]
    view.close()

class ViewRssFeed(ViewFile.View):
    def __init__(
            self,
            modelXbrl: ModelXbrl,
            outfile: str | FileNamedStringIO | None,
            cols: str | list[str] | None,
    ) -> None:
        super(ViewRssFeed, self).__init__(modelXbrl, outfile, "RSS Feed")
        self.cols: str | list[str] | None = cols

    def viewRssFeed(self, modelDocument: ModelDocument) -> None:
        if self.cols:
            if isinstance(self.cols, str):
                self.cols = self.cols.split(",")
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Company Name", "Accession Number", "Form", "Filing Date", "CIK", "Status", "Period", "Yr End", "Results"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedRssReportColumn",  # type: ignore[union-attr]
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=",".join(unrecognizedCols))
        else:
            self.cols = ["Company Name", "Accession Number", "Form", "Filing Date", "CIK", "Status", "Period", "Yr End", "Results"]
        self.addRow(self.cols, asHeader=True)

        if modelDocument.type == ModelDocumentType.RSSFEED:
            for rssItem in modelDocument.rssItems:  # type: ignore[attr-defined]
                cols: list[str | None] = []
                for col in self.cols:
                    if col == "Company Name":
                        cols.append(rssItem.companyName)
                    elif col == "Accession Number":
                        cols.append(rssItem.accessionNumber)
                    elif col == "Form":
                        cols.append(rssItem.formType)
                    elif col == "Filing Date":
                        cols.append(rssItem.filingDate)
                    elif col == "CIK":
                        cols.append(rssItem.cikNumber)
                    elif col == "Status":
                        cols.append(rssItem.status)
                    elif col == "Period":
                        cols.append(rssItem.period)
                    elif col == "Yr End":
                        cols.append(rssItem.fiscalYearEnd)
                    elif col == "Results":
                        cols.append(" ".join(str(result) for result in (rssItem.results or [])) +
                                    ((" " + str(rssItem.assertions)) if rssItem.assertions else ""))
                    else:
                        cols.append("")
                self.addRow(cols, xmlRowElementName="rssItem")
