'''
See COPYRIGHT.md for copyright information.
'''
from arelle import ModelDocument, ViewFile
import os

def viewRssFeed(modelXbrl, outfile, cols):
    modelXbrl.modelManager.showStatus(_("viewing RSS feed"))
    view = ViewRssFeed(modelXbrl, outfile, cols)
    view.viewRssFeed(modelXbrl.modelDocument)
    view.close()

class ViewRssFeed(ViewFile.View):
    def __init__(self, modelXbrl, outfile, cols):
        super(ViewRssFeed, self).__init__(modelXbrl, outfile, "RSS Feed")
        self.cols = cols

    def viewRssFeed(self, modelDocument):
        if self.cols:
            if isinstance(self.cols,str): self.cols = self.cols.replace(',').split()
            unrecognizedCols = []
            for col in self.cols:
                if col not in ("Company Name", "Accession Number", "Form", "Filing Date", "CIK", "Status", "Period", "Yr End", "Results"):
                    unrecognizedCols.append(col)
            if unrecognizedCols:
                self.modelXbrl.error("arelle:unrecognizedRssReportColumn",
                                     _("Unrecognized columns: %(cols)s"),
                                     modelXbrl=self.modelXbrl, cols=','.join(unrecognizedCols))
        else:
            self.cols = ["Company Name", "Accession Number", "Form", "Filing Date", "CIK", "Status", "Period", "Yr End", "Results"]
        self.addRow(self.cols, asHeader=True)

        if modelDocument.type == ModelDocument.Type.RSSFEED:
            for rssItem in modelDocument.rssItems:
                cols = []
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
