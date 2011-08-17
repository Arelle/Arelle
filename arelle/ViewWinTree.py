'''
Created on Oct 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *
from arelle.CntlrWinTooltip import ToolTip
import os

class ViewTree:
    def __init__(self, modelXbrl, tabWin, tabTitle, hasToolTip=False, lang=None):
        self.tabWin = tabWin
        self.viewFrame = Frame(tabWin)
        self.viewFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        tabWin.add(self.viewFrame,text=tabTitle)
        vScrollbar = Scrollbar(self.viewFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(self.viewFrame, orient=HORIZONTAL)
        self.treeView = Treeview(self.viewFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set)
        self.treeView.grid(row=0, column=0, sticky=(N, S, E, W))
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
        self.treeViewSelection = ()
        self.treeView.bind("<<TreeviewSelect>>", self.treeViewSelectionChange, '+')
        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        self.viewFrame.columnconfigure(0, weight=1)
        self.viewFrame.rowconfigure(0, weight=1)
        self.modelXbrl = modelXbrl
        self.hasToolTip = hasToolTip
        self.toolTipText = StringVar()
        if hasToolTip:
            self.treeView.bind("<Motion>", self.motion, '+')
            self.treeView.bind("<Leave>", self.leave, '+')
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(self.treeView, 
                                   textvariable=self.toolTipText, 
                                   wraplength=480, 
                                   follow_mouse=True,
                                   state="disabled")
            self.toolTipColId = None
            self.toolTipRowId = None
        self.modelXbrl = modelXbrl
        self.lang = lang
        self.labelrole = None
        self.nameIsPrefixed = False
        if modelXbrl:
            modelXbrl.views.append(self)
            if not lang: 
                self.lang = modelXbrl.modelManager.defaultLang
                
    def treeViewSelectionChange(self, event=None):
        for node in self.treeViewSelection:
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
            
    def close(self):
        if self.modelXbrl:
            self.tabWin.forget(self.viewFrame)
            self.modelXbrl.views.remove(self)
            self.modelXbrl = None
        
    def leave(self, *args):
        self.toolTipColId = None
        self.toolTipRowId = None

    def motion(self, *args):
        tvColId = self.treeView.identify_column(args[0].x)
        tvRowId = self.treeView.identify_row(args[0].y)
        if tvColId != self.toolTipColId or tvRowId != self.toolTipRowId:
            self.toolTipColId = tvColId
            self.toolTipRowId = tvRowId
            newValue = None
            if tvRowId and len(tvRowId) > 0:
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
                
    def setToolTip(self, text, colId="#0"):
        self.toolTip._hide()
        if isinstance(text,str) and len(text) > 0:
            width = self.treeView.column(colId,"width")
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
            self.treeView.bind( self.modelXbrl.modelManager.cntlr.contextMenuClick, self.popUpMenu, '+' )
            return self.menu

    def popUpMenu(self, event):
        self.menuRow = self.treeView.identify_row(event.y)
        self.menuCol = self.treeView.identify_column(event.x)
        self.menu.post( event.x_root, event.y_root )
        
    def expand(self):
        self.setTreeItemOpen(self.menuRow,open=True)
        
    def expandAll(self):
        self.setTreeItemOpen("",open=True)
        
    def collapse(self):
        self.setTreeItemOpen(self.menuRow,open=False)
        
    def collapseAll(self):
        self.setTreeItemOpen("",open=False)
        
    def setTreeItemOpen(self, node, open=True):
        if node:
            self.treeView.item(node, open=open)
        for childNode in self.treeView.get_children(node):
            self.setTreeItemOpen(childNode, open)
            
    def menuAddExpandCollapse(self):
        self.menu.add_cascade(label=_("Expand"), underline=0, command=self.expand)
        self.menu.add_cascade(label=_("Collapse"), underline=0, command=self.collapse)
        self.menu.add_cascade(label=_("Expand All"), underline=0, command=self.expandAll)
        self.menu.add_cascade(label=_("Collapse All"), underline=0, command=self.collapseAll)
        
    def menuAddClipboard(self):
        if self.modelXbrl.modelManager.cntlr.hasClipboard:
            clipboardMenu = Menu(self.viewFrame, tearoff=0)
            clipboardMenu.add_cascade(label=_("Cell"), underline=0, command=self.copyCellToClipboard)
            clipboardMenu.add_cascade(label=_("Row"), underline=0, command=self.copyRowToClipboard)
            clipboardMenu.add_cascade(label=_("Table"), underline=0, command=self.copyTableToClipboard)
            self.menu.add_cascade(label=_("Copy to clipboard"), menu=clipboardMenu, underline=0)
        
    def menuAddLangs(self):
        langsMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("Language"), menu=langsMenu, underline=0)
        for lang in sorted(self.modelXbrl.langs):
            langsMenu.add_cascade(label=lang, underline=0, command=lambda l=lang: self.setLang(l))

    def menuAddLabelRoles(self, includeConceptName=False, menulabel=None):
        if menulabel is None: menulabel = _("Label Role")
        rolesMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=menulabel, menu=rolesMenu, underline=0)
        from arelle.ModelRelationshipSet import labelroles
        for x in labelroles(self.modelXbrl, includeConceptName):
            rolesMenu.add_cascade(label=x[0][1:], underline=0, command=lambda a=x[1]: self.setLabelrole(a))

    def menuAddNameStyle(self, menulabel=None):
        if menulabel is None: menulabel = _("Name Style")
        nameStyleMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=menulabel, menu=nameStyleMenu, underline=0)
        from arelle.ModelRelationshipSet import labelroles
        nameStyleMenu.add_cascade(label=_("Prefixed"), underline=0, command=lambda a=True: self.setNamestyle(a))
        nameStyleMenu.add_cascade(label=_("No Prefix"), underline=0, command=lambda a=False: self.setNamestyle(a))

    def menuAddUnitDisplay(self):
        rolesMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("Units"), menu=rolesMenu, underline=0)
        rolesMenu.add_cascade(label=_("Unit ID"), underline=0, command=lambda: self.setUnitDisplay(unitDisplayID=True))
        rolesMenu.add_cascade(label=_("Measures"), underline=0, command=lambda: self.setUnitDisplay(unitDisplayID=False))

    def menuAddViews(self, addClose=True, tabWin=None):
        if tabWin is None: tabWin = self.tabWin
        viewMenu = Menu(self.viewFrame, tearoff=0)
        self.menu.add_cascade(label=_("View"), menu=viewMenu, underline=0)
        newViewsMenu = Menu(self.viewFrame, tearoff=0)
        if addClose:
            viewMenu.add_cascade(label=_("Close"), underline=0, command=self.close)
        viewMenu.add_cascade(label=_("Additional view"), menu=newViewsMenu, underline=0)
        from arelle.ModelRelationshipSet import baseSetArcroles
        for x in baseSetArcroles(self.modelXbrl):
            newViewsMenu.add_cascade(label=x[0][1:], underline=0, command=lambda a=x[1]: self.newView(a, tabWin))
    
    def newView(self, arcrole, tabWin):
        from arelle import ViewWinRelationshipSet
        ViewWinRelationshipSet.viewRelationshipSet(self.modelXbrl, tabWin, arcrole, lang=self.lang)
            
    def setLang(self, lang):
        self.lang = lang
        self.view()
        
    def setLabelrole(self, labelrole):
        self.labelrole = labelrole
        self.view()
        
    def setNamestyle(self, isPrefixed):
        self.nameIsPrefixed = isPrefixed
        self.view()
        
    def setUnitDisplay(self, unitDisplayID=False):
        self.unitDisplayID = unitDisplayID
        self.view()
        
    def setColumnsSortable(self, treeColIsInt=False, startUnsorted=False, initialSortCol="#0", initialSortDirForward=True):
        if hasattr(self, 'lastSortColumn') and self.lastSortColumn:
            self.treeView.heading(self.lastSortColumn, image=self.sortImages[2])
        self.lastSortColumn = None if startUnsorted else initialSortCol 
        self.lastSortColumnForward = initialSortDirForward
        self.treeColIsInt = treeColIsInt
        if not hasattr(self, "sortImages"):
            self.sortImages = (PhotoImage(file=os.path.join(self.modelXbrl.modelManager.cntlr.imagesDir, "columnSortUp.gif")),
                               PhotoImage(file=os.path.join(self.modelXbrl.modelManager.cntlr.imagesDir, "columnSortDown.gif")),
                               PhotoImage())
        for col in ("#0",) + self.treeView["columns"]:
            self.treeView.heading(col, command=lambda c=col: self.sortColumn(c))
        if not startUnsorted:
            self.treeView.heading(initialSortCol, image=self.sortImages[not initialSortDirForward])
            
    def colSortVal(self, node, col):
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
    
    def sortNestedRows(self, parentNode, col, reverse):
        l = [(self.colSortVal(node, col), node) for node in self.treeView.get_children(parentNode)]
        l.sort(reverse=reverse)
        # rearrange items in sorted positions     
        for i, (cell, node) in enumerate(l):         
            self.treeView.move(node, parentNode, i)
        # reset even/odd tags
        for i, node in enumerate(self.treeView.get_children(parentNode)):
            self.treeView.item(node, tags=('even' if i & 1 else 'odd',))
            self.sortNestedRows(node, col, reverse)
                    
    def sortColumn(self, col):
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
        self.sortNestedRows('', col, reverse)
        self.treeViewSelectionChange()  # reselect selected rows
        
    def copyCellToClipboard(self, *ignore):
        self.modelXbrl.modelManager.cntlr.clipboardData(
            text=self.treeView.item(self.menuRow)['text'] if self.menuCol == '#0' else self.treeView.set(self.menuRow,self.menuCol))
        
    def copyRowToClipboard(self, *ignore):
        self.modelXbrl.modelManager.cntlr.clipboardData(
            text='\t'.join([self.treeView.item(self.menuRow)['text']] +
                           [self.treeView.set(self.menuRow,c) for c in self.treeView['columns']]))
        
    def copyTableToClipboard(self, *ignore):
        cols = self.treeView['columns']
        lines = ['\t'.join([self.treeView.heading('#0')['text']] +
                           [self.treeView.heading(h)['text'] for h in cols])]
        self.tabLines('', '', cols, lines)
        self.modelXbrl.modelManager.cntlr.clipboardData(text='\n'.join(lines))

    def tabLines(self, parentNode, indent, cols, lines): 
        for node in self.treeView.get_children(parentNode):
            lines.append('\t'.join([indent + self.treeView.item(node)['text']] +
                                   [self.treeView.set(node,c) for c in cols]))
            self.tabLines(node, indent+'    ', cols, lines)
