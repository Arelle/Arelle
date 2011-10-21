'''
Created on Oct 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import *
from tkinter.ttk import *
import re, os
from arelle.CntlrWinTooltip import ToolTip
from arelle.DialogOpenTaxonomyPackage import TAXONOMY_PACKAGE_FILE_NAME, askForEntryPoint

'''
caller checks accepted, if True, caller retrieves url
'''

ARCHIVE = 1
DISCLOSURE_SYSTEM = 2

def askArchiveFile(mainWin, filesource):
    filenames = filesource.dir
    if filenames is not None:   # an IO or other error can return None
        
        # use alternate dialog if taxonomy package file is found
        if TAXONOMY_PACKAGE_FILE_NAME in filenames:
            return askForEntryPoint(mainWin, filesource)
        
        dialog = DialogOpenArchive(mainWin, 
                                   ARCHIVE, 
                                   filesource, 
                                   filenames,
                                   _("Select Archive File"), 
                                   _("File"))
        if dialog.accepted:
            return filesource.url
    return None

def selectDisclosureSystem(mainWin, disclosureSystem):
    dialog = DialogOpenArchive(mainWin, 
                               DISCLOSURE_SYSTEM, 
                               disclosureSystem, 
                               disclosureSystem.dir, 
                               _("Select Disclosure System"), 
                               _("Disclosure System"))
    if dialog.accepted:
        return disclosureSystem.selection
    return None


class DialogOpenArchive(Toplevel):
    def __init__(self, mainWin, openType, filesource, filenames, title, colHeader):
        parent = mainWin.parent
        super().__init__(parent)
        self.parent = parent
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False

        self.transient(self.parent)
        self.title(title)
        
        frame = Frame(self)

        treeFrame = Frame(frame, width=500)
        vScrollbar = Scrollbar(treeFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(treeFrame, orient=HORIZONTAL)
        self.treeView = Treeview(treeFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set)
        self.treeView.grid(row=0, column=0, sticky=(N, S, E, W))
        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        treeFrame.columnconfigure(0, weight=1)
        treeFrame.rowconfigure(0, weight=1)
        treeFrame.grid(row=0, column=0, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.treeView.focus_set()
        
        # set up treeView widget and tabbed pane
        self.treeView.column("#0", width=500, anchor="w")
        self.treeView.heading("#0", text=colHeader)
        try:
            self.isRss = filesource.isRss
            if self.isRss:
                self.treeView.column("#0", width=350, anchor="w")
                self.treeView["columns"] = ("descr", "date", "instDoc")
                self.treeView.column("descr", width=50, anchor="center", stretch=False)
                self.treeView.heading("descr", text="Form")
                self.treeView.column("date", width=170, anchor="w", stretch=False)
                self.treeView.heading("date", text="Pub Date")
                self.treeView.column("instDoc", width=200, anchor="w", stretch=False)
                self.treeView.heading("instDoc", text="Instance Document")
        except AttributeError:
            self.isRss = False
        
        mainWin.showStatus(_("loading archive {0}").format(filesource.url))
        self.filesource = filesource
        self.filenames = filenames
        selection = filesource.selection
        hasToolTip = False
        loadedPaths = []
        i = 0
        selectedNode = None
        for filename in self.filenames:
            if isinstance(filename,tuple):
                if self.isRss:
                    form, date, instDoc = filename[2:5]
                filename = filename[0] # ignore tooltip
                hasToolTip = True
            if filename.endswith("/"):
                filename = filename[:-1]
            path = filename.split("/")
            if not self.isRss and len(path) > 1 and path[:-1] in loadedPaths:
                parent = "file{0}".format(loadedPaths.index(path[:-1]))
            else:
                parent = "" 
            node = self.treeView.insert(parent, "end", "file{0}".format(i), text=path[-1])
            if self.isRss:
                self.treeView.set(node, "descr", form)
                self.treeView.set(node, "date", date)
                self.treeView.set(node, "instDoc", os.path.basename(instDoc))
            if selection == filename:
                selectedNode = node
            loadedPaths.append(path)
            i += 1
        if selectedNode:
            self.treeView.see(selectedNode)
            self.treeView.selection_set(selectedNode)
        mainWin.showStatus(None)
        
        if openType == DISCLOSURE_SYSTEM:
            y = 3
        else:
            y = 1

        okButton = Button(frame, text=_("OK"), command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        okButton.grid(row=y, column=2, sticky=(S,E,W), pady=3)
        cancelButton.grid(row=y, column=3, sticky=(S,E,W), pady=3, padx=3)
        
        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(0, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)
        
        self.toolTipText = StringVar()
        if hasToolTip:
            self.treeView.bind("<Motion>", self.motion, '+')
            self.treeView.bind("<Leave>", self.leave, '+')
            self.toolTipText = StringVar()
            self.toolTip = ToolTip(self.treeView, 
                                   textvariable=self.toolTipText, 
                                   wraplength=640, 
                                   follow_mouse=True,
                                   state="disabled")
            self.toolTipRowId = None

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)
        
    def ok(self, event=None):
        selection = self.treeView.selection()
        if len(selection) > 0:
            filename = self.filenames[int(selection[0][4:])]
            if isinstance(filename,tuple):
                if self.isRss:
                    filename = filename[4]
                else:
                    filename = filename[0]
            if not filename.endswith("/"):
                self.filesource.select(filename)
                self.accepted = True
                self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
        
    def leave(self, *args):
        self.toolTipRowId = None

    def motion(self, *args):
        tvRowId = self.treeView.identify_row(args[0].y)
        if tvRowId != self.toolTipRowId:
            self.toolTipRowId = tvRowId
            newFileIndex = -1
            if tvRowId and len(tvRowId) > 4:
                try:
                    newFileIndex = int(tvRowId[4:])
                except ValueError:
                    pass
            self.setToolTip(newFileIndex)
                
    def setToolTip(self, fileIndex):
        self.toolTip._hide()
        if fileIndex >= 0 and fileIndex < len(self.filenames):
            filenameItem = self.filenames[fileIndex]
            if isinstance(filenameItem, tuple):
                self.toolTipText.set(filenameItem[1].replace("\\n","\n"))
                self.toolTip.configure(state="normal")
                self.toolTip._schedule()
            else:
                self.toolTipText.set("")
                self.toolTip.configure(state="disabled")
        else:
            self.toolTipText.set("")
            self.toolTip.configure(state="disabled")
