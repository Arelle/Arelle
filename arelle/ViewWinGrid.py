"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle.UiUtil import scrolledHeaderedFrame
from arelle.ViewWinPane import ViewPane

if TYPE_CHECKING:
    from tkinter import Menu
    from tkinter.ttk import Notebook

    from arelle.ModelXbrl import ModelXbrl


class ViewGrid(ViewPane):
    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        tabWin: Notebook,
        tabTitle: str,
        hasToolTip: bool = False,
        lang: str | None = None,
    ) -> None:
        contentView = scrolledHeaderedFrame(tabWin)
        super(ViewGrid, self).__init__(modelXbrl, tabWin, tabTitle,
                                       contentView, hasToolTip=hasToolTip,  # type: ignore[arg-type]
                                       lang=lang)
        self.gridTblHdr = self.viewFrame.tblHdrInterior  # type: ignore[attr-defined]
        self.gridColHdr = self.viewFrame.colHdrInterior  # type: ignore[attr-defined]
        self.gridRowHdr = self.viewFrame.rowHdrInterior  # type: ignore[attr-defined]
        self.gridBody = self.viewFrame.bodyInterior  # type: ignore[attr-defined]

        self.gridTblHdr.contextMenuClick = self.contextMenuClick
        self.gridColHdr.contextMenuClick = self.contextMenuClick
        self.gridRowHdr.contextMenuClick = self.contextMenuClick
        self.gridBody.contextMenuClick = self.contextMenuClick

    def motion(self, *args: Any) -> None:
        '''
        tvColId = self.gridBody.identify_column(args[0].x)
        tvRowId = self.gridBody.identify_row(args[0].y)
        if tvColId != self.toolTipColId or tvRowId != self.toolTipRowId:
            self.toolTipColId = tvColId
            self.toolTipRowId = tvRowId
            newValue = None
            if tvRowId and len(tvRowId) > 0:
                try:
                    col = int(tvColId[1:])
                    if col == 0:
                        newValue = self.gridBody.item(tvRowId,"text")
                    else:
                        values = self.gridBody.item(tvRowId,"values")
                        if col <= len(values):
                            newValue = values[col - 1]
                except ValueError:
                    pass
            self.setToolTip(newValue, tvColId)
        '''

    def setToolTip(self, text: str | None, colId: str = "#0") -> None:
        self.toolTip._hide()
        if isinstance(text, str) and len(text) > 0:
            width = self.gridBody.column(colId, "width")
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

    def contextMenu(self) -> Menu:
        super(ViewGrid, self).contextMenu()
        self.bindContextMenu(self.gridBody)
        self.bindContextMenu(self.gridTblHdr)
        self.bindContextMenu(self.gridColHdr)
        self.bindContextMenu(self.gridRowHdr)
        return self.menu
