'''
@author: Acsone S. A.
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from tkinter import Menu, StringVar
from tkinter.ttk import Frame
from typing import TYPE_CHECKING, Any

from arelle.CntlrWinTooltip import ToolTip
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from tkinter import Widget
    from tkinter.ttk import Notebook

    from arelle.ModelXbrl import ModelXbrl

_: TypeGetText


class ViewPane:
    def __init__(
        self,
        modelXbrl: ModelXbrl | None,
        tabWin: Notebook,
        tabTitle: str,
        contentView: Frame,
        hasToolTip: bool = False,
        lang: str | None = None,
    ) -> None:
        self.blockViewModelObject = 0
        self.tabWin = tabWin

        self.viewFrame = contentView
        self.viewFrame.view = self  # type: ignore[attr-defined]

        tabWin.add(self.viewFrame, text=tabTitle)
        self.modelXbrl = modelXbrl
        self.hasToolTip = hasToolTip
        self.toolTipText = StringVar()
        if hasToolTip:
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(
                self.gridBody,  # type: ignore[attr-defined]
                textvariable=self.toolTipText,
                wraplength=480,
                follow_mouse=True,
                state="disabled",
            )
            self.toolTipColId: str | None = None
            self.toolTipRowId: str | None = None
        self.modelXbrl = modelXbrl
        modelManager = self.modelXbrl.modelManager  # type: ignore[union-attr]
        self.contextMenuClick = modelManager.cntlr.contextMenuClick
        self.lang = lang
        if modelXbrl:
            modelXbrl.views.append(self)
            if not lang:
                self.lang = modelXbrl.modelManager.defaultLang

    def close(self) -> None:
        del self.viewFrame.view  # type: ignore[attr-defined]
        self.tabWin.forget(self.viewFrame)
        if self in self.modelXbrl.views:  # type: ignore[union-attr]
            self.modelXbrl.views.remove(self)  # type: ignore[union-attr]
        self.modelXbrl = None

    def select(self) -> None:
        self.tabWin.select(self.viewFrame)  # type: ignore[no-untyped-call]

    def onClick(self, *args: Any) -> None:
        if self.modelXbrl:
            self.modelXbrl.modelManager.cntlr.currentView = self  # type: ignore[attr-defined]

    def leave(self, *args: Any) -> None:
        self.toolTipColId = None
        self.toolTipRowId = None

    def motion(self, *args: Any) -> None:
        pass

    def contextMenu(self) -> Menu:
        try:
            return self.menu
        except AttributeError:
            self.menu: Menu = Menu(self.viewFrame, tearoff=0)
            return self.menu

    def bindContextMenu(self, widget: Widget) -> None:
        if not widget.bind(self.contextMenuClick):
            widget.bind(self.contextMenuClick, self.popUpMenu)

    def popUpMenu(self, event: Any) -> None:
        self.menu.post(event.x_root, event.y_root)

    def menuAddLangs(self) -> None:
        langsMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("Language"), menu=langsMenu, underline=0)
        for lang in sorted(self.modelXbrl.langs):  # type: ignore[union-attr]
            langsMenu.add_cascade(label=lang, underline=0,
                                  command=lambda l=lang: self.setLang(l))  # type: ignore[misc]

    def setLang(self, lang: str) -> None:
        self.lang = lang
        self.view()  # type: ignore[attr-defined]
