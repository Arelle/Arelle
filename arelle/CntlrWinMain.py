'''
Created on Oct 3, 2010

This module is Arelle's controller in windowing interactive UI mode

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, subprocess, pickle, time, locale, re
from tkinter import *
import tkinter.tix
from tkinter.ttk import *
import tkinter.filedialog
import tkinter.messagebox, traceback
from arelle.Locale import format_string
from arelle.CntlrWinTooltip import ToolTip
from arelle import XbrlConst
import gettext

import threading, queue

from arelle import Cntlr
from arelle import (DialogURL, 
                ModelDocument,
                ModelManager,
                ViewWinDTS,
                ViewWinProperties, ViewWinConcepts, ViewWinRelationshipSet, ViewWinFormulae,
                ViewWinFactList, ViewWinFactTable, ViewWinRenderedGrid, ViewWinXml,
                ViewWinTests, ViewWinVersReport, ViewWinRssFeed,
                ViewCsvTests,
                Updater
               )
from arelle.ModelFormulaObject import FormulaOptions
from arelle.ModelRssItem import RssWatchOptions
from arelle.FileSource import openFileSource

restartMain = True

class CntlrWinMain (Cntlr.Cntlr):

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.filename = None
        self.dirty = False
        overrideLang = self.config.get("overrideLang")
        self.lang = overrideLang if overrideLang else self.modelManager.defaultLang
        self.data = {}
        
        imgpath = self.imagesDir + os.sep

        self.isMac = sys.platform == "darwin"
        self.isMSW = sys.platform.startswith("win")
        if self.isMSW:
            icon = imgpath + "arelle.ico"
            parent.iconbitmap(icon, default=icon)
            #image = PhotoImage(file=path + "arelle32.gif")
            #label = Label(None, image=image)
            #parent.iconwindow(label)
        else:
            parent.iconbitmap("@" + imgpath + "arelle.xbm")
            # try with gif file
            #parent.iconbitmap(path + "arelle.gif")

        self.menubar = Menu(self.parent)
        self.parent["menu"] = self.menubar
        
        self.fileMenu = Menu(self.menubar, tearoff=0)
        self.fileMenuLength = 1
        for label, command, shortcut_text, shortcut in (
                #(_("New..."), self.fileNew, "Ctrl+N", "<Control-n>"),
                (_("Open File..."), self.fileOpen, "Ctrl+O", "<Control-o>"),
                (_("Open Web..."), self.webOpen, "Shift+Alt+O", "<Shift-Alt-o>"),
                (_("Import File..."), self.importOpen, None, None),
                (_("Save..."), self.fileSave, "Ctrl+S", "<Control-s>"),
                (_("Close"), self.fileClose, "Ctrl+W", "<Control-w>"),
                (None, None, None, None),
                (_("Quit"), self.quit, "Ctrl+Q", "<Control-q>"),
                #(_("Restart"), self.restart, None, None),
                (None, None, None, None),
                ("",None,None,None) # position for file history
                ):
            if label is None:
                self.fileMenu.add_separator()
            else:
                self.fileMenu.add_command(label=label, underline=0, command=command, accelerator=shortcut_text)
                self.parent.bind(shortcut, command)
                self.fileMenuLength += 1
        self.loadFileMenuHistory()
        self.menubar.add_cascade(label=_("File"), menu=self.fileMenu, underline=0)
        
        toolsMenu = Menu(self.menubar, tearoff=0)
        
        validateMenu = Menu(self.menubar, tearoff=0)
        toolsMenu.add_cascade(label=_("Validation"), menu=validateMenu, underline=0)
        validateMenu.add_command(label=_("Validate"), underline=0, command=self.validate)
        self.modelManager.validateDisclosureSystem = self.config.setdefault("validateDisclosureSystem",False)
        self.validateDisclosureSystem = BooleanVar(value=self.modelManager.validateDisclosureSystem)
        self.validateDisclosureSystem.trace("w", self.setValidateDisclosureSystem)
        validateMenu.add_checkbutton(label=_("Disclosure system checks"), underline=0, variable=self.validateDisclosureSystem, onvalue=True, offvalue=False)
        validateMenu.add_command(label=_("Select disclosure system..."), underline=0, command=self.selectDisclosureSystem)
        self.modelManager.validateCalcLB = self.config.setdefault("validateCalcLB",False)
        self.validateCalcLB = BooleanVar(value=self.modelManager.validateCalcLB)
        self.validateCalcLB.trace("w", self.setValidateCalcLB)
        validateMenu.add_checkbutton(label=_("Calc Linkbase checks"), underline=0, variable=self.validateCalcLB, onvalue=True, offvalue=False)
        self.modelManager.validateInferDecimals = self.config.setdefault("validateInferDecimals",False)
        self.validateInferDecimals = BooleanVar(value=self.modelManager.validateInferDecimals)
        self.validateInferDecimals.trace("w", self.setValidateInferDecimals)
        validateMenu.add_checkbutton(label=_("Infer Decimals in calculations"), underline=0, variable=self.validateInferDecimals, onvalue=True, offvalue=False)
        self.modelManager.validateUtr = self.config.setdefault("validateUtr",True)
        self.validateUtr = BooleanVar(value=self.modelManager.validateUtr)
        self.validateUtr.trace("w", self.setValidateUtr)
        validateMenu.add_checkbutton(label=_("Unit Type Registry validation"), underline=0, variable=self.validateUtr, onvalue=True, offvalue=False)

        formulaMenu = Menu(self.menubar, tearoff=0)
        formulaMenu.add_command(label=_("Parameters..."), underline=0, command=self.formulaParametersDialog)

        toolsMenu.add_cascade(label=_("Formula"), menu=formulaMenu, underline=0)
        self.modelManager.formulaOptions = self.config.setdefault("formulaOptions",FormulaOptions())

        toolsMenu.add_command(label=_("Compare DTSes..."), underline=0, command=self.compareDTSes)
        cacheMenu = Menu(self.menubar, tearoff=0)
        
        rssWatchMenu = Menu(self.menubar, tearoff=0)
        rssWatchMenu.add_command(label=_("Options..."), underline=0, command=self.rssWatchOptionsDialog)
        rssWatchMenu.add_command(label=_("Start"), underline=0, command=lambda: self.rssWatchControl(start=True))
        rssWatchMenu.add_command(label=_("Stop"), underline=0, command=lambda: self.rssWatchControl(stop=True))

        toolsMenu.add_cascade(label=_("RSS Watch"), menu=rssWatchMenu, underline=0)
        self.modelManager.rssWatchOptions = self.config.setdefault("rssWatchOptions",RssWatchOptions())

        toolsMenu.add_cascade(label=_("Internet"), menu=cacheMenu, underline=0)
        self.webCache.workOffline  = self.config.setdefault("workOffline",False)
        self.workOffline = BooleanVar(value=self.webCache.workOffline)
        self.workOffline.trace("w", self.setWorkOffline)
        cacheMenu.add_checkbutton(label=_("Work offline"), underline=0, variable=self.workOffline, onvalue=True, offvalue=False)
        cacheMenu.add_command(label=_("Clear cache"), underline=0, command=self.confirmClearWebCache)
        cacheMenu.add_command(label=_("Manage cache"), underline=0, command=self.manageWebCache)
        cacheMenu.add_command(label=_("Proxy Server"), underline=0, command=self.setupProxy)
        
        logmsgMenu = Menu(self.menubar, tearoff=0)
        toolsMenu.add_cascade(label=_("Messages log"), menu=logmsgMenu, underline=0)
        logmsgMenu.add_command(label=_("Clear"), underline=0, command=self.logClear)
        logmsgMenu.add_command(label=_("Save to file"), underline=0, command=self.logSaveToFile)

        toolsMenu.add_cascade(label=_("Language..."), underline=0, command=self.languagesDialog)

        self.menubar.add_cascade(label=_("Tools"), menu=toolsMenu, underline=0)

        helpMenu = Menu(self.menubar, tearoff=0)
        for label, command, shortcut_text, shortcut in (
                (_("Check for updates"), lambda: Updater.checkForUpdates(self), None, None),
                (None, None, None, None),
                (_("About..."), self.helpAbout, None, None),
                ):
            if label is None:
                helpMenu.add_separator()
            else:
                helpMenu.add_command(label=label, underline=0, command=command, accelerator=shortcut_text)
                self.parent.bind(shortcut, command)
        self.menubar.add_cascade(label=_("Help"), menu=helpMenu, underline=0)

        windowFrame = Frame(self.parent)

        self.statusbar = Label(windowFrame, text=_("Ready..."), anchor=W)
        self.statusbarTimerId  = self.statusbar.after(5000, self.uiClearStatusTimerEvent)
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky=EW)
        
        #self.balloon = tkinter.tix.Balloon(windowFrame, statusbar=self.statusbar)
        self.toolbar_images = []
        toolbar = Frame(windowFrame)
        menubarColumn = 0
        self.validateTooltipText = StringVar()
        for image, command, toolTip, statusMsg in (
                #("images/toolbarNewFile.gif", self.fileNew),
                ("toolbarOpenFile.gif", self.fileOpen, _("Open local file"), _("Open by choosing a local XBRL file, testcase, or archive file")),
                ("toolbarOpenWeb.gif", self.webOpen, _("Open web file"), _("Enter an http:// URL of an XBRL file or testcase")),
                ("toolbarSaveFile.gif", self.fileSave, _("Save file"), _("Saves currently selected local XBRL file")),
                ("toolbarClose.gif", self.fileClose, _("Close"), _("Closes currently selected instance/DTS or testcase(s)")),
                (None,None,None,None),
                ("toolbarFindMenu.gif", self.find, _("Find"), _("Find dialog for scope and method of searching")),
                (None,None,None,None),
                ("toolbarValidate.gif", self.validate, self.validateTooltipText, _("Validate currently selected DTS or testcase(s)")),
                ("toolbarCompare.gif", self.compareDTSes, _("Compare DTSes"), _("compare two DTSes")),
                (None,None,None,None),
                ("toolbarLogClear.gif", self.logClear, _("Messages Log | Clear"), _("Clears the messages log")),
                #(Combobox(toolbar, textvariable=self.findVar, values=self.findValues,
                #          ), self.logClear, _("Find options"), _("Select of find options")),
                ):
            if command is None:
                tbControl = Separator(toolbar, orient=VERTICAL)
                tbControl.grid(row=0, column=menubarColumn, padx=6)
            elif isinstance(image, Combobox):
                tbControl = image
                tbControl.grid(row=0, column=menubarColumn)
            else:
                image = os.path.join(self.imagesDir, image)
                try:
                    image = PhotoImage(file=image)
                    self.toolbar_images.append(image)
                    tbControl = Button(toolbar, image=image, command=command, style="Toolbutton")
                    tbControl.grid(row=0, column=menubarColumn)
                except TclError as err:
                    print(err)
            if isinstance(toolTip,StringVar):
                ToolTip(tbControl, textvariable=toolTip, wraplength=240)
            else:
                ToolTip(tbControl, text=toolTip)
            menubarColumn += 1
        toolbar.grid(row=0, column=0, sticky=(N, W))

        paneWinTopBtm = PanedWindow(windowFrame, orient=VERTICAL)
        paneWinTopBtm.grid(row=1, column=0, sticky=(N, S, E, W))
        paneWinLeftRt = tkinter.PanedWindow(paneWinTopBtm, orient=HORIZONTAL)
        paneWinLeftRt.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinTopBtm.add(paneWinLeftRt)
        self.tabWinTopLeft = Notebook(paneWinLeftRt, width=250, height=300)
        self.tabWinTopLeft.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinLeftRt.add(self.tabWinTopLeft)
        self.tabWinTopRt = Notebook(paneWinLeftRt)
        self.tabWinTopRt.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinLeftRt.add(self.tabWinTopRt)
        self.tabWinBtm = Notebook(paneWinTopBtm)
        self.tabWinBtm.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinTopBtm.add(self.tabWinBtm)

        from arelle import ViewWinList
        self.logView = ViewWinList.ViewList(None, self.tabWinBtm, _("messages"), True)
        logViewMenu = self.logView.contextMenu(contextMenuClick=self.contextMenuClick)
        logViewMenu.add_command(label=_("Clear"), underline=0, command=self.logClear)
        logViewMenu.add_command(label=_("Save to file"), underline=0, command=self.logSaveToFile)
        if self.hasClipboard:
            logViewMenu.add_command(label=_("Copy to clipboard"), underline=0, command=lambda: self.logView.copyToClipboard(cntlr=self))
        
        windowFrame.grid(row=0, column=0, sticky=(N,S,E,W))
        
        windowFrame.columnconfigure(0, weight=999)
        windowFrame.columnconfigure(1, weight=1)
        windowFrame.rowconfigure(0, weight=1)
        windowFrame.rowconfigure(1, weight=999)
        windowFrame.rowconfigure(2, weight=1)
        paneWinTopBtm.columnconfigure(0, weight=1)
        paneWinTopBtm.rowconfigure(0, weight=1)
        paneWinLeftRt.columnconfigure(0, weight=1)
        paneWinLeftRt.rowconfigure(0, weight=1)
        self.tabWinTopLeft.columnconfigure(0, weight=1)
        self.tabWinTopLeft.rowconfigure(0, weight=1)
        self.tabWinTopRt.columnconfigure(0, weight=1)
        self.tabWinTopRt.rowconfigure(0, weight=1)
        self.tabWinBtm.columnconfigure(0, weight=1)
        self.tabWinBtm.rowconfigure(0, weight=1)
        
        
        window = self.parent.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        
        priorState = self.config.get('windowState')
        screenW = self.parent.winfo_screenwidth() - 16 # allow for window edge
        screenH = self.parent.winfo_screenheight() - 64 # allow for caption and menus
        if priorState == "zoomed":
            self.parent.state("zoomed")
            w = screenW
            h = screenH
        else:
            priorGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)",self.config.get('windowGeometry'))
            if priorGeometry and priorGeometry.lastindex >= 4:
                try:
                    w = int(priorGeometry.group(1))
                    h = int(priorGeometry.group(2))
                    x = int(priorGeometry.group(3))
                    y = int(priorGeometry.group(4))
                    if x + w > screenW:
                        if w < screenW:
                            x = screenW - w
                        else:
                            x = 0
                            w = screenW
                    elif x < 0:
                        x = 0
                        if w > screenW:
                            w = screenW
                    if y + h > screenH:
                        if y < screenH:
                            y = screenH - h
                        else:
                            y = 0
                            h = screenH
                    elif y < 0:
                        y = 0
                        if h > screenH:
                            h = screenH
                    self.parent.geometry("{0}x{1}+{2}+{3}".format(w,h,x,y))
                except:
                    pass
        # set top/btm divider
        topLeftW, topLeftH = self.config.get('tabWinTopLeftSize',(250,300))
        if 10 < topLeftW < w - 60:
            self.tabWinTopLeft.config(width=topLeftW)
        if 10 < topLeftH < h - 60:
            self.tabWinTopLeft.config(height=topLeftH)
        
        self.parent.title(_("arelle - Unnamed"))
        
        self.logFile = None
        
        self.uiThreadQueue = queue.Queue()     # background processes communicate with ui thread
        self.uiThreadChecker(self.statusbar)    # start background queue

        if not self.modelManager.disclosureSystem.select(self.config.setdefault("disclosureSystem", None)):
            self.validateDisclosureSystem.set(False)
            self.modelManager.validateDisclosureSystem = False
        self.setValidateTooltipText()
        
        
    def loadFileMenuHistory(self):
        self.fileMenu.delete(self.fileMenuLength, self.fileMenuLength + 1)
        fileHistory = self.config.setdefault("fileHistory", [])
        self.recentFilesMenu = Menu(self.menubar, tearoff=0)
        for i in range( min( len(fileHistory), 10 ) ):
            self.recentFilesMenu.add_command(
                 label=fileHistory[i], 
                 command=lambda j=i: self.fileOpenFile(self.config["fileHistory"][j]))
        self.fileMenu.add_cascade(label=_("Recent files"), menu=self.recentFilesMenu, underline=0)
        importHistory = self.config.setdefault("importHistory", [])
        self.recentAttachMenu = Menu(self.menubar, tearoff=0)
        for i in range( min( len(importHistory), 10 ) ):
            self.recentAttachMenu.add_command(
                 label=importHistory[i], 
                 command=lambda j=i: self.fileOpenFile(self.config["fileImportHistory"][j],attach=True))
        self.fileMenu.add_cascade(label=_("Recent imports"), menu=self.recentAttachMenu, underline=0)
       
        
    def fileNew(self, *ignore):
        if not self.okayToContinue():
            return
        self.logClear()
        self.dirty = False
        self.filename = None
        self.data = {}
        self.parent.title(_("arelle - Unnamed"));
        self.modelManager.load(None);
        
    def okayToContinue(self):
        if not self.dirty:
            return True
        reply = tkinter.messagebox.askyesnocancel(
                    _("arelle - Unsaved Changes"),
                    _("Save unsaved changes?"), 
                    parent=self.parent)
        if reply is None:
            return False
        if reply:
            return self.fileSave()
        return True
        
    def fileSave(self, *ignore):
        if self.modelManager.modelXbrl:
            if self.modelManager.modelXbrl.modelDocument.type == ModelDocument.Type.TESTCASESINDEX:
                filename = tkinter.filedialog.asksaveasfilename(
                        title=_("arelle - Save Test Results"),
                        initialdir=os.path.dirname(self.modelManager.modelXbrl.modelDocument.uri),
                        filetypes=[(_("CSV file"), "*.csv")],
                        defaultextension=".csv",
                        parent=self.parent)
                if not filename:
                    return False
                try:
                    ViewCsvTests.viewTests(self.modelManager.modelXbrl, filename)
                except (IOError, EnvironmentError) as err:
                    tkinter.messagebox.showwarning(_("arelle - Error"),
                                        _("Failed to save {0}:\n{1}").format(
                                        self.filename, err),
                                        parent=self.parent)
                return True
            elif self.modelManager.modelXbrl.formulaOutputInstance:
                filename = tkinter.filedialog.asksaveasfilename(
                        title=_("arelle - Save Formula Result Instance Document"),
                        initialdir=os.path.dirname(self.modelManager.modelXbrl.modelDocument.uri),
                        filetypes=[(_("XBRL output instance .xml"), "*.xml"), (_("XBRL output instance .xbrl"), "*.xbrl")],
                        defaultextension=".xml",
                        parent=self.parent)
                if not filename:
                    return False
                try:
                    from arelle import XmlUtil
                    with open(filename, "w") as fh:
                        XmlUtil.writexml(fh, self.modelManager.modelXbrl.formulaOutputInstance.modelDocument.xmlDocument, encoding="utf-8")
                    self.addToLog(_("[info] Saved formula output instance to {0}").format(filename) )
                except (IOError, EnvironmentError) as err:
                    tkinter.messagebox.showwarning(_("arelle - Error"),
                                    _("Failed to save {0}:\n{1}").format(
                                    self.filename, err),
                                    parent=self.parent)
                return True
        if self.filename is None:
            filename = tkinter.filedialog.asksaveasfilename(
                    title=_("arelle - Save File"),
                    initialdir=".",
                    filetypes=[(_("Xbrl file"), "*.x*")],
                    defaultextension=".xbrl",
                    parent=self.parent)
            if not filename:
                return False
            self.filename = filename
            if not self.filename.endswith(".xbrl"):
                self.filename += ".xbrl"
        try:
            with open(self.filename, "wb") as fh:
                pickle.dump(self.data, fh, pickle.HIGHEST_PROTOCOL)
            self.dirty = False
            self.uiShowStatus(_("Saved {0} items to {1}").format(
                                len(self.data),
                                self.filename), clearAfter=5000)
            self.parent.title(_("arelle - {0}").format(
                                os.path.basename(self.filename)))
        except (EnvironmentError, pickle.PickleError) as err:
            tkinter.messagebox.showwarning(_("arelle - Error"),
                                _("Failed to save {0}:\n{1}").format(
                                self.filename, err),
                                parent=self.parent)
        return True;
    
    def fileOpen(self, *ignore):
        if not self.okayToContinue():
            return
        filename = tkinter.filedialog.askopenfilename(
                            title=_("arelle - Open file"),
                            initialdir=self.config.setdefault("fileOpenDir","."),
                            filetypes=[] if self.isMac else [(_("XBRL files"), "*.*")],
                            defaultextension=".xbrl",
                            parent=self.parent)
        if self.isMSW and "/Microsoft/Windows/Temporary Internet Files/Content.IE5/" in filename:
            tkinter.messagebox.showerror(_("Loading web-accessed files"),
                _('Please open web-accessed files with the second toolbar button, "Open web file", or the File menu, second entry, "Open web..."'), parent=self.parent)
            return
        if os.sep == "\\":
            filename = filename.replace("/", "\\")
            
        self.fileOpenFile(filename)
    
    def importOpen(self, *ignore):
        if not self.modelManager.modelXbrl or self.modelManager.modelXbrl.modelDocument.type not in (
             ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE, ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Import requires an opened DTS"), parent=self.parent)
            return False
        filename = tkinter.filedialog.askopenfilename(
                            title=_("arelle - Import file into opened DTS"),
                            initialdir=self.config.setdefault("importOpenDir","."),
                            filetypes=[] if self.isMac else [(_("XBRL files"), "*.*")],
                            defaultextension=".xml",
                            parent=self.parent)
        if self.isMSW and "/Microsoft/Windows/Temporary Internet Files/Content.IE5/" in filename:
            tkinter.messagebox.showerror(_("Loading web-accessed files"),
                _('Please open web-accessed files with the second toolbar button, "Open web file", or the File menu, second entry, "Open web..."'), parent=self.parent)
            return
        if os.sep == "\\":
            filename = filename.replace("/", "\\")
            
        self.fileOpenFile(filename, attach=True)
    
        
    def updateFileHistory(self, url, importToDTS):
        key = "importHistory" if importToDTS else "fileHistory"
        fileHistory = self.config.setdefault(key, [])
        while fileHistory.count(url) > 0:
            fileHistory.remove(url)
        if len(fileHistory) > 10:
            fileHistory[10:] = []
        fileHistory.insert(0, url)
        self.config[key] = fileHistory
        self.loadFileMenuHistory()
        self.saveConfig()
        
    def fileOpenFile(self, filename, importToDTS=False):
        if filename:
            filesource = None
            # check for archive files
            filesource = openFileSource(filename,self)
            if filesource.isArchive and not filesource.selection: # or filesource.isRss:
                from arelle import DialogOpenArchive
                filename = DialogOpenArchive.askArchiveFile(self, filesource)
                
        if filename:
            if importToDTS:
                self.config["importOpenDir"] = os.path.dirname(filename)
            else:
                if not filename.startswith("http://"):
                    self.config["fileOpenDir"] = os.path.dirname(filename)
            self.updateFileHistory(filename, importToDTS)
            thread = threading.Thread(target=lambda: self.backgroundLoadXbrl(filesource,importToDTS))
            thread.daemon = True
            thread.start()
            
    def webOpen(self, *ignore):
        if not self.okayToContinue():
            return
        url = DialogURL.askURL(self.parent)
        if url:
            self.updateFileHistory(url, False)
            filesource = openFileSource(url,self)
            if filesource.isArchive and not filesource.selection: # or filesource.isRss:
                from arelle import DialogOpenArchive
                url = DialogOpenArchive.askArchiveFile(self, filesource)
            self.updateFileHistory(url, False)
            thread = threading.Thread(target=lambda: self.backgroundLoadXbrl(filesource,False))
            thread.daemon = True
            thread.start()
            
    def backgroundLoadXbrl(self, filesource, importToDTS):
        startedAt = time.time()
        try:
            if importToDTS:
                action = _("imported")
                modelXbrl = self.modelManager.modelXbrl
                if modelXbrl:
                    ModelDocument.load(modelXbrl, filesource.url)
            else:
                action = _("loaded")
                modelXbrl = self.modelManager.load(filesource, _("views loading"))
        except Exception as err:
            msg = _("Exception loading {0}: {1}, at {2}").format(
                     filesource.url,
                     err,
                     traceback.format_tb(sys.exc_info()[2]))
            # not sure if message box can be shown from background thread
            # tkinter.messagebox.showwarning(_("Exception loading"),msg, parent=self.parent)
            self.addToLog(msg);
            return
        if modelXbrl and modelXbrl.modelDocument:
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("%s in %.2f secs"), 
                                        (action, time.time() - startedAt)))
            self.showStatus(_("{0}, preparing views").format(action))
            self.waitForUiThreadQueue() # force status update
            self.uiThreadQueue.put((self.showLoadedXbrl, [modelXbrl, importToDTS]))
        else:
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("not successfully %s in %.2f secs"), 
                                        (action, time.time() - startedAt)))

    def showLoadedXbrl(self, modelXbrl, attach):
        startedAt = time.time()
        currentAction = "setting title"
        try:
            if attach:
                modelXbrl.closeViews()
            self.parent.title(_("arelle - {0}").format(
                            os.path.basename(modelXbrl.modelDocument.uri)))
            self.setValidateTooltipText()
            if modelXbrl.modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, 
                        ModelDocument.Type.TESTCASE, ModelDocument.Type.REGISTRY, ModelDocument.Type.REGISTRYTESTCASE):
                currentAction = "tree view of tests"
                ViewWinTests.viewTests(modelXbrl, self.tabWinTopRt)
            elif modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
                currentAction = "view of versioning report"
                ViewWinVersReport.viewVersReport(modelXbrl, self.tabWinTopRt)
                from arelle.ViewWinDiffs import ViewWinDiffs
                ViewWinDiffs(modelXbrl, self.tabWinBtm, lang=self.lang)
            elif modelXbrl.modelDocument.type == ModelDocument.Type.RSSFEED:
                currentAction = "view of RSS feed"
                ViewWinRssFeed.viewRssFeed(modelXbrl, self.tabWinTopRt)
            else:
                currentAction = "tree view of tests"
                ViewWinDTS.viewDTS(modelXbrl, self.tabWinTopLeft, altTabWin=self.tabWinTopRt)
                currentAction = "view of concepts"
                ViewWinConcepts.viewConcepts(modelXbrl, self.tabWinBtm, "Concepts", lang=self.lang, altTabWin=self.tabWinTopRt)
                if modelXbrl.hasEuRendering:  # show rendering grid even without any facts
                    ViewWinRenderedGrid.viewRenderedGrid(modelXbrl, self.tabWinTopRt, lang=self.lang)
                if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
                    currentAction = "table view of facts"
                    if not modelXbrl.hasEuRendering: # table view only if not grid rendered view
                        ViewWinFactTable.viewFacts(modelXbrl, self.tabWinTopRt, lang=self.lang)
                    currentAction = "tree/list of facts"
                    ViewWinFactList.viewFacts(modelXbrl, self.tabWinTopRt, lang=self.lang)
                if modelXbrl.hasFormulae:
                    currentAction = "formulae view"
                    ViewWinFormulae.viewFormulae(modelXbrl, self.tabWinTopRt)
                currentAction = "presentation linkbase view"
                ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, XbrlConst.parentChild, lang=self.lang)
                currentAction = "calculation linkbase view"
                ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, XbrlConst.summationItem, lang=self.lang)
                currentAction = "dimensions relationships view"
                ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, "XBRL-dimensions", lang=self.lang)
                if modelXbrl.hasEuRendering:
                    currentAction = "rendering view"
                    ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, "EU-rendering", lang=self.lang)
            currentAction = "property grid"
            ViewWinProperties.viewProperties(modelXbrl, self.tabWinTopLeft)
            currentAction = "log view creation time"
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("views %.2f secs"), 
                                        time.time() - startedAt))
        except Exception as err:
            msg = _("Exception preparing {0}: {1}, at {2}").format(
                     currentAction,
                     err,
                     traceback.format_tb(sys.exc_info()[2]))
            tkinter.messagebox.showwarning(_("Exception preparing view"),msg, parent=self.parent)
            self.addToLog(msg);
        self.showStatus(_("Ready..."), 2000)
        
    def showFormulaOutputInstance(self, priorOutputInstance, currentOutputInstance):
        currentAction = "closing prior formula output instance"
        try:
            if priorOutputInstance: # if has UI must close on UI thread, not background thread
                priorOutputInstance.close()
            currentAction = "showing resulting formula output instance"
            if currentOutputInstance:
                ViewWinXml.viewXml(currentOutputInstance, self.tabWinBtm, "Formula Output Instance", currentOutputInstance.modelDocument.xmlDocument)
        except Exception as err:
            msg = _("Exception {0}: {1}, at {2}").format(
                     currentAction,
                     err,
                     traceback.format_tb(sys.exc_info()[2]))
            tkinter.messagebox.showwarning(_("Exception preparing view"),msg, parent=self.parent)
            self.addToLog(msg);
        self.showStatus(_("Ready..."), 2000)
        
    def fileClose(self):
        if not self.okayToContinue():
            return
        self.modelManager.close()
        self.parent.title(_("arelle - Unnamed"))
        self.setValidateTooltipText()

    def validate(self):
        if self.modelManager.modelXbrl:
            thread = threading.Thread(target=lambda: self.backgroundValidate())
            thread.daemon = True
            thread.start()
            
    def backgroundValidate(self):
        startedAt = time.time()
        modelXbrl = self.modelManager.modelXbrl
        priorOutputInstance = modelXbrl.formulaOutputInstance
        modelXbrl.formulaOutputInstance = None # prevent closing on background thread by validateFormula
        self.modelManager.validate()
        self.addToLog(format_string(self.modelManager.locale, 
                                    _("validated in %.2f secs"), 
                                    time.time() - startedAt))
        if modelXbrl and (priorOutputInstance or modelXbrl.formulaOutputInstance):
            self.uiThreadQueue.put((self.showFormulaOutputInstance, [priorOutputInstance, modelXbrl.formulaOutputInstance]))
            
        self.uiThreadQueue.put((self.logSelect, []))


    def compareDTSes(self):
        countLoadedDTSes = len(self.modelManager.loadedModelXbrls)
        if countLoadedDTSes != 2:
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Two DTSes are required for the Compare DTSes operation, {0} found").format(countLoadedDTSes),
                            parent=self.parent)
            return False
        versReportFile = tkinter.filedialog.asksaveasfilename(
                title=_("arelle - Save Versioning Report File"),
                initialdir=self.config.setdefault("versioningReportDir","."),
                filetypes=[(_("Versioning report file"), "*.xml")],
                defaultextension=".xml",
                parent=self.parent)
        if not versReportFile:
            return False
        self.config["versioningReportDir"] = os.path.dirname(versReportFile)
        self.saveConfig()
        thread = threading.Thread(target=lambda: self.backgroundCompareDTSes(versReportFile))
        thread.daemon = True
        thread.start()
            
    def backgroundCompareDTSes(self, versReportFile):
        startedAt = time.time()
        modelVersReport = self.modelManager.compareDTSes(versReportFile)
        if modelVersReport and modelVersReport.modelDocument:
            self.addToLog(format_string(self.modelManager.locale, 
                                        _("compared in %.2f secs"), 
                                        time.time() - startedAt))
            self.uiThreadQueue.put((self.showComparedDTSes, [modelVersReport]))
            
    def showComparedDTSes(self, modelVersReport):
        # close prior DTS displays
        modelVersReport.modelDocument.fromDTS.closeViews()
        modelVersReport.modelDocument.toDTS.closeViews()
        self.showLoadedXbrl(modelVersReport, True)

    def loadFile(self, filename):
        self.filename = filename
        self.listBox.delete(0, END)
        self.dirty = False
        try:
            with open(self.filename, "rb") as fh:
                self.data = pickle.load(fh)
            for name in sorted(self.data, key=str.lower):
                self.listBox.insert(END, name)
            self.showStatus(_("Loaded {0} items from {1}").format(
                            self.listbox.size(),
                            self.filename), clearAfter=5000)
            self.parent.title(_("arelle - {0}").format(
                            os.path.basename(self.filename)))
                            
        except (EnvironmentError, pickle.PickleError) as err:
            tkinter.messagebox.showwarning(_("arelle - Error"),
                            _("Failed to load {0}\n{1}").format(
                            self.filename,
                            err),
                            parent=self.parent)
                            
    def quit(self, event=None, restartAfterQuit=False):
        if self.okayToContinue():
            global restartMain
            restartMain = restartAfterQuit
            state = self.parent.state()
            if state == "normal":
                self.config["windowGeometry"] = self.parent.geometry()
            if state in ("normal", "zoomed"):
                self.config["windowState"] = state
            self.config["tabWinTopLeftSize"] = (self.tabWinTopLeft.winfo_width(),
                                                self.tabWinTopLeft.winfo_height())
            super().close()
            self.parent.unbind_all(())
            self.parent.destroy()
            if self.logFile:
                self.logFile.close()
                self.logFile = None
                
    def restart(self, event=None):
        self.quit(event, restartAfterQuit=True)
                    
    def setWorkOffline(self, *args):
        self.webCache.workOffline = self.workOffline.get()
        self.config["workOffline"] = self.webCache.workOffline
        self.saveConfig()
            
    def confirmClearWebCache(self):
        if tkinter.messagebox.askyesno(
                    _("arelle - Clear Internet Cache"),
                    _("Are you sure you want to clear the internet cache?"), 
                    parent=self.parent):
            self.webCache.clear()

    def manageWebCache(self):
        if sys.platform.startswith("win"):
            command = 'explorer'
        elif sys.platform in ("darwin", "macos"):
            command = 'open'
        else: # linux/unix
            command = 'xdg-open'
        try:
            subprocess.Popen([command,self.webCache.cacheDir])
        except:
            pass
        
    def setupProxy(self):
        from arelle.DialogUserPassword import askProxy
        proxySettings = askProxy(self.parent, self.config.get("proxySettings"))
        if proxySettings:
            self.webCache.resetProxies(proxySettings)
            self.config["proxySettings"] = proxySettings
            self.saveConfig()
        
    def setValidateDisclosureSystem(self, *args):
        self.modelManager.validateDisclosureSystem = self.validateDisclosureSystem.get()
        self.config["validateDisclosureSystem"] = self.modelManager.validateDisclosureSystem
        self.saveConfig()
        if self.modelManager.validateDisclosureSystem:
            if not self.modelManager.disclosureSystem or not self.modelManager.disclosureSystem.selection:
                self.selectDisclosureSystem()
        self.setValidateTooltipText()
            
    def selectDisclosureSystem(self, *args):
        from arelle import DialogOpenArchive
        self.config["disclosureSystem"] = DialogOpenArchive.selectDisclosureSystem(self, self.modelManager.disclosureSystem)
        self.saveConfig()
        self.setValidateTooltipText()
        
    def formulaParametersDialog(self, *args):
        from arelle import DialogFormulaParameters
        DialogFormulaParameters.getParameters(self)
        self.setValidateTooltipText()
        
    def rssWatchOptionsDialog(self, *args):
        from arelle import DialogRssWatch
        DialogRssWatch.getOptions(self)
        
    # find or open rssWatch view
    def rssWatchControl(self, start=False, stop=False, close=False):
        from arelle.ModelDocument import Type
        from arelle import WatchRss
        if not self.modelManager.rssWatchOptions.feedSourceUri:
            tkinter.messagebox.showwarning(_("RSS Watch Control Error"),
                                _("RSS Feed is not set up, please select options and select feed"),
                                parent=self.parent)
            return False
        rssModelXbrl = None
        for loadedModelXbrl in self.modelManager.loadedModelXbrls:
            if (loadedModelXbrl.modelDocument.type == Type.RSSFEED and
                loadedModelXbrl.modelDocument.uri == self.modelManager.rssWatchOptions.feedSourceUri):
                rssModelXbrl = loadedModelXbrl
                break                
        #not loaded
        if start:
            if not rssModelXbrl:
                rssModelXbrl = self.modelManager.create(Type.RSSFEED, self.modelManager.rssWatchOptions.feedSourceUri)
                self.showLoadedXbrl(rssModelXbrl, False)
            if not hasattr(rssModelXbrl,"watchRss"):
                WatchRss.initializeWatcher(rssModelXbrl)
            rssModelXbrl.watchRss.start()
        elif stop:
            if rssModelXbrl and rssModelXbrl.watchRss:
                rssModelXbrl.watchRss.stop()

    # for ui thread option updating
    def rssWatchUpdateOption(self, latestPubDate=None):
        self.uiThreadQueue.put((self.uiRssWatchUpdateOption, [latestPubDate]))
        
    # ui thread addToLog
    def uiRssWatchUpdateOption(self, latestPubDate): 
        if latestPubDate:
            self.modelManager.rssWatchOptions.latestPubDate = latestPubDate
        self.config["rssWatchOptions"] = self.modelManager.rssWatchOptions
        self.saveConfig()
    
    def languagesDialog(self, *args):
        override = self.lang if self.lang != self.modelManager.defaultLang else ""
        import tkinter.simpledialog
        newValue = tkinter.simpledialog.askstring(_("arelle - Labels language code setting"),
                _("The system default language is: {0} \n\n"
                  "You may override with a different language for labels display. \n\n"
                  "Current language override code: {1} \n"
                  "(Leave empty to use the system default language.)").format(
                self.modelManager.defaultLang, override),
                parent=self.parent)
        if newValue is not None:
            self.config["langOverride"] = newValue
            if newValue:
                self.lang = newValue
            else:
                self.lang = self.modelManager.defaultLang
            if self.modelManager.modelXbrl and self.modelManager.modelXbrl.modelDocument:
                self.showLoadedXbrl(self.modelManager.modelXbrl, True) # reload views
            self.saveConfig()
        
    def setValidateTooltipText(self):
        if self.modelManager.modelXbrl and self.modelManager.modelXbrl.modelDocument:
            valType = self.modelManager.modelXbrl.modelDocument.type
            if valType == ModelDocument.Type.TESTCASESINDEX:
                v = _("Validate testcases")
            elif valType == ModelDocument.Type.TESTCASE:
                v = _("Validate testcase")
            elif valType == ModelDocument.Type.VERSIONINGREPORT:
                v = _("Validate versioning report")
            else:
                if self.modelManager.validateCalcLB:
                    if self.modelManager.validateInferDecimals:
                        c = _("\nCheck calculations (infer decimals)")
                    else:
                        c = _("\nCheck calculations (infer precision)")
                else:
                    c = ""
                if self.modelManager.validateUtr:
                    u = _("\nCheck unit type registry")
                else:
                    u = ""
                if self.modelManager.validateDisclosureSystem:
                    v = _("Validate\nCheck disclosure system rules\n{0}{1}{2}").format(self.modelManager.disclosureSystem.selection,c,u)
                else:
                    v = _("Validate{0}{1}").format(c,u)
        else:
            v = _("Validate")
        self.validateTooltipText.set(v)
            
    def setValidateCalcLB(self, *args):
        self.modelManager.validateCalcLB = self.validateCalcLB.get()
        self.config["validateCalcLB"] = self.modelManager.validateCalcLB
        self.saveConfig()
        self.setValidateTooltipText()
            
    def setValidateInferDecimals(self, *args):
        self.modelManager.validateInferDecimals = self.validateInferDecimals.get()
        self.config["validateInferDecimals"] = self.modelManager.validateInferDecimals
        self.saveConfig()
        self.setValidateTooltipText()
            
    def setValidateUtr(self, *args):
        self.modelManager.validateUtr = self.validateUtr.get()
        self.config["validateUtr"] = self.modelManager.validateUtr
        self.saveConfig()
        self.setValidateTooltipText()
        
    def find(self, *args):
        from arelle.DialogFind import find
        find(self)
            
    def helpAbout(self, event=None):
        from arelle import DialogAbout, Version
        DialogAbout.about(self.parent,
                          _("About arelle"),
                          os.path.join(self.imagesDir, "arelle32.gif"),
                          _("arelle\u00ae {0}\n"
                              "An open source XBRL platform\n"
                              "\u00a9 2010-2011 Mark V Systems Limited\n"
                              "All rights reserved\nhttp://www.arelle.org\nsupport@arelle.org\n\n"
                              "Licensed under the Apache License, Version 2.0 (the \"License\"); "
                              "you may not use this file except in compliance with the License.  "
                              "You may obtain a copy of the License at\n\n"
                              "http://www.apache.org/licenses/LICENSE-2.0\n\n"
                              "Unless required by applicable law or agreed to in writing, software "
                              "distributed under the License is distributed on an \"AS IS\" BASIS, "
                              "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  "
                              "See the License for the specific language governing permissions and "
                              "limitations under the License."
                              "\n\nIncludes:"
                              "\n   Python\u00ae \u00a9 2001-2010 Python Software Foundation"
                              "\n   PyParsing \u00a9 2003-2010 Paul T. McGuire"
                              "\n   lxml \u00a9 2004 Infrae, ElementTree \u00a9 1999-2004 by Fredrik Lundh"
                              "\n   xlrd \u00a9 2005-2009 Stephen J. Machin, Lingfo Pty Ltd, \u00a9 2001 D. Giffin, \u00a9 2000 A. Khan"
                              "\n   xlwt \u00a9 2007 Stephen J. Machin, Lingfo Pty Ltd, \u00a9 2005 R. V. Kiseliov"
                              )
                            .format(Version.version))

    # worker threads addToLog        
    def addToLog(self, message):
        self.uiThreadQueue.put((self.uiAddToLog, [message]))
        
    # ui thread addToLog
    def uiAddToLog(self, message):
        try:
            self.logView.append(message)
        except:
            pass
        
    def logClear(self, *ignore):
        self.logView.clear()
        
    def logSelect(self, *ignore):
        self.logView.select()
        
    def logSaveToFile(self, *ignore):
        filename = tkinter.filedialog.asksaveasfilename(
                title=_("arelle - Save Messages Log"),
                initialdir=".",
                filetypes=[(_("Txt file"), "*.txt")],
                defaultextension=".txt",
                parent=self.parent)
        if not filename:
            return False
        try:
            self.logView.saveToFile(filename)
        except (IOError, EnvironmentError) as err:
            tkinter.messagebox.showwarning(_("arelle - Error"),
                                _("Failed to save {0}:\n{1}").format(
                                filename, err),
                                parent=self.parent)
        return True;
    

    # worker threads viewModelObject                 
    def viewModelObject(self, modelXbrl, objectId):
        self.uiThreadQueue.put((self.uiViewModelObject, [modelXbrl, objectId]))
        
    # ui thread viewModelObject
    def uiViewModelObject(self, modelXbrl, objectId):
        modelXbrl.viewModelObject(objectId)

    # worker threads viewModelObject                 
    def reloadViews(self, modelXbrl):
        self.uiThreadQueue.put((self.uiReloadViews, [modelXbrl]))
        
    # ui thread viewModelObject
    def uiReloadViews(self, modelXbrl):
        for view in modelXbrl.views:
            view.view()

    # worker threads showStatus                 
    def showStatus(self, message, clearAfter=None):
        self.uiThreadQueue.put((self.uiShowStatus, [message, clearAfter]))
        
    # ui thread showStatus
    def uiClearStatusTimerEvent(self):
        if self.statusbarTimerId:   # if timer still wanted, clear status
            self.statusbar["text"] = ""
        self.statusbarTimerId  = None
        
    def uiShowStatus(self, message, clearAfter=None):
        if self.statusbarTimerId: # ignore timer
            self.statusbarTimerId = None
        self.statusbar["text"] = message
        if clearAfter is not None and clearAfter > 0:
            self.statusbarTimerId  = self.statusbar.after(clearAfter, self.uiClearStatusTimerEvent)
            
    # web authentication password request
    def internet_user_password(self, host, realm):
        from arelle.DialogUserPassword import askUserPassword
        untilDone = threading.Event()
        result = []
        self.uiThreadQueue.put((askUserPassword, [self.parent, host, realm, untilDone, result]))
        untilDone.wait()
        return result[0]
    
    def waitForUiThreadQueue(self):
        for i in range(40): # max 2 secs
            if self.uiThreadQueue.empty():
                break
            time.sleep(0.05)

    def uiThreadChecker(self, widget, delayMsecs=100):        # 10x per second
        # process callback on main (UI) thread
        while not self.uiThreadQueue.empty():
            try:
                (callback, args) = self.uiThreadQueue.get(block=False)
            except queue.Empty:
                pass
            else:
                callback(*args)
        widget.after(delayMsecs, lambda: self.uiThreadChecker(widget))

def main():
    # this is the entry called by arelleGUI.pyw for windows
    gettext.install("arelle")
    global restartMain
    while restartMain:
        restartMain = False
        application = Tk()
        cntlrWinMain = CntlrWinMain(application)
        application.protocol("WM_DELETE_WINDOW", cntlrWinMain.quit)
        application.mainloop()

if __name__ == "__main__":
    # this is the entry called by MacOS open and MacOS shell scripts
    # check if ARELLE_ARGS are used to emulate command line operation
    if os.getenv("ARELLE_ARGS"):
        # command line mode
        from arelle import CntlrCmdLine
        CntlrCmdLine.main()
    else:
        # GUI mode
        main()