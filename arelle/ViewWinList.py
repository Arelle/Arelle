"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from tkinter import N, S, E, W, VERTICAL, END, StringVar, Menu, Event, Listbox
from tkinter.ttk import Frame, Scrollbar, Notebook
from typing import TYPE_CHECKING, Any

from arelle.CntlrWinTooltip import ToolTip
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.Cntlr import Cntlr

_: TypeGetText


class ViewList:
    menu: Menu

    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        tabWin: Notebook,
        tabTitle: str,
        hasToolTip: bool = False,
    ) -> None:
        self.tabWin = tabWin
        self.viewFrame = Frame(tabWin)
        self.viewFrame.view = self  # type: ignore[attr-defined]
        self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        tabWin.add(self.viewFrame,text=tabTitle)
        xmlScrollbar = Scrollbar(self.viewFrame, orient=VERTICAL)
        self.listBox = Listbox(self.viewFrame, yscrollcommand=xmlScrollbar.set)
        self.listBox.grid(row=0, column=0, sticky=(N, S, E, W))
        self.listBox.bind("<Motion>", self.listBoxMotion, "+")
        self.listBox.bind("<1>", self.listBoxClick, "+")
        self.listBox.bind("<Leave>", self.listBoxLeave, "+")
        xmlScrollbar["command"] = self.listBox.yview
        xmlScrollbar.grid(row=0, column=1, sticky=(N, S))
        self.viewFrame.columnconfigure(0, weight=1)
        self.viewFrame.rowconfigure(0, weight=1)
        self.listBoxToolTipText = StringVar()
        if hasToolTip:
            self.listBoxToolTip = ToolTip(self.listBox, textvariable=self.listBoxToolTipText, wraplength=480, follow_mouse=True, state="disabled")
            self.listBoxRow = -9999999
        self.modelXbrl = modelXbrl
        if modelXbrl:
            modelXbrl.views.append(self)

    def close(self) -> None:
        del self.viewFrame.view  # type: ignore[attr-defined]
        self.tabWin.forget(self.viewFrame)
        self.modelXbrl.views.remove(self)  # type: ignore[union-attr]
        self.modelXbrl = None

    def select(self) -> None:
        self.tabWin.select(self.viewFrame)  # type: ignore[no-untyped-call]

    def append(self, line: str) -> None:
        self.listBox.insert(END, line)

    def clear(self) -> None:
        self.listBox.delete(0, END)

    def listBoxClick(self, *args: Any) -> None:
        if self.modelXbrl:
            self.modelXbrl.modelManager.cntlr.currentView = self  # type: ignore[attr-defined]

    def listBoxLeave(self, *args: Any) -> None:
        self.listBoxRow = -9999999

    def lines(self) -> Any:
        return self.listBox.get(0, END)

    def lineText(self, lineNumber: int) -> Any:
        return self.listBox.get(lineNumber)

    def selectLine(self, lineNumber: int) -> None:
        self.listBox.selection_clear(0, END)
        self.listBox.selection_set(lineNumber)

    def saveToFile(self, filename: str) -> None:
        with open(filename, "w") as fh:
            fh.writelines([logEntry + "\n" for logEntry in self.listBox.get(0, END)])

    def copyToClipboard(self, cntlr: Cntlr | None = None, *ignore: Any) -> None:
        if cntlr is None:
            cntlr = self.modelXbrl.modelManager.cntlr  # type: ignore[union-attr]
        cntlr.clipboardData(text="\n".join(self.listBox.get(0, END)))

    def listBoxMotion(self, *args: Any) -> None:
        lbRow = self.listBox.nearest(args[0].y)  # type: ignore[no-untyped-call]
        if lbRow != self.listBoxRow:
            self.listBoxRow = lbRow
            text = self.listBox.get(lbRow)
            self.listBoxToolTip._hide()
            if text and len(text) > 0:
                if len(text) * 8 > 200:
                    self.listBoxToolTipText.set(text[:2048] + "..." if len(text) > 2048 else text)
                    self.listBoxToolTip.configure(state="normal")
                    self.listBoxToolTip._schedule()
                else:
                    self.listBoxToolTipText.set("")
                    self.listBoxToolTip.configure(state="disabled")
            else:
                self.listBoxToolTipText.set("")
                self.listBoxToolTip.configure(state="disabled")

    def contextMenu(self, contextMenuClick: str | None = None) -> Menu:
        try:
            return self.menu
        except AttributeError:
            if contextMenuClick is None:
                assert self.modelXbrl is not None
                contextMenuClick = self.modelXbrl.modelManager.cntlr.contextMenuClick
            self.menu = Menu(self.viewFrame, tearoff = 0)
            self.listBox.bind(contextMenuClick, self.popUpMenu)
            return self.menu

    def popUpMenu(self, event: Event) -> None:
        self.menu.post(event.x_root, event.y_root)

    def menuAddSaveClipboard(self) -> None:
        self.menu.add_command(label=_("Save to file"), underline=0, command=self.modelXbrl.modelManager.cntlr.fileSave)  # type: ignore[union-attr]
        if self.modelXbrl.modelManager.cntlr.hasClipboard:  # type: ignore[union-attr]
            self.menu.add_command(label=_("Copy to clipboard"), underline=0, command=self.copyToClipboard)
