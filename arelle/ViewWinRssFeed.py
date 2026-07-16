"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from tkinter import Menu, Event
from typing import TYPE_CHECKING, Any

from arelle import ViewWinTree
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from tkinter.ttk import Notebook

    from arelle.ModelDocument import ModelDocument
    from arelle.ModelRssItem import ModelRssItem
    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


def viewRssFeed(modelXbrl: ModelXbrl, tabWin: Notebook) -> None:
    view = ViewRssFeed(modelXbrl, tabWin)
    modelXbrl.modelManager.showStatus(_("viewing RSS feed"))
    view.treeView["columns"] = ("form", "filingDate", "cik", "status", "period", "fiscalYrEnd", "results")
    view.treeView.column("#0", width=240, anchor="w")
    view.treeView.heading("#0", text="Company Name")
    view.treeView.column("form", width=30, anchor="w")
    view.treeView.heading("form", text="Form")
    view.treeView.column("filingDate", width=60, anchor="w")
    view.treeView.heading("filingDate", text="Filing Date")
    view.treeView.column("cik", width=60, anchor="w")
    view.treeView.heading("cik", text="CIK")
    view.treeView.column("status", width=70, anchor="w")
    view.treeView.heading("status", text="Status")
    view.treeView.column("period", width=40, anchor="w")
    view.treeView.heading("period", text="Period")
    view.treeView.column("fiscalYrEnd", width=25, anchor="w")
    view.treeView.heading("fiscalYrEnd", text="Yr End")
    view.treeView.column("results", width=100, anchor="w")
    view.treeView.heading("results",  text="Results")
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.treeView.bind("<<TreeviewSelect>>", view.treeviewSelect, "+")
    view.treeView.bind("<Enter>", view.treeviewEnter, "+")
    view.treeView.bind("<Leave>", view.treeviewLeave, "+")

    # menu
    # intercept menu click before pops up to set the viewable RSS item htm URLs
    view.treeView.bind(view.modelXbrl.modelManager.cntlr.contextMenuClick, view.setMenuHtmURLs, "+")
    cntxMenu = view.contextMenu()
    view.setMenuHtmURLs()
    rssWatchMenu = Menu(view.viewFrame, tearoff=0)
    rssWatchMenu.add_command(label=_("Options..."), underline=0, command=lambda: modelXbrl.modelManager.cntlr.rssWatchOptionsDialog())  # type: ignore[attr-defined]
    rssWatchMenu.add_command(label=_("Start"), underline=0, command=lambda: modelXbrl.modelManager.cntlr.rssWatchControl(start=True))  # type: ignore[attr-defined]
    rssWatchMenu.add_command(label=_("Stop"), underline=0, command=lambda: modelXbrl.modelManager.cntlr.rssWatchControl(stop=True))  # type: ignore[attr-defined]
    cntxMenu.add_cascade(label=_("RSS Watch"), menu=rssWatchMenu, underline=0)  # type: ignore[union-attr]
    view.menuAddClipboard()

class ViewRssFeed(ViewWinTree.ViewTree):
    blockViewModelObject: int

    def __init__(self, modelXbrl: ModelXbrl, tabWin: Notebook) -> None:
        super(ViewRssFeed, self).__init__(modelXbrl, tabWin, "RSS Feed", True)

    def view(self) -> None: # reload view
        self.setColumnsSortable(startUnsorted=True)
        self.clearTreeView()
        self.viewRssFeed(self.modelXbrl.modelDocument, "")  # type: ignore[arg-type]

    def viewRssFeed(self, modelDocument: ModelDocument, parentNode: str) -> None:
        self.id = 1
        for rssItem in modelDocument.rssItems:  # type: ignore[attr-defined]
            node = self.treeView.insert(parentNode, "end", rssItem.objectId(),
                                        text=(rssItem.companyName or ""),
                                        tags=("odd" if self.id & 1 else "even",))
            self.treeView.set(node, "form", rssItem.formType)
            self.treeView.set(node, "filingDate", rssItem.filingDate)
            self.treeView.set(node, "cik", rssItem.cikNumber)
            self.treeView.set(node, "status", rssItem.status)
            self.treeView.set(node, "period", rssItem.period)
            self.treeView.set(node, "fiscalYrEnd", rssItem.fiscalYearEnd)
            self.treeView.set(node, "results", " ".join(str(result) for result in (rssItem.results or [])) +
                                                ((" " + str(rssItem.assertions)) if rssItem.assertions else ""))
            self.id += 1
        else:
            pass

    def setMenuHtmURLs(self, event: Event | None = None) -> None:
        import webbrowser
        filingMenu = Menu(self.viewFrame, tearoff=0)
        filingMenu.add_command(label=_("Open Instance Document"), underline=0, command=self.openInstance)
        for pluginMenuExtender in self.modelXbrl.modelManager.cntlr.plugins.hooks("RssFeed.Menu.Filing"):
            pluginMenuExtender(self, filingMenu)

        if event is not None:
            self.menu.delete(0, 0)  # type: ignore[union-attr] # remove old filings
            menuRow = self.treeView.identify_row(event.y) # this is the object ID
            modelRssItem = self.modelXbrl.modelObject(menuRow)
            if modelRssItem is not None:
                for description, url in modelRssItem.htmURLs:  # type: ignore[attr-defined]
                    filingMenu.add_command(label=description, underline=0,
                                           command=lambda u=url: webbrowser.open(u))  # type: ignore[misc]
        self.menu.insert_cascade(0, label=_("Filing"), menu=filingMenu, underline=0)  # type: ignore[union-attr]

    def openInstance(self) -> None:
        rssItemObj = self.modelXbrl.modelObject(self.menuRow)
        if rssItemObj is not None:
            self.modelXbrl.modelManager.cntlr.fileOpenFile(rssItemObj.zippedUrl, selectTopView=True)  # type: ignore[attr-defined]

    def treeviewEnter(self, *args: Any) -> None:
        self.blockSelectEvent = 0

    def treeviewLeave(self, *args: Any) -> None:
        self.blockSelectEvent = 1

    def treeviewSelect(self, *args: Any) -> None:
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            self.modelXbrl.viewModelObject(self.treeView.selection()[0])
            self.blockViewModelObject -= 1

    def viewModelObject(self, rssItem: ModelRssItem) -> None:
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            rssItemId = rssItem.objectId()
            if self.treeView.exists(rssItemId):
                self.treeView.set(rssItemId, "status", rssItem.status)
                self.treeView.set(rssItemId, "results", " ".join(str(result) for result in (rssItem.results or [])) +
                                  ((" " + str(rssItem.assertions)) if rssItem.assertions else ""))
                self.treeView.see(rssItemId)
                self.treeView.selection_set(rssItemId)
            self.blockViewModelObject -= 1
