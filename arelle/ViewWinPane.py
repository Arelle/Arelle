'''
@author: Acsone S. A.
See COPYRIGHT.md for copyright information.
'''
from tkinter import *
try:
    from tkinter.ttk import *
except ImportError:
    from ttk import *
from arelle.CntlrWinTooltip import ToolTip

class ViewPane:
    def __init__(self, modelXbrl, tabWin, tabTitle,
                 contentView, hasToolTip=False, lang=None):
        self.blockViewModelObject = 0
        self.tabWin = tabWin

        self.viewFrame = contentView
        self.viewFrame.view = self

        tabWin.add(self.viewFrame,text=tabTitle)
        self.modelXbrl = modelXbrl
        self.hasToolTip = hasToolTip
        self.toolTipText = StringVar()
        if hasToolTip:
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(self.gridBody,
                                   textvariable=self.toolTipText,
                                   wraplength=480,
                                   follow_mouse=True,
                                   state="disabled")
            self.toolTipColId = None
            self.toolTipRowId = None
        self.modelXbrl = modelXbrl
        modelManager = self.modelXbrl.modelManager
        self.contextMenuClick = modelManager.cntlr.contextMenuClick
        self.lang = lang
        if modelXbrl:
            modelXbrl.views.append(self)
            if not lang:
                self.lang = modelXbrl.modelManager.defaultLang

    def close(self):
        del self.viewFrame.view
        self.tabWin.forget(self.viewFrame)
        if self in self.modelXbrl.views:
            self.modelXbrl.views.remove(self)
        self.modelXbrl = None

    def select(self):
        self.tabWin.select(self.viewFrame)

    def onClick(self, *args):
        if self.modelXbrl:
            self.modelXbrl.modelManager.cntlr.currentView = self

    def leave(self, *args):
        self.toolTipColId = None
        self.toolTipRowId = None

    def motion(self, *args):
        pass


    def contextMenu(self):
        try:
            return self.menu
        except AttributeError:
            self.menu = Menu( self.viewFrame, tearoff = 0 )
            return self.menu

    def bindContextMenu(self, widget):
        if not widget.bind(self.contextMenuClick):
            widget.bind( self.contextMenuClick, self.popUpMenu )

    def popUpMenu(self, event):
        self.menu.post( event.x_root, event.y_root )

    def menuAddLangs(self):
        langsMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("Language"), menu=langsMenu, underline=0)
        for lang in sorted(self.modelXbrl.langs):
            langsMenu.add_cascade(label=lang, underline=0,
                                  command=lambda l=lang: self.setLang(l))

    def setLang(self, lang):
        self.lang = lang
        self.view()
