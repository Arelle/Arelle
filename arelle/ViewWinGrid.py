'''
Created on Oct 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *
from arelle.CntlrWinTooltip import ToolTip
from arelle.UiUtil import (scrolledHeaderedFrame, scrolledFrame)

class ViewGrid:
    def __init__(self, modelXbrl, tabWin, tabTitle, hasToolTip=False, lang=None):
        self.tabWin = tabWin
        #self.viewFrame = Frame(tabWin)
        #self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        '''
        paneWin = PanedWindow(self.viewFrame, orient=VERTICAL)
        paneWin.grid(row=1, column=0, sticky=(N, S, E, W))
        self.zGrid = scrollgrid(paneWin)
        self.zGrid.grid(row=0, column=0, sticky=(N, S, E, W))
        self.xyGrid = scrollgrid(paneWin)
        self.xyGrid.grid(row=1, column=0, sticky=(N, S, E, W))
        '''
        '''
        self.gridBody = scrollgrid(self.viewFrame)
        self.gridBody.grid(row=0, column=0, sticky=(N, S, E, W))
        '''
        
        self.viewFrame = scrolledHeaderedFrame(tabWin)
        self.gridTblHdr = self.viewFrame.tblHdrInterior
        self.gridColHdr = self.viewFrame.colHdrInterior
        self.gridRowHdr = self.viewFrame.rowHdrInterior
        self.gridBody = self.viewFrame.bodyInterior
        '''
        self.viewFrame = scrolledFrame(tabWin)
        self.gridTblHdr = self.gridRowHdr = self.gridColHdr = self.gridBody = self.viewFrame.interior
        '''
        
        tabWin.add(self.viewFrame,text=tabTitle)
        self.modelXbrl = modelXbrl
        self.hasToolTip = hasToolTip
        self.toolTipText = StringVar()
        if hasToolTip:
            self.gridBody.bind("<Motion>", self.motion, '+')
            self.gridBody.bind("<Leave>", self.leave, '+')
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(self.gridBody, 
                                   textvariable=self.toolTipText, 
                                   wraplength=480, 
                                   follow_mouse=True,
                                   state="disabled")
            self.toolTipColId = None
            self.toolTipRowId = None
        self.modelXbrl = modelXbrl
        self.contextMenuClick = self.modelXbrl.modelManager.cntlr.contextMenuClick
        self.gridTblHdr.contextMenuClick = self.contextMenuClick
        self.gridColHdr.contextMenuClick = self.contextMenuClick
        self.gridRowHdr.contextMenuClick = self.contextMenuClick
        self.gridBody.contextMenuClick = self.contextMenuClick
        self.lang = lang
        if modelXbrl:
            modelXbrl.views.append(self)
            if not lang: 
                self.lang = modelXbrl.modelManager.defaultLang
        
    def close(self):
        self.tabWin.forget(self.viewFrame)
        self.modelXbrl.views.remove(self)
        self.modelXbrl = None
        
    def select(self):
        self.tabWin.select(self.viewFrame)
        
    def leave(self, *args):
        self.toolTipColId = None
        self.toolTipRowId = None

    def motion(self, *args):
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
                
    def setToolTip(self, text, colId="#0"):
        self.toolTip._hide()
        if isinstance(text,str) and len(text) > 0:
            width = self.gridBody.column(colId,"width")
            if len(text) * 8 > width or '\n' in text:
                self.toolTipText.set(text)
                self.toolTip.configure(state="normal")
                self.toolTip._schedule()
            else:
                self.toolTipText.set("")
                self.toolTip.configure(state="disabled")
        else:
            self.toolTipText.set("")
            self.toolTip.configure(state="disabled")

    def contextMenu(self):
        try:
            return self.menu
        except AttributeError:
            self.menu = Menu( self.viewFrame, tearoff = 0 )
            self.gridBody.bind( self.contextMenuClick, self.popUpMenu )
            if not self.gridTblHdr.bind(self.contextMenuClick): 
                self.gridTblHdr.bind( self.contextMenuClick, self.popUpMenu )
            if not self.gridColHdr.bind(self.contextMenuClick): 
                self.gridColHdr.bind( self.contextMenuClick, self.popUpMenu )
            if not self.gridRowHdr.bind(self.contextMenuClick): 
                self.gridRowHdr.bind( self.contextMenuClick, self.popUpMenu )
            return self.menu

    def popUpMenu(self, event):
        self.menu.post( event.x_root, event.y_root )
        
    def menuAddLangs(self):
        langsMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("Language"), menu=langsMenu, underline=0)
        for lang in sorted(self.modelXbrl.langs):
            langsMenu.add_cascade(label=lang, underline=0, command=lambda l=lang: self.setLang(l))
    
    def setLang(self, lang):
        self.lang = lang
        self.view()

