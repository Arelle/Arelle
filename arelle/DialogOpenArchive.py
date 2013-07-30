'''
Created on Oct 20, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from tkinter import Toplevel, StringVar, VERTICAL, HORIZONTAL, N, S, E, W, messagebox
try:
    from tkinter.ttk import Frame, Button, Treeview, Scrollbar
except ImportError:
    from ttk import Frame, Button, Treeview, Scrollbar
import re, os, sys
from arelle.CntlrWinTooltip import ToolTip
from arelle.UrlUtil import isHttpUrl
from arelle.TaxonomyPackage import parseTxmyPkg

'''
caller checks accepted, if True, caller retrieves url
'''

ARCHIVE = 1
ENTRY_POINTS = 2
DISCLOSURE_SYSTEM = 3

def askArchiveFile(mainWin, filesource):
    filenames = filesource.dir
    if filenames is not None:   # an IO or other error can return None
        
        if filesource.isTaxonomyPackage:            
            dialog = DialogOpenArchive(mainWin, 
                                       ENTRY_POINTS, 
                                       filesource, 
                                       filenames,
                                       _("Select Entry Point"), 
                                       _("File"),
                                       showAltViewButton=True)
        else:
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
    if dialog and dialog.accepted:
        return disclosureSystem.selection
    return None


class DialogOpenArchive(Toplevel):
    def __init__(self, mainWin, openType, filesource, filenames, title, colHeader, showAltViewButton=False):
        parent = mainWin.parent
        super(DialogOpenArchive, self).__init__(parent)
        self.parent = parent
        self.showAltViewButton = showAltViewButton
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False

        self.transient(self.parent)
        
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
        
        mainWin.showStatus(_("loading archive {0}").format(filesource.url))
        self.filesource = filesource
        self.filenames = filenames
        self.selection = filesource.selection
        self.hasToolTip = False
        selectedNode = None

        if openType == ENTRY_POINTS:
            try:
                metadataFiles = filesource.taxonomyPackageMetadataFiles
                if len(metadataFiles) != 1:
                    raise IOError(_("Taxonomy package contained more than one metadata file: {0}.")
                                  .format(', '.join(metadataFiles)))
                metadataFile = metadataFiles[0]
                metadata = filesource.file(filesource.url + os.sep + metadataFile)[0]
                self.metadataFilePrefix = os.sep.join(os.path.split(metadataFile)[:-1])
                if self.metadataFilePrefix:
                    self.metadataFilePrefix += os.sep
        
                self.nameToUrls, self.remappings = parseTxmyPkg(mainWin, metadata)
            except Exception as e:
                self.close()
                err = _("Failed to parse metadata; the underlying error was: {0}").format(e)
                messagebox.showerror(_("Malformed taxonomy package"), err)
                mainWin.addToLog(err)
                return
    
        mainWin.showStatus(None)
        
        if openType == DISCLOSURE_SYSTEM:
            y = 3
        else:
            y = 1

        okButton = Button(frame, text=_("OK"), command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        okButton.grid(row=y, column=2, sticky=(S,E,W), pady=3)
        cancelButton.grid(row=y, column=3, sticky=(S,E,W), pady=3, padx=3)
        
        if showAltViewButton:
            self.altViewButton = Button(frame, command=self.showAltView)
            self.altViewButton.grid(row=y, column=0, sticky=(S,W), pady=3, padx=3)
        
        self.loadTreeView(openType, colHeader, title)

        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(0, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)
        
        self.toolTipText = StringVar()
        if self.hasToolTip:
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
        
    def loadTreeView(self, openType, title, colHeader):
        self.title(title)
        self.openType = openType
        selectedNode = None

        # clear previous treeview entries
        for previousNode in self.treeView.get_children(""): 
            self.treeView.delete(previousNode)

        # set up treeView widget and tabbed pane
        if openType in (ARCHIVE, DISCLOSURE_SYSTEM):
            self.treeView.column("#0", width=500, anchor="w")
            self.treeView.heading("#0", text=colHeader)
            try:
                self.isRss = self.filesource.isRss
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
                self.treeView["columns"] = tuple()
        
            loadedPaths = []
            for i, filename in enumerate(self.filenames):
                if isinstance(filename,tuple):
                    if self.isRss:
                        form, date, instDoc = filename[2:5]
                    filename = filename[0] # ignore tooltip
                    self.hasToolTip = True
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
                if self.selection == filename:
                    selectedNode = node
                loadedPaths.append(path)

        elif openType == ENTRY_POINTS:
            self.treeView.column("#0", width=150, anchor="w")
            self.treeView.heading("#0", text="Name")
    
            self.treeView["columns"] = ("url",)
            self.treeView.column("url", width=350, anchor="w")
            self.treeView.heading("url", text="URL")
            
            for name, urls in self.nameToUrls.items():
                displayUrl = urls[1] # display the canonical URL
                self.treeView.insert("", "end", name, values=[displayUrl], text=name)
                
            self.hasToolTip = True
        else: # unknown openType
            return None
        if selectedNode:
            self.treeView.see(selectedNode)
            self.treeView.selection_set(selectedNode)

        if self.showAltViewButton:
            self.altViewButton.config(text=_("Show Files") if openType == ENTRY_POINTS else _("Show Entries"))

        
    def ok(self, event=None):
        selection = self.treeView.selection()
        if len(selection) > 0:
            if hasattr(self, "remappings"):
                # load file source remappings
                self.filesource.mappedPaths = \
                    dict((prefix, 
                          remapping if isHttpUrl(remapping)
                          else (self.filesource.baseurl + os.sep + self.metadataFilePrefix +remapping.replace("/", os.sep)))
                          for prefix, remapping in self.remappings.items())
            if self.openType in (ARCHIVE, DISCLOSURE_SYSTEM):
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
            elif self.openType == ENTRY_POINTS:
                epName = selection[0]
                #index 0 is the remapped Url, as opposed to the canonical one used for display
                urlOrFile = self.nameToUrls[epName][0]
                    
                if not urlOrFile.endswith("/"):
                    # check if it's an absolute URL rather than a path into the archive
                    if isHttpUrl(urlOrFile):
                        self.filesource.select(urlOrFile)  # absolute path selection
                    else:
                        # assume it's a path inside the archive:
                        self.filesource.select(self.metadataFilePrefix + urlOrFile)
                    self.accepted = True
                    self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
        
    def showAltView(self, event=None):
        if self.openType == ENTRY_POINTS:
            self.loadTreeView(ARCHIVE, _("Select Entry Point"), _("File"))
        else:
            self.loadTreeView(ENTRY_POINTS, _("Select Archive File"), _("File"))
        
    def leave(self, *args):
        self.toolTipRowId = None

    def motion(self, *args):
        tvRowId = self.treeView.identify_row(args[0].y)
        if tvRowId != self.toolTipRowId:
            text = None
            if self.openType in (ARCHIVE, DISCLOSURE_SYSTEM):
                self.toolTipRowId = tvRowId
                if tvRowId and len(tvRowId) > 4:
                    try:
                        text = self.filenames[ int(tvRowId[4:]) ]
                        if isinstance(text, tuple):
                            text = text[1].replace("\\n","\n")
                    except (KeyError, ValueError):
                        pass
            elif self.openType == ENTRY_POINTS:
                try:
                    epUrl = self.nameToUrls[tvRowId][1]
                    text = "{0}\n{1}".format(tvRowId, epUrl)
                except KeyError:
                    pass
            self.setToolTip(text)
                
    def setToolTip(self, text):
        self.toolTip._hide()
        if text:
            self.toolTipText.set(text)
            self.toolTip.configure(state="normal")
            self.toolTip._schedule()
        else:
            self.toolTipText.set("")
            self.toolTip.configure(state="disabled")

