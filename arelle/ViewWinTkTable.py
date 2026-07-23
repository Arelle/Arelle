"""
@author: Acsone S. A.
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Callable
from tkinter import Menu
from typing import TYPE_CHECKING, Any

from arelle.UITkTable import ScrolledTkTableFrame
from arelle.ViewWinPane import ViewPane

if TYPE_CHECKING:
    from tkinter.ttk import Notebook

    from arelle.ModelXbrl import ModelXbrl


class ViewTkTable(ViewPane):
    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        tabWin: Notebook,
        tabTitle: str,
        hasToolTip: bool = False,
        lang: str | None = None,
        browseCmd: Callable[..., Any] | None = None,
    ) -> None:
        contentView = ScrolledTkTableFrame(tabWin, browseCmd)
        super(ViewTkTable, self).__init__(modelXbrl, tabWin, tabTitle,
                                       contentView, hasToolTip=hasToolTip,
                                       lang=lang)
        self.viewFrame: ScrolledTkTableFrame = contentView
        self.table = self.viewFrame.table
        self.setHeightAndWidth()
        self.table.contextMenuClick = self.contextMenuClick

    def contextMenu(self) -> Menu:
        super(ViewTkTable, self).contextMenu()
        self.bindContextMenu(self.table)
        return self.menu

    def setHeightAndWidth(self) -> None:
        frameWidth = self.tabWin.winfo_width()
        frameHeight = self.tabWin.winfo_height()
        self.table.configure(maxheight=frameHeight - self.viewFrame.horizontalScrollbarHeight,  # type: ignore[call-arg]
                          maxwidth=frameWidth - self.viewFrame.verticalScrollbarWidth)
