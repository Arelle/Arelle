'''
Created on Oct 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *

class ViewTree:
    def __init__(self, modelXbrl, tabWin, tabTitle):
        self.tabWin = tabWin
        self.viewFrame = Frame(tabWin)
        self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        tabWin.add(self.viewFrame,text=tabTitle)
        vScrollbar = Scrollbar(self.viewFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(self.viewFrame, orient=HORIZONTAL)
        self.treeView = Treeview(self.viewFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set)
        self.treeView.grid(row=0, column=0, sticky=(N, S, E, W))
        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        self.viewFrame.columnconfigure(0, weight=1)
        self.viewFrame.rowconfigure(0, weight=1)
        self.modelXbrl = modelXbrl
        modelXbrl.views.append(self)
        
    def close(self):
        self.tabWin.forget(self.viewFrame)
        self.modelXbrl.views.remove(self)
        self.modelXbrl = None
