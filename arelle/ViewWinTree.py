'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import os
from tkinter import HORIZONTAL, VERTICAL, N, S, E, W, StringVar, TclError, Menu, PhotoImage
from tkinter.ttk import Frame, Scrollbar, Treeview, Notebook
from typing import TYPE_CHECKING, Any, Callable, Iterable

from arelle.CntlrWinTooltip import ToolTip
from arelle.ViewUtil import baseSetArcroles, labelroles
from arelle.typing import TypeGetText

_: TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl


class ViewTree:
    view: Callable[[], None] | None
    menu: Menu | None

    def __init__(
        self,
        modelXbrl: ModelXbrl,
        tabWin: Notebook,
        tabTitle: str,
        hasToolTip: bool = False,
        lang: str | None = None,
    ) -> None:
        self.tabWin = tabWin
        self.viewFrame = Frame(tabWin)
        self.viewFrame.view = self  # type: ignore[attr-defined]
        self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        tabWin.add(self.viewFrame, text=tabTitle)
        self.tabTitle = tabTitle # for error messages
        vScrollbar = Scrollbar(self.viewFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(self.viewFrame, orient=HORIZONTAL)
        self.treeView = Treeview(self.viewFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set)
        self.treeView.grid(row=0, column=0, sticky=(N, S, E, W))
        try:
            _isDarkTheme = bool(self.viewFrame.tk.call("tk::unsupported::MacWindowStyle", "isdark", "."))
        except TclError:
            _isDarkTheme = False
        if _isDarkTheme:
            self.treeView.tag_configure("ELR", background="#2D3033")
            self.treeView.tag_configure("even", background="#303030")
            self.treeView.tag_configure("odd", background="#212121")
        else:
            self.treeView.tag_configure("ELR", background="#E0F0FF")
            self.treeView.tag_configure("even", background="#F0F0F0")
            self.treeView.tag_configure("odd", background="#FFFFFF")
        if modelXbrl.modelManager.cntlr.isMac or modelXbrl.modelManager.cntlr.isMSW:
            highlightColor = "#%04x%04x%04x" % self.treeView.winfo_rgb("SystemHighlight")
        else:
            highlightColor = "#33339999ffff"  # using MSW value for Unix/Linux which has no named colors
        self.treeView.tag_configure("selected-ELR", background=highlightColor)
        self.treeView.tag_configure("selected-even", background=highlightColor)
        self.treeView.tag_configure("selected-odd", background=highlightColor)
        self.treeViewSelection: tuple[str, ...] = ()
        self.treeView.bind("<<TreeviewSelect>>", self.viewSelectionChange, "+")
        self.treeView.bind("<1>", self.onViewClick, "+")
        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E, W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N, S))
        self.viewFrame.columnconfigure(0, weight=1)
        self.viewFrame.rowconfigure(0, weight=1)
        self.modelXbrl: ModelXbrl = modelXbrl
        self.hasToolTip = hasToolTip
        self.toolTipText = StringVar()
        if hasToolTip:
            self.treeView.bind("<Motion>", self.motion, "+")
            self.treeView.bind("<Leave>", self.leave, "+")
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(self.treeView,
                                   textvariable=self.toolTipText,
                                   wraplength=480,
                                   follow_mouse=True,
                                   state="disabled")
            self.toolTipColId: str | None = None
            self.toolTipRowId: str | None = None
        self.modelXbrl = modelXbrl
        self.lang = lang
        self.labelrole: str | None = None
        self.nameIsPrefixed = False
        if modelXbrl:
            modelXbrl.views.append(self)
            if not lang:
                self.lang = modelXbrl.modelManager.defaultLang

    def clearTreeView(self) -> None:
        self.treeViewSelection = ()
        for node in self.treeView.get_children():
            self.treeView.delete(node)

    def viewSelectionChange(self, event: Any = None) -> None:
        for node in self.treeViewSelection:
            if self.treeView.exists(node):
                priorTags = self.treeView.item(node)["tags"]
                if priorTags:
                    priorBgTag = priorTags[0]
                    if priorBgTag.startswith("selected-"):
                        self.treeView.item(node, tags=(priorBgTag[9:],))
        self.treeViewSelection = self.treeView.selection()
        for node in self.treeViewSelection:
            priorTags = self.treeView.item(node)["tags"]
            if priorTags:
                self.treeView.item(node, tags=("selected-" + priorTags[0],))

    def onViewClick(self, *args: Any) -> None:
        self.modelXbrl.modelManager.cntlr.currentView = self  # type: ignore[attr-defined]

    def close(self) -> None:
        del self.viewFrame.view  # type: ignore[attr-defined]
        if self.modelXbrl:
            self.tabWin.forget(self.viewFrame)
            self.modelXbrl.views.remove(self)
            self.modelXbrl = None  # type: ignore[assignment]
            self.view = None

    def select(self) -> None:
        self.tabWin.select(self.viewFrame)  # type: ignore[no-untyped-call]

    def leave(self, *args: Any) -> None:
        self.toolTipColId = None
        self.toolTipRowId = None

    def motion(self, *args: Any) -> None:
        tvColId = self.treeView.identify_column(args[0].x)
        tvRowId = self.treeView.identify_row(args[0].y)
        if tvColId != self.toolTipColId or tvRowId != self.toolTipRowId:
            self.toolTipColId = tvColId
            self.toolTipRowId = tvRowId
            newValue = self.getToolTip(tvRowId, tvColId)
            if newValue is None and tvRowId and len(tvRowId) > 0:
                try:
                    col = int(tvColId[1:])
                    if col == 0:
                        newValue = self.treeView.item(tvRowId,"text")
                    else:
                        values = self.treeView.item(tvRowId,"values")
                        if col <= len(values):
                            newValue = values[col - 1]
                except ValueError:
                    pass
            self.setToolTip(newValue, tvColId)

    def getToolTip(self, rowId: str, colId: str) -> str | None:
        return None

    def setToolTip(self, text: str | None, colId: str = "#0") -> None:
        self.toolTip._hide()
        if isinstance(text, str) and len(text) > 0:
            width = self.treeView.column(colId,"width")
            if len(text) * 8 > width or "\n" in text:
                self.toolTipText.set(text)
                self.toolTip.configure(state="normal")
                self.toolTip._schedule()
            else:
                self.toolTipText.set("")
                self.toolTip.configure(state="disabled")
        else:
            self.toolTipText.set("")
            self.toolTip.configure(state="disabled")

    def contextMenu(self) -> Menu | None:
        try:
            return self.menu
        except AttributeError:
            try:
                self.menu = Menu(self.viewFrame, tearoff=0)
                self.treeView.bind(self.modelXbrl.modelManager.cntlr.contextMenuClick, self.popUpMenu, "+")
                return self.menu
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None
                return None

    def popUpMenu(self, event: Any) -> None:
        if self.menu:
            self.menuRow = self.treeView.identify_row(event.y)
            self.menuCol = self.treeView.identify_column(event.x)
            self.menu.post(event.x_root, event.y_root)

    def expand(self) -> None:
        self.setTreeItemOpen(self.menuRow, open=True)

    def expandAll(self) -> None:
        self.setTreeItemOpen("", open=True)

    def collapse(self) -> None:
        self.setTreeItemOpen(self.menuRow, open=False)

    def collapseAll(self) -> None:
        self.setTreeItemOpen("", open=False)

    def setTreeItemOpen(self, node: str, open: bool = True) -> None:
        if node:
            self.treeView.item(node, open=open)
        for childNode in self.treeView.get_children(node):
            self.setTreeItemOpen(childNode, open)

    def menuAddExpandCollapse(self) -> None:
        if self.menu:
            self.menu.add_command(label=_("Expand"), underline=0, command=self.expand)
            self.menu.add_command(label=_("Collapse"), underline=0, command=self.collapse)
            self.menu.add_command(label=_("Expand all"), underline=0, command=self.expandAll)
            self.menu.add_command(label=_("Collapse all"), underline=0, command=self.collapseAll)

    def menuAddClipboard(self) -> None:
        if self.menu and self.modelXbrl.modelManager.cntlr.hasClipboard:
            try:
                clipboardMenu = Menu(self.viewFrame, tearoff=0)
                clipboardMenu.add_command(label=_("Cell"), underline=0, command=self.copyCellToClipboard)
                clipboardMenu.add_command(label=_("Row"), underline=0, command=self.copyRowToClipboard)
                clipboardMenu.add_command(label=_("Table"), underline=0, command=self.copyTableToClipboard)
                self.menu.add_cascade(label=_("Copy to clipboard"), menu=clipboardMenu, underline=0)
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating clipboard menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def menuAddLangs(self) -> None:
        if self.menu:
            try:
                langsMenu = Menu(self.viewFrame, tearoff=0)
                self.menu.add_cascade(label=_("Language"), menu=langsMenu, underline=0)
                for lang in sorted(self.modelXbrl.langs):
                    langsMenu.add_command(label=lang, underline=0, command=lambda l=lang: self.setLang(l))  # type: ignore[misc]
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context languages menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def menuAddLabelRoles(
        self,
        includeConceptName: bool = False,
        menulabel: str | None = None,
        usedLabelroles: list[tuple[str, str]] | None = None,
    ) -> None:
        if self.menu:
            try:
                if menulabel is None:
                    menulabel = _("Label role")
                rolesMenu = Menu(self.viewFrame, tearoff=0)
                self.menu.add_cascade(label=menulabel, menu=rolesMenu, underline=0)
                if usedLabelroles is None: # provided for OIM taxonomy
                    usedLabelroles = labelroles(self.modelXbrl, includeConceptName) # arelle infrastructure
                for x in usedLabelroles:
                    rolesMenu.add_command(label=x[0][1:], underline=0, command=lambda a=x[1]: self.setLabelrole(a))  # type: ignore[misc]
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context label roles menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def menuAddNameStyle(self, menulabel: str | None = None) -> None:
        if self.menu:
            try:
                if menulabel is None: menulabel = _("Name Style")
                nameStyleMenu = Menu(self.viewFrame, tearoff=0)
                self.menu.add_cascade(label=menulabel, menu=nameStyleMenu, underline=0)
                nameStyleMenu.add_command(label=_("Prefixed"), underline=0, command=lambda a=True: self.setNamestyle(a))  # type: ignore[misc]
                nameStyleMenu.add_command(label=_("No prefix"), underline=0, command=lambda a=False: self.setNamestyle(a))  # type: ignore[misc]
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context name style menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def menuAddUnitDisplay(self) -> None:
        if self.menu:
            try:
                rolesMenu = Menu(self.viewFrame, tearoff=0)
                self.menu.add_cascade(label=_("Units"), menu=rolesMenu, underline=0)
                rolesMenu.add_command(label=_("Unit ID"), underline=0, command=lambda: self.setUnitDisplay(unitDisplayID=True))
                rolesMenu.add_command(label=_("Measures"), underline=0, command=lambda: self.setUnitDisplay(unitDisplayID=False))
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context unit menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def menuAddViews(
        self,
        addClose: bool = True,
        tabWin: Notebook | None = None,
        additionalViews: Iterable[tuple[Any, ...]] | None = None,
        additionalViewMethod: Callable[..., None] | None = None,
    ) -> None:
        if self.menu:
            try:
                if tabWin is None: tabWin = self.tabWin
                viewMenu = Menu(self.viewFrame, tearoff=0)
                self.menu.add_cascade(label=_("View"), menu=viewMenu, underline=0)
                newViewsMenu = Menu(self.viewFrame, tearoff=0)
                if addClose:
                    viewMenu.add_command(label=_("Close"), underline=0, command=self.close)
                viewMenu.add_cascade(label=_("Additional view"), menu=newViewsMenu, underline=0)
                if not additionalViews: # 2.1 view
                    newViewsMenu.add_command(label=_("Arcrole group..."), underline=0, command=lambda: self.newArcroleGroupView(tabWin))
                    for x in baseSetArcroles(self.modelXbrl) + [( " Role Types","!CustomRoleTypes!"), (" Arcrole Types", "!CustomArcroleTypes!")]:
                        newViewsMenu.add_command(label=x[0][1:], underline=0, command=lambda a=x[1]: self.newView(a, tabWin))  # type: ignore[misc]
                else:
                    for viewParams in additionalViews:
                        newViewsMenu.add_command(
                            label=viewParams[2],
                            underline=0,
                            command=lambda a=additionalViewMethod, b=viewParams, c=additionalViews:  # type: ignore[misc]
                            a(self.modelXbrl, *b, additionalViews=c)
                        )
            except Exception as ex: # tkinter menu problem maybe
                self.modelXbrl.info("arelle:internalException",
                                    _("Exception creating context add-views menu in %(title)s: %(error)s"),
                                    modelObject=self.modelXbrl.modelDocument, title=self.tabTitle, error=str(ex))
                self.menu = None

    def newView(self, arcrole: str, tabWin: Notebook) -> None:
        if arcrole in ("!CustomRoleTypes!", "!CustomArcroleTypes!"):
            from arelle import ViewWinRoleTypes
            ViewWinRoleTypes.viewRoleTypes(self.modelXbrl, tabWin, arcrole=="!CustomArcroleTypes!", lang=self.lang)  # type: ignore[no-untyped-call]
        else:
            from arelle import ViewWinRelationshipSet
            ViewWinRelationshipSet.viewRelationshipSet(self.modelXbrl, tabWin, arcrole, lang=self.lang)  # type: ignore[no-untyped-call]

    def newArcroleGroupView(self, tabWin: Notebook) -> None:
        from arelle.DialogArcroleGroup import getArcroleGroup
        from arelle import ViewWinRelationshipSet
        arcroleGroup = getArcroleGroup(self.modelXbrl.modelManager.cntlr, self.modelXbrl)  # type: ignore[no-untyped-call]
        if arcroleGroup:
            ViewWinRelationshipSet.viewRelationshipSet(self.modelXbrl, tabWin, arcroleGroup, lang=self.lang)  # type: ignore[no-untyped-call]

    def setLang(self, lang: str) -> None:
        self.lang = lang
        self.view()  # type: ignore[misc]

    def setLabelrole(self, labelrole: str) -> None:
        self.labelrole = labelrole
        self.view()  # type: ignore[misc]

    def setNamestyle(self, isPrefixed: bool) -> None:
        self.nameIsPrefixed = isPrefixed
        self.view()  # type: ignore[misc]

    def setUnitDisplay(self, unitDisplayID: bool = False) -> None:
        self.unitDisplayID = unitDisplayID
        self.view()  # type: ignore[misc]

    def setColumnsSortable(
        self,
        treeColIsInt: bool = False,
        startUnsorted: bool = False,
        initialSortCol: str = "#0",
        initialSortDirForward: bool = True,
    ) -> None:
        if hasattr(self, "lastSortColumn") and self.lastSortColumn:
            self.treeView.heading(self.lastSortColumn, image=self.sortImages[2])
        self.lastSortColumn: str | None = None if startUnsorted else initialSortCol
        self.lastSortColumnForward = initialSortDirForward
        self.treeColIsInt = treeColIsInt
        if not hasattr(self, "sortImages"):
            self.sortImages: tuple[PhotoImage, PhotoImage, PhotoImage] = (
                PhotoImage(file=os.path.join(self.modelXbrl.modelManager.cntlr.imagesDir, "columnSortUp.gif")),
                PhotoImage(file=os.path.join(self.modelXbrl.modelManager.cntlr.imagesDir, "columnSortDown.gif")),
                PhotoImage(),
            )
        for col in ("#0",) + (self.treeView["columns"] or ()):
            self.treeView.heading(col, command=lambda c=col: self.sortColumn(c))  # type: ignore[misc]
        if not startUnsorted:
            self.treeView.heading(initialSortCol, image=self.sortImages[not initialSortDirForward])

    def colSortVal(self, node: str, col: str) -> str | int:
        if col == "#0":
            treeColVal = self.treeView.item(node)["text"]
            if self.treeColIsInt:
                return int(treeColVal)
        else:
            treeColVal = self.treeView.set(node, col)
            if col == "sequence":
                try:
                    return int(treeColVal)
                except:
                    return 0
        return treeColVal

    def sortNestedRows(self, parentNode: str, col: str, reverse: bool) -> None:
        l = [(self.colSortVal(node, col), node) for node in self.treeView.get_children(parentNode)]
        l.sort(reverse=reverse)
        # rearrange items in sorted positions
        for i, (cell, node) in enumerate(l):
            self.treeView.move(node, parentNode, i)
        # reset even/odd tags
        for i, node in enumerate(self.treeView.get_children(parentNode)):
            self.treeView.item(node, tags=("even" if i & 1 else "odd",))
            self.sortNestedRows(node, col, reverse)

    def sortColumn(self, col: str) -> None:
        if col == self.lastSortColumn:
            reverse = self.lastSortColumnForward
            self.lastSortColumnForward = not reverse
        else:
            if self.lastSortColumn:
                self.treeView.heading(self.lastSortColumn, image=self.sortImages[2])
            reverse = False
            self.lastSortColumnForward = True
            self.lastSortColumn = col
        self.treeView.heading(col, image=self.sortImages[reverse])
        self.sortNestedRows("", col, reverse)
        self.viewSelectionChange()  # reselect selected rows

    def copyCellToClipboard(self, *ignore: Any) -> None:
        self.modelXbrl.modelManager.cntlr.clipboardData(
            text=self.treeView.item(self.menuRow)["text"]
            if self.menuCol == "#0" else self.treeView.set(self.menuRow, self.menuCol)
        )

    def copyRowToClipboard(self, *ignore: Any) -> None:
        self.modelXbrl.modelManager.cntlr.clipboardData(
            text="\t".join([self.treeView.item(self.menuRow)["text"]] +
                           [self.treeView.set(self.menuRow,c) for c in self.treeView["columns"]]))

    def copyTableToClipboard(self, *ignore: Any) -> None:
        cols = self.treeView["columns"]
        lines = ["\t".join([self.treeView.heading("#0")["text"]] +
                           [self.treeView.heading(h)["text"] for h in cols])]
        self.tabLines("", "", cols, lines)
        self.modelXbrl.modelManager.cntlr.clipboardData(text='\n'.join(lines))

    def tabLines(self, parentNode: str, indent: str, cols: Iterable[str], lines: list[str]) -> None:
        for node in self.treeView.get_children(parentNode):
            lines.append("\t".join('"{}"'.format(c.replace('"', '""')) if (isinstance(c, str) and "\n" in c) else c
                                   for c in ([indent + self.treeView.item(node)["text"]] +
                                             [self.treeView.set(node, c) for c in cols])))
            self.tabLines(node, indent + "    ", cols, lines)
