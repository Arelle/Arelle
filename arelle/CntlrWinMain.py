'''
This module is Arelle's controller in windowing interactive UI mode

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from arelle import PythonUtil # define 2.x or 3.x string types
import os, sys, subprocess, pickle, time, locale, re, fnmatch, platform

if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    # need the .dll directory in path to be able to access Tk and Tcl DLLs efore importinng Tk, etc.
    os.environ['PATH'] = os.path.dirname(sys.executable) + ";" + os.environ['PATH']

from tkinter import (Tk, Tcl, TclError, Toplevel, Menu, PhotoImage, StringVar, BooleanVar, N, S, E, W, EW,
                     HORIZONTAL, VERTICAL, END, font as tkFont)
try:
    from tkinter.ttk import Frame, Button, Label, Combobox, Separator, PanedWindow, Notebook
except ImportError:  # 3.0 versions of tkinter
    from ttk import Frame, Button, Label, Combobox, Separator, PanedWindow, Notebook
try:
    import syslog
except ImportError:
    syslog = None
import tkinter.tix
import tkinter.filedialog
import tkinter.messagebox, traceback
import tkinter.simpledialog
from arelle.FileSource import saveFile as writeToFile
from arelle.Locale import format_string
from arelle.CntlrWinTooltip import ToolTip
from arelle import XbrlConst
from arelle.PluginManager import pluginClassMethods
from arelle.UrlUtil import isHttpUrl
from arelle.Version import copyrightLabel
import logging

import threading, queue

from arelle import Cntlr
from arelle import (DialogURL, DialogLanguage,
                    DialogPluginManager, DialogPackageManager,
                    ModelDocument,
                    ModelManager,
                    PackageManager,
                    RenderingEvaluator,
                    TableStructure,
                    ViewWinDTS,
                    ViewWinProperties, ViewWinConcepts, ViewWinRelationshipSet, ViewWinFormulae,
                    ViewWinFactList, ViewFileFactList, ViewWinFactTable, ViewWinRenderedGrid, ViewWinXml,
                    ViewWinRoleTypes, ViewFileRoleTypes, ViewFileConcepts,
                    ViewWinTests, ViewWinTree, ViewWinVersReport, ViewWinRssFeed,
                    ViewFileTests,
                    ViewFileRenderedGrid,
                    ViewFileRelationshipSet,
                    Updater
                   )
from arelle.ModelFormulaObject import FormulaOptions
from arelle.FileSource import openFileSource

restartMain = True

class CntlrWinMain (Cntlr.Cntlr):

    def __init__(self, parent):
        super(CntlrWinMain, self).__init__(hasGui=True)
        self.parent = parent
        self.filename = None
        self.dirty = False
        overrideLang = self.config.get("labelLangOverride")
        localeSetupMessage = self.modelManager.setLocale() # set locale before GUI for menu strings, pass any msg to logger after log pane starts up
        self.labelLang = overrideLang if overrideLang else self.modelManager.defaultLang
        self.data = {}

        # Background processes communicate with UI thread through this queue
        # Prepare early so messages encountered during initialization can be queued for logging
        self.uiThreadQueue = queue.Queue()

        if self.isMac: # mac Python fonts bigger than other apps (terminal, text edit, Word), and to windows Arelle
            _defaultFont = tkFont.nametofont("TkDefaultFont") # label, status bar, treegrid
            _defaultFont.configure(size=11)
            _textFont = tkFont.nametofont("TkTextFont") # entry widget and combobox entry field
            _textFont.configure(size=11)
            #parent.option_add("*Font", _defaultFont) # would be needed if not using defaulted font
            toolbarButtonPadding = 1
        else:
            toolbarButtonPadding = 4

        tkinter.CallWrapper = TkinterCallWrapper


        imgpath = self.imagesDir + os.sep

        if self.isMSW:
            icon = imgpath + "arelle.ico"
            parent.iconbitmap(icon, default=icon)
            #image = PhotoImage(file=path + "arelle32.gif")
            #label = Label(None, image=image)
            #parent.iconwindow(label)
        else:
            self.iconImage = PhotoImage(file=imgpath + "arelle-mac-icon-4.gif") # must keep reference during life of window
            parent.tk.call('wm', 'iconphoto', parent._w, self.iconImage)
            #parent.iconbitmap("@" + imgpath + "arelle.xbm")
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
                (_("Import File..."), self.importFileOpen, None, None),
                (_("Import Web..."), self.importWebOpen, None, None),
                (_("Reopen"), self.fileReopen, None, None),
                ("PLUG-IN", "CntlrWinMain.Menu.File.Open", None, None),
                (_("Save"), self.fileSaveExistingFile, "Ctrl+S", "<Control-s>"),
                (_("Save As..."), self.fileSave, None, None),
                (_("Save DTS Package"), self.saveDTSpackage, None, None),
                ("PLUG-IN", "CntlrWinMain.Menu.File.Save", None, None),
                (_("Close"), self.fileClose, "Ctrl+W", "<Control-w>"),
                (None, None, None, None),
                (_("Quit"), self.quit, "Ctrl+Q", "<Control-q>"),
                #(_("Restart"), self.restart, None, None),
                (None, None, None, None),
                ("",None,None,None) # position for file history
                ):
            if label is None:
                self.fileMenu.add_separator()
            elif label == "PLUG-IN":
                for pluginMenuExtender in pluginClassMethods(command):
                    pluginMenuExtender(self, self.fileMenu)
                    self.fileMenuLength += 1
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
        self.modelManager.validateInferDecimals = self.config.setdefault("validateInferDecimals",True)
        self.validateInferDecimals = BooleanVar(value=self.modelManager.validateInferDecimals)
        self.validateInferDecimals.trace("w", self.setValidateInferDecimals)
        validateMenu.add_checkbutton(label=_("Infer Decimals in calculations"), underline=0, variable=self.validateInferDecimals, onvalue=True, offvalue=False)
        self.modelManager.validateDedupCalcs = self.config.setdefault("validateDedupCalcs",False)
        self.validateDedupCalcs = BooleanVar(value=self.modelManager.validateDedupCalcs)
        self.validateDedupCalcs.trace("w", self.setValidateDedupCalcs)
        validateMenu.add_checkbutton(label=_("De-duplicate calculations"), underline=0, variable=self.validateDedupCalcs, onvalue=True, offvalue=False)
        self.modelManager.validateUtr = self.config.setdefault("validateUtr",True)
        self.validateUtr = BooleanVar(value=self.modelManager.validateUtr)
        self.validateUtr.trace("w", self.setValidateUtr)
        validateMenu.add_checkbutton(label=_("Unit Type Registry validation"), underline=0, variable=self.validateUtr, onvalue=True, offvalue=False)
        for pluginMenuExtender in pluginClassMethods("CntlrWinMain.Menu.Validation"):
            pluginMenuExtender(self, validateMenu)

        formulaMenu = Menu(self.menubar, tearoff=0)
        formulaMenu.add_command(label=_("Parameters..."), underline=0, command=self.formulaParametersDialog)

        toolsMenu.add_cascade(label=_("Formula"), menu=formulaMenu, underline=0)
        self.modelManager.formulaOptions = FormulaOptions(self.config.get("formulaParameters"))

        toolsMenu.add_command(label=_("Compare DTSes..."), underline=0, command=self.compareDTSes)
        cacheMenu = Menu(self.menubar, tearoff=0)

        rssWatchMenu = Menu(self.menubar, tearoff=0)
        rssWatchMenu.add_command(label=_("Options..."), underline=0, command=self.rssWatchOptionsDialog)
        rssWatchMenu.add_command(label=_("Start"), underline=0, command=lambda: self.rssWatchControl(start=True))
        rssWatchMenu.add_command(label=_("Stop"), underline=0, command=lambda: self.rssWatchControl(stop=True))

        toolsMenu.add_cascade(label=_("RSS Watch"), menu=rssWatchMenu, underline=0)
        self.modelManager.rssWatchOptions = self.config.setdefault("rssWatchOptions", {})

        toolsMenu.add_cascade(label=_("Internet"), menu=cacheMenu, underline=0)
        self.webCache.workOffline  = self.config.setdefault("workOffline",False)
        self.workOffline = BooleanVar(value=self.webCache.workOffline)
        self.workOffline.trace("w", self.setWorkOffline)
        cacheMenu.add_checkbutton(label=_("Work offline"), underline=0, variable=self.workOffline, onvalue=True, offvalue=False)
        self.webCache.noCertificateCheck = self.config.setdefault("noCertificateCheck",False) # resets proxy handler stack if true
        self.noCertificateCheck = BooleanVar(value=self.webCache.noCertificateCheck)
        self.noCertificateCheck.trace("w", self.setNoCertificateCheck)
        cacheMenu.add_checkbutton(label=_("No certificate check"), underline=0, variable=self.noCertificateCheck, onvalue=True, offvalue=False)
        '''
        self.webCache.recheck  = self.config.setdefault("webRecheck",False)
        self.webRecheck = BooleanVar(value=self.webCache.webRecheck)
        self.webRecheck.trace("w", self.setWebRecheck)
        cacheMenu.add_checkbutton(label=_("Recheck file dates weekly"), underline=0, variable=self.workOffline, onvalue=True, offvalue=False)
        self.webCache.notify  = self.config.setdefault("",False)
        self.downloadNotify = BooleanVar(value=self.webCache.retrievalNotify)
        self.downloadNotify.trace("w", self.setRetrievalNotify)
        cacheMenu.add_checkbutton(label=_("Notify file downloads"), underline=0, variable=self.workOffline, onvalue=True, offvalue=False)
        '''

        internetCacheRecheckMenu = Menu(cacheMenu, tearoff=0)
        self.webCache.recheck = self.config.setdefault("internetRecheck", "weekly")
        self.internetRecheckVar = StringVar(value=self.webCache.recheck)
        self._internetRecheckLabel = _("Internet recheck Interval")
        _recheck_initial = 'disable' if self.webCache.workOffline else 'normal'
        self.internetRecheckVar.trace("w", self.setInternetRecheck)

        _internetRecheckEntries = ((_("daily"), "daily"), (_("weekly"), "weekly"), (_("monthly"), "monthly"), (_("never"), "never"))

        for (_opt_label, _opt_val) in _internetRecheckEntries:
            internetCacheRecheckMenu.add_checkbutton(
                    label=_opt_label,
                    variable=self.internetRecheckVar,
                    underline=0,
                    onvalue=_opt_val
             )

        cacheMenu.add_command(label=_("Clear cache"), underline=0, command=self.confirmClearWebCache)
        cacheMenu.add_command(label=_("Manage cache"), underline=0, command=self.manageWebCache)
        cacheMenu.add_cascade(label=self._internetRecheckLabel, menu=internetCacheRecheckMenu, underline=0, state=_recheck_initial)
        cacheMenu.add_command(label=_("Proxy Server"), underline=0, command=self.setupProxy)
        cacheMenu.add_command(label=_("HTTP User Agent"), underline=0, command=self.setupUserAgent)
        self.webCache.httpUserAgent = self.config.get("httpUserAgent")
        self._cacheMenu = cacheMenu

        logmsgMenu = Menu(self.menubar, tearoff=0)
        toolsMenu.add_cascade(label=_("Messages log"), menu=logmsgMenu, underline=0)
        logmsgMenu.add_command(label=_("Clear"), underline=0, command=self.logClear)
        logmsgMenu.add_command(label=_("Save to file"), underline=0, command=self.logSaveToFile)
        self.modelManager.collectProfileStats = self.config.setdefault("collectProfileStats",False)
        self.collectProfileStats = BooleanVar(value=self.modelManager.collectProfileStats)
        self.collectProfileStats.trace("w", self.setCollectProfileStats)
        logmsgMenu.add_checkbutton(label=_("Collect profile stats"), underline=0, variable=self.collectProfileStats, onvalue=True, offvalue=False)
        logmsgMenu.add_command(label=_("Log profile stats"), underline=0, command=self.showProfileStats)
        logmsgMenu.add_command(label=_("Clear profile stats"), underline=0, command=self.clearProfileStats)
        self.showDebugMessages = BooleanVar(value=self.config.setdefault("showDebugMessages",False))
        self.showDebugMessages.trace("w", self.setShowDebugMessages)
        logmsgMenu.add_checkbutton(label=_("Show debug messages"), underline=0, variable=self.showDebugMessages, onvalue=True, offvalue=False)

        toolsMenu.add_command(label=_("Language..."), underline=0, command=lambda: DialogLanguage.askLanguage(self))

        for pluginMenuExtender in pluginClassMethods("CntlrWinMain.Menu.Tools"):
            pluginMenuExtender(self, toolsMenu)
        self.menubar.add_cascade(label=_("Tools"), menu=toolsMenu, underline=0)

        # view menu only if any plug-in additions provided
        if any (pluginClassMethods("CntlrWinMain.Menu.View")):
            viewMenu = Menu(self.menubar, tearoff=0)
            for pluginMenuExtender in pluginClassMethods("CntlrWinMain.Menu.View"):
                pluginMenuExtender(self, viewMenu)
            self.menubar.add_cascade(label=_("View"), menu=viewMenu, underline=0)

        helpMenu = Menu(self.menubar, tearoff=0)
        for label, command, shortcut_text, shortcut in (
                (_("Check for updates"), lambda: Updater.checkForUpdates(self), None, None),
                (_("Manage plug-ins"), lambda: DialogPluginManager.dialogPluginManager(self), None, None),
                (_("Manage packages"), lambda: DialogPackageManager.dialogPackageManager(self), None, None),
                ("PLUG-IN", "CntlrWinMain.Menu.Help.Upper", None, None),
                (None, None, None, None),
                (_("About..."), self.helpAbout, None, None),
                ("PLUG-IN", "CntlrWinMain.Menu.Help.Lower", None, None),
                ):
            if label is None:
                helpMenu.add_separator()
            elif label == "PLUG-IN":
                for pluginMenuExtender in pluginClassMethods(command):
                    pluginMenuExtender(self, helpMenu)
            else:
                helpMenu.add_command(label=label, underline=0, command=command, accelerator=shortcut_text)
                self.parent.bind(shortcut, command)
        for pluginMenuExtender in pluginClassMethods("CntlrWinMain.Menu.Help"):
            pluginMenuExtender(self, toolsMenu)
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
                ("toolbarReopen.gif", self.fileReopen, _("Reopen"), _("Reopen last opened XBRL file or testcase(s)")),
                ("toolbarSaveFile.gif", self.fileSaveExistingFile, _("Save file"), _("Saves currently selected local XBRL file")),
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
                    tbControl = Button(toolbar, image=image, command=command, style="Toolbutton", padding=toolbarButtonPadding)
                    tbControl.grid(row=0, column=menubarColumn)
                except TclError as err:
                    print(err)
            if isinstance(toolTip,StringVar):
                ToolTip(tbControl, textvariable=toolTip, wraplength=240)
            else:
                ToolTip(tbControl, text=toolTip)
            menubarColumn += 1
        for toolbarExtender in pluginClassMethods("CntlrWinMain.Toolbar"):
            toolbarExtender(self, toolbar)
        toolbar.grid(row=0, column=0, sticky=(N, W))

        paneWinTopBtm = PanedWindow(windowFrame, orient=VERTICAL)
        paneWinTopBtm.grid(row=1, column=0, sticky=(N, S, E, W))
        paneWinLeftRt = tkinter.PanedWindow(paneWinTopBtm, orient=HORIZONTAL)
        paneWinLeftRt.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinLeftRt.bind("<<NotebookTabChanged>>", self.onTabChanged)
        paneWinTopBtm.add(paneWinLeftRt)
        self.tabWinTopLeft = Notebook(paneWinLeftRt, width=250, height=300)
        self.tabWinTopLeft.grid(row=0, column=0, sticky=(N, S, E, W))
        paneWinLeftRt.add(self.tabWinTopLeft)
        self.tabWinTopRt = Notebook(paneWinLeftRt)
        self.tabWinTopRt.grid(row=0, column=0, sticky=(N, S, E, W))
        self.tabWinTopRt.bind("<<NotebookTabChanged>>", self.onTabChanged)
        paneWinLeftRt.add(self.tabWinTopRt)
        self.tabWinBtm = Notebook(paneWinTopBtm)
        self.tabWinBtm.grid(row=0, column=0, sticky=(N, S, E, W))
        self.tabWinBtm.bind("<<NotebookTabChanged>>", self.onTabChanged)
        paneWinTopBtm.add(self.tabWinBtm)

        from arelle import ViewWinList
        self.logView = ViewWinList.ViewList(None, self.tabWinBtm, _("messages"), True)
        self.startLogging(logHandler=WinMainLogHandler(self)) # start logger
        self.postLoggingInit(localeSetupMessage) # Cntlr options after logging is started, logger pane now available for any locale startup messages
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

        self.uiThreadChecker(self.statusbar)    # start background queue

        self.modelManager.loadCustomTransforms() # load if custom transforms not loaded
        if not self.modelManager.disclosureSystem.select(self.config.setdefault("disclosureSystem", None)):
            self.validateDisclosureSystem.set(False)
            self.modelManager.validateDisclosureSystem = False

        # load argv overrides for modelManager options
        lastArg = None
        for arg in sys.argv:
            if not arg: continue
            if lastArg == "--skipLoading": # skip loading matching files (list of unix patterns)
                self.modelManager.skipLoading = re.compile('|'.join(fnmatch.translate(f) for f in arg.split('|')))
            elif arg == "--skipDTS": # skip DTS loading, discovery, etc
                self.modelManager.skipDTS = True
            lastArg = arg
        self.setValidateTooltipText()


    def onTabChanged(self, event, *args):
        try:
            widgetIndex = event.widget.index("current")
            tabId = event.widget.tabs()[widgetIndex]
            for widget in event.widget.winfo_children():
                if str(widget) == tabId:
                    self.currentView = widget.view
                    break
        except (AttributeError, TypeError, TclError):
            pass

    def loadFileMenuHistory(self):
        self.fileMenu.delete(self.fileMenuLength, self.fileMenuLength + 2)
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
                 command=lambda j=i: self.fileOpenFile(self.config["importHistory"][j],importToDTS=True))
        self.fileMenu.add_cascade(label=_("Recent imports"), menu=self.recentAttachMenu, underline=0)
        self.packagesMenu = Menu(self.menubar, tearoff=0)
        hasPackages = False
        for i, packageInfo in enumerate(sorted(PackageManager.packagesConfig.get("packages", []),
                                               key=lambda packageInfo: (packageInfo.get("name",""),packageInfo.get("version",""))),
                                        start=1):
            name = packageInfo.get("name", "package{}".format(i))
            version = packageInfo.get("version")
            if version:
                name = "{} ({})".format(name, version)
            URL = packageInfo.get("URL")
            if name and URL and packageInfo.get("status") == "enabled":
                self.packagesMenu.add_command(
                     label=name,
                     command=lambda url=URL: self.fileOpenFile(url))
                hasPackages = True
        if hasPackages:
            self.fileMenu.add_cascade(label=_("Packages"), menu=self.packagesMenu, underline=0)

    def onPackageEnablementChanged(self):
        self.loadFileMenuHistory()

    def fileNew(self, *ignore):
        if not self.okayToContinue():
            return
        self.logClear()
        self.dirty = False
        self.filename = None
        self.data = {}
        self.parent.title(_("arelle - Unnamed"));
        self.modelManager.load(None);

    def getViewAndModelXbrl(self):
        view = getattr(self, "currentView", None)
        if view:
            modelXbrl = None
            try:
                modelXbrl = view.modelXbrl
                return (view, modelXbrl)
            except AttributeError:
                return (view, None)
        return (None, None)

    def okayToContinue(self):
        view, modelXbrl = self.getViewAndModelXbrl()
        documentIsModified = False
        if view is not None:
            try:
                # What follows only exists in ViewWinRenderedGrid
                view.updateInstanceFromFactPrototypes()
            except AttributeError:
                pass
        if modelXbrl is not None:
            documentIsModified = modelXbrl.isModified()
        if not self.dirty and (not documentIsModified):
            return True
        reply = tkinter.messagebox.askokcancel(
                    _("arelle - Unsaved Changes"),
                    _("Are you sure to close the current instance without saving?\n (OK will discard changes.)"),
                    parent=self.parent)
        if reply is None:
            return False
        else:
            return reply

    def fileSave(self, event=None, view=None, fileType=None, filenameFromInstance=False, *ignore):
        if view is None:
            view = getattr(self, "currentView", None)
        if view is not None:
            filename = None
            modelXbrl = None
            try:
                modelXbrl = view.modelXbrl
            except AttributeError:
                pass
            if filenameFromInstance:
                try:
                    modelXbrl = view.modelXbrl
                    filename = modelXbrl.modelDocument.filepath
                    if filename.endswith('.xsd'): # DTS entry point, no instance saved yet!
                        filename = None
                except AttributeError:
                    pass
            if isinstance(view, ViewWinRenderedGrid.ViewRenderedGrid):
                initialdir = os.path.dirname(modelXbrl.modelDocument.uri)
                if fileType in ("html", "xml", None):
                    if fileType == "html" and filename is None:
                        filename = self.uiFileDialog("save",
                                title=_("arelle - Save HTML-rendered Table"),
                                initialdir=initialdir,
                                filetypes=[(_("HTML file .html"), "*.html"), (_("HTML file .htm"), "*.htm")],
                                defaultextension=".html")
                    elif fileType == "xml" and filename is None:
                        filename = self.uiFileDialog("save",
                                title=_("arelle - Save Table Layout Model"),
                                initialdir=initialdir,
                                filetypes=[(_("Layout model file .xml"), "*.xml")],
                                defaultextension=".xml")
                    else: # ask file type
                        if filename is None:
                            filename = self.uiFileDialog("save",
                                    title=_("arelle - Save XBRL Instance or HTML-rendered Table"),
                                    initialdir=initialdir,
                                    filetypes=[(_("XBRL instance .xbrl"), "*.xbrl"), (_("XBRL instance .xml"), "*.xml"), (_("HTML table .html"), "*.html"), (_("HTML table .htm"), "*.htm")],
                                    defaultextension=".html")
                        if filename and (filename.endswith(".xbrl") or filename.endswith(".xml")):
                            view.saveInstance(filename)
                            return True
                    if not filename:
                        return False
                    try:
                        ViewFileRenderedGrid.viewRenderedGrid(modelXbrl, filename, lang=self.labelLang, sourceView=view)
                    except (IOError, EnvironmentError) as err:
                        tkinter.messagebox.showwarning(_("arelle - Error"),
                                        _("Failed to save {0}:\n{1}").format(
                                        filename, err),
                                        parent=self.parent)
                    return True
                elif fileType == "xbrl":
                    return self.uiFileDialog("save",
                            title=_("arelle - Save Instance"),
                            initialdir=initialdir,
                            filetypes=[(_("XBRL instance .xbrl"), "*.xbrl"), (_("XBRL instance .xml"), "*.xml")],
                            defaultextension=".xbrl")
            elif isinstance(view, ViewWinTests.ViewTests) and modelXbrl.modelDocument.type in (ModelDocument.Type.TESTCASESINDEX, ModelDocument.Type.TESTCASE):
                filename = self.uiFileDialog("save",
                        title=_("arelle - Save Test Results"),
                        initialdir=os.path.dirname(self.modelManager.modelXbrl.modelDocument.uri),
                        filetypes=[(_("XLSX file"), "*.xlsx"),(_("CSV file"), "*.csv"),(_("HTML file"), "*.html"),(_("XML file"), "*.xml"),(_("JSON file"), "*.json")],
                        defaultextension=".xlsx")
                if not filename:
                    return False
                try:
                    ViewFileTests.viewTests(self.modelManager.modelXbrl, filename)
                except (IOError, EnvironmentError) as err:
                    tkinter.messagebox.showwarning(_("arelle - Error"),
                                        _("Failed to save {0}:\n{1}").format(
                                        filename, err),
                                        parent=self.parent)
                return True
            elif isinstance(view, ViewWinTree.ViewTree):
                filename = self.uiFileDialog("save",
                        title=_("arelle - Save {0}").format(view.tabTitle),
                        initialdir=os.path.dirname(self.modelManager.modelXbrl.modelDocument.uri),
                        filetypes=[(_("XLSX file"), "*.xlsx"),(_("CSV file"), "*.csv"),(_("HTML file"), "*.html"),(_("XML file"), "*.xml"),(_("JSON file"), "*.json")],
                        defaultextension=".xlsx")
                if not filename:
                    return False
                try:
                    if isinstance(view, ViewWinRoleTypes.ViewRoleTypes):
                        ViewFileRoleTypes.viewRoleTypes(modelXbrl, filename, view.tabTitle, view.isArcrole, lang=view.lang)
                    elif isinstance(view, ViewWinConcepts.ViewConcepts):
                        ViewFileConcepts.viewConcepts(modelXbrl, filename, labelrole=view.labelrole, lang=view.lang)
                    elif isinstance(view, ViewWinFactList.ViewFactList):
                        ViewFileFactList.viewFacts(modelXbrl, filename, labelrole=view.labelrole, lang=view.lang)
                    else:
                        ViewFileRelationshipSet.viewRelationshipSet(modelXbrl, filename, view.tabTitle, view.arcrole, labelrole=view.labelrole, lang=view.lang)
                except (IOError, EnvironmentError) as err:
                    tkinter.messagebox.showwarning(_("arelle - Error"),
                                        _("Failed to save {0}:\n{1}").format(
                                        filename, err),
                                        parent=self.parent)
                return True

            elif isinstance(view, ViewWinXml.ViewXml) and self.modelManager.modelXbrl.formulaOutputInstance:
                filename = self.uiFileDialog("save",
                        title=_("arelle - Save Formula Result Instance Document"),
                        initialdir=os.path.dirname(self.modelManager.modelXbrl.modelDocument.uri),
                        filetypes=[(_("XBRL output instance .xml"), "*.xml"), (_("XBRL output instance .xbrl"), "*.xbrl")],
                        defaultextension=".xml")
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
        tkinter.messagebox.showwarning(_("arelle - Save what?"),
                                       _("Nothing has been selected that can be saved.  \nPlease select a view pane that can be saved."),
                                       parent=self.parent)
        '''
        if self.filename is None:
            filename = self.uiFileDialog("save",
                    title=_("arelle - Save File"),
                    initialdir=".",
                    filetypes=[(_("Xbrl file"), "*.x*")],
                    defaultextension=".xbrl")
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
        '''

    def fileSaveExistingFile(self, event=None, view=None, fileType=None, *ignore):
        return self.fileSave(view=view, fileType=fileType, filenameFromInstance=True)

    def saveDTSpackage(self):
        self.modelManager.saveDTSpackage(allDTSes=True)

    def fileOpen(self, *ignore):
        if not self.okayToContinue():
            return
        filename = self.uiFileDialog("open",
                            title=_("arelle - Open file"),
                            initialdir=self.config.setdefault("fileOpenDir","."),
                            filetypes=[(_("XBRL files"), "*.*")],
                            defaultextension=".xbrl")
        if self.isMSW and "/Microsoft/Windows/Temporary Internet Files/Content.IE5/" in filename:
            tkinter.messagebox.showerror(_("Loading web-accessed files"),
                _('Please open web-accessed files with the second toolbar button, "Open web file", or the File menu, second entry, "Open web..."'), parent=self.parent)
            return
        if os.sep == "\\":
            filename = filename.replace("/", "\\")

        self.fileOpenFile(filename)

    def importFileOpen(self, *ignore):
        if not self.modelManager.modelXbrl or self.modelManager.modelXbrl.modelDocument.type not in (
             ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE, ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Import requires an opened DTS"), parent=self.parent)
            return False
        filename = self.uiFileDialog("open",
                            title=_("arelle - Import file into opened DTS"),
                            initialdir=self.config.setdefault("importOpenDir","."),
                            filetypes=[(_("XBRL files"), "*.*")],
                            defaultextension=".xml")
        if self.isMSW and "/Microsoft/Windows/Temporary Internet Files/Content.IE5/" in filename:
            tkinter.messagebox.showerror(_("Loading web-accessed files"),
                _('Please import web-accessed files with the File menu, fourth entry, "Import web..."'), parent=self.parent)
            return
        if os.sep == "\\":
            filename = filename.replace("/", "\\")

        self.fileOpenFile(filename, importToDTS=True)


    def updateFileHistory(self, url, importToDTS):
        if isinstance(url, list): # may be multi-doc ixds
            if len(url) != 1:
                return
            url = url[0]
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

    def fileOpenFile(self, filename, importToDTS=False, selectTopView=False):
        if filename:
            for xbrlLoadedMethod in pluginClassMethods("CntlrWinMain.Xbrl.Open"):
                filename = xbrlLoadedMethod(self, filename) # runs in GUI thread, allows mapping filename, mult return filename
            filesource = None
            # check for archive files
            filesource = openFileSource(filename, self,
                                        checkIfXmlIsEis=self.modelManager.disclosureSystem and
                                        self.modelManager.disclosureSystem.validationType == "EFM")
            if filesource.isArchive:
                if not filesource.selection: # or filesource.isRss:
                    from arelle import DialogOpenArchive
                    filename = DialogOpenArchive.askArchiveFile(self, filesource)
                    if filename and filesource.basefile and not isHttpUrl(filesource.basefile):
                        self.config["fileOpenDir"] = os.path.dirname(filesource.baseurl)
                filesource.loadTaxonomyPackageMappings() # if a package, load mappings if not loaded yet
        if filename:
            if not isinstance(filename, (dict, list)): # json objects
                if importToDTS:
                    if not isHttpUrl(filename):
                        self.config["importOpenDir"] = os.path.dirname(filename)
                else:
                    if not isHttpUrl(filename):
                        self.config["fileOpenDir"] = os.path.dirname(filesource.baseurl if filesource.isArchive else filename)
                self.updateFileHistory(filename, importToDTS)
            elif len(filename) == 1:
                self.updateFileHistory(filename[0], importToDTS)
            thread = threading.Thread(target=self.backgroundLoadXbrl, args=(filesource,importToDTS,selectTopView), daemon=True).start()

    def webOpen(self, *ignore):
        if not self.okayToContinue():
            return
        url = DialogURL.askURL(self.parent, buttonSEC=True, buttonRSS=True)
        if url:
            self.updateFileHistory(url, False)
            for xbrlLoadedMethod in pluginClassMethods("CntlrWinMain.Xbrl.Open"):
                url = xbrlLoadedMethod(self, url) # runs in GUI thread, allows mapping url, mult return url
            filesource = openFileSource(url,self)
            if filesource.isArchive and not filesource.selection: # or filesource.isRss:
                from arelle import DialogOpenArchive
                url = DialogOpenArchive.askArchiveFile(self, filesource)
                self.updateFileHistory(url, False)
            thread = threading.Thread(target=self.backgroundLoadXbrl, args=(filesource,False,False), daemon=True).start()

    def importWebOpen(self, *ignore):
        if not self.modelManager.modelXbrl or self.modelManager.modelXbrl.modelDocument.type not in (
             ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE, ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Import requires an opened DTS"), parent=self.parent)
            return False
        url = DialogURL.askURL(self.parent, buttonSEC=False, buttonRSS=False)
        if url:
            self.fileOpenFile(url, importToDTS=True)


    def backgroundLoadXbrl(self, filesource, importToDTS, selectTopView):
        startedAt = time.time()
        try:
            if importToDTS:
                action = _("imported")
                profileStat = "import"
                modelXbrl = self.modelManager.modelXbrl
                if modelXbrl:
                    ModelDocument.load(modelXbrl, filesource.url, isSupplemental=importToDTS)
                    modelXbrl.relationshipSets.clear() # relationships have to be re-cached
            else:
                action = _("loaded")
                profileStat = "load"
                modelXbrl = self.modelManager.load(filesource, _("views loading"),
                                                   checkModifiedTime=isHttpUrl(filesource.url)) # check modified time if GUI-loading from web
        except ModelDocument.LoadingException:
            self.showStatus(_("Loading terminated, unrecoverable error"), 15000)
            return
        except Exception as err:
            msg = _("Exception loading {0}: {1}, at {2}").format(
                     filesource.url,
                     err,
                     traceback.format_tb(sys.exc_info()[2]))
            # not sure if message box can be shown from background thread
            # tkinter.messagebox.showwarning(_("Exception loading"),msg, parent=self.parent)
            self.addToLog(msg);
            self.showStatus(_("Loading terminated, unrecoverable error"), 15000)
            return
        if modelXbrl and modelXbrl.modelDocument:
            statTime = time.time() - startedAt
            modelXbrl.profileStat(profileStat, statTime)
            self.addToLog(format_string(self.modelManager.locale,
                                        _("%s in %.2f secs"),
                                        (action, statTime)))
            if modelXbrl.hasTableRendering:
                self.showStatus(_("Initializing table rendering"))
                RenderingEvaluator.init(modelXbrl)
            self.showStatus(_("{0}, preparing views").format(action))
            self.waitForUiThreadQueue() # force status update
            self.uiThreadQueue.put((self.showLoadedXbrl, [modelXbrl, importToDTS, selectTopView]))
        else:
            self.addToLog(format_string(self.modelManager.locale,
                                        _("not successfully %s in %.2f secs"),
                                        (action, time.time() - startedAt)))
            self.showStatus(_("Loading terminated"), 15000)

    def showLoadedXbrl(self, modelXbrl, attach, selectTopView=False):
        startedAt = time.time()
        currentAction = "setting title"
        topView = None
        self.currentView = None
        try:
            if attach:
                modelXbrl.closeViews()
            self.parent.title(_("arelle - {0}").format(
                            os.path.basename(modelXbrl.modelDocument.uri)))
            self.setValidateTooltipText()
            if modelXbrl.modelDocument.type in ModelDocument.Type.TESTCASETYPES:
                currentAction = "tree view of tests"
                ViewWinTests.viewTests(modelXbrl, self.tabWinTopRt)
                topView = modelXbrl.views[-1]
            elif modelXbrl.modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
                currentAction = "view of versioning report"
                ViewWinVersReport.viewVersReport(modelXbrl, self.tabWinTopRt)
                from arelle.ViewWinDiffs import ViewWinDiffs
                ViewWinDiffs(modelXbrl, self.tabWinBtm, lang=self.labelLang)
            elif modelXbrl.modelDocument.type == ModelDocument.Type.RSSFEED:
                currentAction = "view of RSS feed"
                ViewWinRssFeed.viewRssFeed(modelXbrl, self.tabWinTopRt)
                topView = modelXbrl.views[-1]
            else:
                if modelXbrl.hasTableIndexing:
                    currentAction = "table index view"
                    ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopLeft, ("Tables", (XbrlConst.euGroupTable,)), lang=self.labelLang,
                                                               treeColHdr="Table Index", showLinkroles=False, showColumns=False, expandAll=True)
                elif modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
                    currentAction = "table index view"
                    firstTableLinkroleURI, indexLinkroleURI = TableStructure.evaluateTableIndex(modelXbrl, lang=self.labelLang)
                    if firstTableLinkroleURI is not None:
                        ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopLeft, ("Tables", (XbrlConst.parentChild,)), lang=self.labelLang, linkrole=indexLinkroleURI,
                                                                   treeColHdr="Table Index", showRelationships=False, showColumns=False, expandAll=False, hasTableIndex=True)
                '''
                elif (modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET) and
                      not modelXbrl.hasTableRendering):
                    currentAction = "facttable ELRs view"
                    ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopLeft, ("Tables", (XbrlConst.parentChild,)), lang=self.labelLang,
                                                               treeColHdr="Fact Table Index", showLinkroles=True, showColumns=False, showRelationships=False, expandAll=False)
                '''
                currentAction = "tree view of DTS"
                ViewWinDTS.viewDTS(modelXbrl, self.tabWinTopLeft, altTabWin=self.tabWinTopRt)
                currentAction = "view of concepts"
                ViewWinConcepts.viewConcepts(modelXbrl, self.tabWinBtm, "Concepts", lang=self.labelLang, altTabWin=self.tabWinTopRt)
                if modelXbrl.hasTableRendering:  # show rendering grid even without any facts
                    ViewWinRenderedGrid.viewRenderedGrid(modelXbrl, self.tabWinTopRt, lang=self.labelLang)
                    if topView is None: topView = modelXbrl.views[-1]
                if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
                    currentAction = "table view of facts"
                    if (not modelXbrl.hasTableRendering and # table view only if not grid rendered view
                        modelXbrl.relationshipSet(XbrlConst.parentChild)): # requires presentation relationships to render this tab
                        ViewWinFactTable.viewFacts(modelXbrl, self.tabWinTopRt, linkrole=firstTableLinkroleURI, lang=self.labelLang, expandAll=firstTableLinkroleURI is not None)
                        if topView is None: topView = modelXbrl.views[-1]
                    currentAction = "tree/list of facts"
                    ViewWinFactList.viewFacts(modelXbrl, self.tabWinTopRt, lang=self.labelLang)
                    if topView is None: topView = modelXbrl.views[-1]
                currentAction = "presentation linkbase view"
                hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, XbrlConst.parentChild, lang=self.labelLang)
                if hasView and topView is None: topView = modelXbrl.views[-1]
                currentAction = "calculation linkbase view"
                hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, XbrlConst.summationItem, lang=self.labelLang)
                if hasView and topView is None: topView = modelXbrl.views[-1]
                currentAction = "dimensions relationships view"
                hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, "XBRL-dimensions", lang=self.labelLang)
                if hasView and topView is None: topView = modelXbrl.views[-1]
                currentAction = "anchoring relationships view"
                hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, XbrlConst.widerNarrower, lang=self.labelLang, noRelationshipsMsg=False, treeColHdr="Wider-Narrower Relationships")
                if hasView and topView is None: topView = modelXbrl.views[-1]
                if modelXbrl.hasTableRendering:
                    currentAction = "rendering view"
                    hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, "Table-rendering", lang=self.labelLang)
                    if hasView and topView is None: topView = modelXbrl.views[-1]
                if modelXbrl.hasFormulae:
                    currentAction = "formulae view"
                    ViewWinFormulae.viewFormulae(modelXbrl, self.tabWinTopRt)
                    if topView is None: topView = modelXbrl.views[-1]
                for name, arcroles in sorted(self.config.get("arcroleGroups", {}).items()):
                    if XbrlConst.arcroleGroupDetect in arcroles:
                        currentAction = name + " view"
                        hasView = ViewWinRelationshipSet.viewRelationshipSet(modelXbrl, self.tabWinTopRt, (name, arcroles), lang=self.labelLang)
                        if hasView and topView is None: topView = modelXbrl.views[-1]
            currentAction = "property grid"
            ViewWinProperties.viewProperties(modelXbrl, self.tabWinTopLeft)
            currentAction = "log view creation time"
            viewTime = time.time() - startedAt
            modelXbrl.profileStat("view", viewTime)
            self.addToLog(format_string(self.modelManager.locale,
                                        _("views %.2f secs"), viewTime))
            if selectTopView and topView:
                topView.select()
            self.currentView = topView
            currentAction = "plugin method CntlrWinMain.Xbrl.Loaded"
            for xbrlLoadedMethod in pluginClassMethods("CntlrWinMain.Xbrl.Loaded"):
                xbrlLoadedMethod(self, modelXbrl, attach) # runs in GUI thread
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

    def showProfileStats(self):
        modelXbrl = self.modelManager.modelXbrl
        if modelXbrl and self.modelManager.collectProfileStats:
            modelXbrl.logProfileStats()

    def clearProfileStats(self):
        modelXbrl = self.modelManager.modelXbrl
        if modelXbrl and self.modelManager.collectProfileStats:
            modelXbrl.profileStats.clear()

    def fileClose(self, *ignore):
        if not self.okayToContinue():
            return
        self.modelManager.close()
        self.parent.title(_("arelle - Unnamed"))
        self.setValidateTooltipText()
        self.currentView = None

    def fileReopen(self, *ignore):
        self.fileClose()
        fileHistory = self.config.setdefault("fileHistory", [])
        if len(fileHistory) > 0:
            self.fileOpenFile(fileHistory[0])

    def validate(self):
        modelXbrl = self.modelManager.modelXbrl
        if modelXbrl and modelXbrl.modelDocument:
            if (modelXbrl.modelManager.validateDisclosureSystem and
                not modelXbrl.modelManager.disclosureSystem.selection):
                tkinter.messagebox.showwarning(_("arelle - Warning"),
                                _("Validation - disclosure system checks is requested but no disclosure system is selected, please select one by validation - select disclosure system."),
                                parent=self.parent)
            else:
                if modelXbrl.modelDocument.type in ModelDocument.Type.TESTCASETYPES:
                    for pluginXbrlMethod in pluginClassMethods("Testcases.Start"):
                        pluginXbrlMethod(self, None, modelXbrl)
                thread = threading.Thread(target=self.backgroundValidate, daemon=True).start()

    def backgroundValidate(self):
        startedAt = time.time()
        modelXbrl = self.modelManager.modelXbrl
        priorOutputInstance = modelXbrl.formulaOutputInstance
        modelXbrl.formulaOutputInstance = None # prevent closing on background thread by validateFormula
        self.modelManager.validate()
        self.addToLog(format_string(self.modelManager.locale,
                                    _("validated in %.2f secs"),
                                    time.time() - startedAt))
        if not modelXbrl.isClosed and (priorOutputInstance or modelXbrl.formulaOutputInstance):
            self.uiThreadQueue.put((self.showFormulaOutputInstance, [priorOutputInstance, modelXbrl.formulaOutputInstance]))

        self.uiThreadQueue.put((self.logSelect, []))

    def compareDTSes(self):
        countLoadedDTSes = len(self.modelManager.loadedModelXbrls)
        if countLoadedDTSes != 2:
            tkinter.messagebox.showwarning(_("arelle - Warning"),
                            _("Two DTSes are required for the Compare DTSes operation, {0} found").format(countLoadedDTSes),
                            parent=self.parent)
            return False
        versReportFile = self.uiFileDialog("save",
                title=_("arelle - Save Versioning Report File"),
                initialdir=self.config.setdefault("versioningReportDir","."),
                filetypes=[(_("Versioning report file"), "*.xml")],
                defaultextension=".xml")
        if not versReportFile:
            return False
        self.config["versioningReportDir"] = os.path.dirname(versReportFile)
        self.saveConfig()
        thread = threading.Thread(target=self.backgroundCompareDTSes, args=(versReportFile,), daemon=True).start()

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
            self.modelManager.close()
            logging.shutdown()
            global restartMain
            restartMain = restartAfterQuit
            state = self.parent.state()
            if state == "normal":
                self.config["windowGeometry"] = self.parent.geometry()
            if state in ("normal", "zoomed"):
                self.config["windowState"] = state
            if self.isMSW: adjustW = 4; adjustH = 6  # tweak to prevent splitter regions from growing on reloading
            elif self.isMac: adjustW = 54; adjustH = 39
            else: adjustW = 2; adjustH = 2  # linux (tested on ubuntu)
            self.config["tabWinTopLeftSize"] = (self.tabWinTopLeft.winfo_width() - adjustW,
                                                self.tabWinTopLeft.winfo_height() - adjustH)
            super(CntlrWinMain, self).close(saveConfig=True)
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
        # disable internet recheck choices when working offline
        if self.workOffline.get():
            self._cacheMenu.entryconfig(self._internetRecheckLabel, state='disable')
        else:
            self._cacheMenu.entryconfig(self._internetRecheckLabel, state='normal')

    def setInternetRecheck(self, *args):
        self.webCache.recheck = self.internetRecheckVar.get()
        self.config["internetRecheck"] = self.webCache.recheck
        self.addToLog('WebCache.recheck = {}'.format(self.webCache.recheck), messageCode='debug', level=logging.DEBUG)
        self.addToLog('WebCache.maxAgeSeconds = {}'.format(self.webCache.maxAgeSeconds), messageCode='debug', level=logging.DEBUG)
        self.saveConfig()

    def setNoCertificateCheck(self, *args):
        self.webCache.noCertificateCheck = self.noCertificateCheck.get() # resets proxy handlers
        self.config["noCertificateCheck"] = self.webCache.noCertificateCheck
        self.saveConfig()

    def confirmClearWebCache(self):
        if tkinter.messagebox.askyesno(
                    _("arelle - Clear Internet Cache"),
                    _("Are you sure you want to clear the internet cache?"),
                    parent=self.parent):
            def backgroundClearCache():
                self.showStatus(_("Clearing internet cache"))
                self.webCache.clear()
                self.showStatus(_("Internet cache cleared"), 5000)
            thread = threading.Thread(target=backgroundClearCache, daemon=True).start()

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

    def setupUserAgent(self):
        httpUserAgent = tkinter.simpledialog.askstring(
            _("HTTP header User-Agent value"),
            _("Specify non-standard value or cancel to use standard User Agent"),
            initialvalue=self.config.get("httpUserAgent"),
            parent=self.parent)
        self.webCache.httpUserAgent = httpUserAgent
        if not httpUserAgent:
            self.config.pop("httpUserAgent",None)
        else:
            self.config["httpUserAgent"] = httpUserAgent
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
        DialogFormulaParameters.getParameters(self)
        self.setValidateTooltipText()

    def rssWatchOptionsDialog(self, *args):
        from arelle import DialogRssWatch
        DialogRssWatch.getOptions(self)

    # find or open rssWatch view
    def rssWatchControl(self, start=False, stop=False, close=False):
        from arelle.ModelDocument import Type
        from arelle import WatchRss
        if not self.modelManager.rssWatchOptions.get("feedSourceUri"):
            tkinter.messagebox.showwarning(_("RSS Watch Control Error"),
                                _("RSS Feed is not set up, please select options and select feed"),
                                parent=self.parent)
            return False
        rssModelXbrl = None
        for loadedModelXbrl in self.modelManager.loadedModelXbrls:
            if (loadedModelXbrl.modelDocument.type == Type.RSSFEED and
                loadedModelXbrl.modelDocument.uri == self.modelManager.rssWatchOptions.get("feedSourceUri")):
                rssModelXbrl = loadedModelXbrl
                break
        #not loaded
        if start:
            if not rssModelXbrl:
                rssModelXbrl = self.modelManager.create(Type.RSSFEED, self.modelManager.rssWatchOptions.get("feedSourceUri"))
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
            self.modelManager.rssWatchOptions["latestPubDate"] = latestPubDate
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
            self.config["labelLangOverride"] = newValue
            if newValue:
                self.lang = newValue
            else:
                self.lang = self.modelManager.defaultLang
            if self.modelManager.modelXbrl and self.modelManager.modelXbrl.modelDocument:
                self.showLoadedXbrl(self.modelManager.modelXbrl, True) # reload views
            self.saveConfig()

    def setValidateTooltipText(self):
        if self.modelManager.modelXbrl and not self.modelManager.modelXbrl.isClosed and self.modelManager.modelXbrl.modelDocument is not None:
            valType = self.modelManager.modelXbrl.modelDocument.type
            if valType in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
                valName = "DTS"
            else:
                valName = ModelDocument.Type.typeName[valType]
            if valType == ModelDocument.Type.VERSIONINGREPORT:
                v = _("Validate versioning report")
            else:
                if self.modelManager.validateCalcLB:
                    if self.modelManager.validateInferDecimals:
                        c = _("\nCheck calculations (infer decimals)")
                    else:
                        c = _("\nCheck calculations (infer precision)")
                    if self.modelManager.validateDedupCalcs:
                        c += _("\nDeduplicate calculations")
                else:
                    c = ""
                if self.modelManager.validateUtr:
                    u = _("\nCheck unit type registry")
                else:
                    u = ""
                if self.modelManager.validateDisclosureSystem:
                    v = _("Validate {0}\nCheck disclosure system rules\n{1}{2}{3}").format(
                           valName, self.modelManager.disclosureSystem.selection,c,u)
                else:
                    v = _("Validate {0}{1}{2}").format(valName, c, u)
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

    def setValidateDedupCalcs(self, *args):
        self.modelManager.validateDedupCalcs = self.validateDedupCalcs.get()
        self.config["validateDedupCalcs"] = self.modelManager.validateDedupCalcs
        self.saveConfig()
        self.setValidateTooltipText()

    def setValidateUtr(self, *args):
        self.modelManager.validateUtr = self.validateUtr.get()
        self.config["validateUtr"] = self.modelManager.validateUtr
        self.saveConfig()
        self.setValidateTooltipText()

    def setCollectProfileStats(self, *args):
        self.modelManager.collectProfileStats = self.collectProfileStats.get()
        self.config["collectProfileStats"] = self.modelManager.collectProfileStats
        self.saveConfig()

    def setShowDebugMessages(self, *args):
        self.config["showDebugMessages"] = self.showDebugMessages.get()
        self.saveConfig()

    def find(self, *args):
        from arelle.DialogFind import find
        find(self)

    def helpAbout(self, event=None):
        from arelle import DialogAbout, Version
        from lxml import etree
        DialogAbout.about(self.parent,
                          _("About arelle"),
                          os.path.join(self.imagesDir, "arelle32.gif"),
                          _("arelle\u00ae {version} ({wordSize}bit {platform})\n"
                              "An open source XBRL platform\n"
                              "{copyrightLabel}\n"
                              "http://www.arelle.org\nsupport@arelle.org\n\n"
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
                              "\n   Python\u00ae {pythonVersion} \u00a9 2001-2016 Python Software Foundation"
                              "\n   Tcl/Tk {tcltkVersion} \u00a9 Univ. of Calif., Sun, Scriptics, ActiveState, and others"
                              "\n   PyParsing \u00a9 2003-2013 Paul T. McGuire"
                              "\n   lxml {lxmlVersion} \u00a9 2004 Infrae, ElementTree \u00a9 1999-2004 by Fredrik Lundh"
                              "{bottleCopyright}"
                              "\n   May include installable plug-in modules with author-specific license terms").format(
                                  version=Version.__version__,
                                  wordSize=self.systemWordSize,
                                  platform=platform.machine(),
                                  copyrightLabel=copyrightLabel.replace("(c)", "\u00a9"),
                                  pythonVersion=f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}',
                                  tcltkVersion=Tcl().eval('info patchlevel'),
                                  lxmlVersion=f'{etree.LXML_VERSION[0]}.{etree.LXML_VERSION[1]}.{etree.LXML_VERSION[2]}',
                                  bottleCopyright=_("\n   Bottle \u00a9 2011-2013 Marcel Hellkamp"
                                                    "\n   CherryPy \u00a9 2002-2013 CherryPy Team") if self.hasWebServer else ""
                          ))


    # worker threads addToLog
    def addToLog(self, message, messageCode="", messageArgs=None, file="", refs=[], level=logging.INFO):
        if level < logging.INFO and not self.showDebugMessages.get():
            return # skip DEBUG and INFO-RESULT messages
        if messageCode and messageCode not in message: # prepend message code
            message = "[{}] {}".format(messageCode, message)
        if refs:
            message += " - " + Cntlr.logRefsFileLines(refs)
        elif file:
            if isinstance(file, (tuple,list,set)):
                message += " - " + ", ".join(file)
            elif isinstance(file, str):
                message += " - " + file
        if isinstance(messageArgs, dict):
            try:
                message = message % messageArgs
            except (KeyError, TypeError, ValueError) as ex:
                message += " \nMessage log error: " + str(ex) + " \nMessage arguments: " + str(messageArgs)
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
        filename = self.uiFileDialog("save",
                title=_("arelle - Save Messages Log"),
                initialdir=".",
                filetypes=[(_("Txt file"), "*.txt")],
                defaultextension=".txt")
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
        self.waitForUiThreadQueue() # force prior ui view updates if any
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
    def showStatus(self, message: str, clearAfter: int | None = None) -> None:
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

    # web file login requested
    def internet_logon(self, url, quotedUrl, dialogCaption, dialogText):
        from arelle.DialogUserPassword import askInternetLogon
        untilDone = threading.Event()
        result = []
        self.uiThreadQueue.put((askInternetLogon, [self.parent, url, quotedUrl, dialogCaption, dialogText, untilDone, result]))
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

    def uiFileDialog(self, action, title=None, initialdir=None, filetypes=[], defaultextension=None, owner=None, multiple=False, parent=None):
        if parent is None: parent = self.parent
        if multiple and action == "open":  # return as simple list of file names
            multFileNames = tkinter.filedialog.askopenfilename(
                                    multiple=True,
                                    title=title,
                                    initialdir=initialdir,
                                    filetypes=[] if self.isMac else filetypes,
                                    defaultextension=defaultextension,
                                    parent=parent)
            if isinstance(multFileNames, (tuple,list)):
                return multFileNames
            return re.findall("[{]([^}]+)[}]",  # older multiple returns "{file1} {file2}..."
                              multFileNames)
        elif self.hasWin32gui:
            import win32gui
            try:
                filename, filter, flags = {"open":win32gui.GetOpenFileNameW,
                                           "save":win32gui.GetSaveFileNameW}[action](
                            hwndOwner=(owner if owner else parent).winfo_id(),
                            hInstance=win32gui.GetModuleHandle(None),
                            Filter='\0'.join(e for t in filetypes+['\0'] for e in t),
                            MaxFile=4096,
                            InitialDir=initialdir,
                            Title=title,
                            DefExt=defaultextension)
                return filename
            except win32gui.error:
                return ''
        else:
            return {"open":tkinter.filedialog.askopenfilename,
                    "save":tkinter.filedialog.asksaveasfilename}[action](
                            title=title,
                            initialdir=initialdir,
                            filetypes=[] if self.isMac else filetypes,
                            defaultextension=defaultextension,
                            parent=parent)

from arelle import DialogFormulaParameters

class WinMainLogHandler(logging.Handler):
    def __init__(self, cntlr):
        super(WinMainLogHandler, self).__init__()
        self.cntlr = cntlr
        #formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(file)s %(sourceLine)s")
        formatter = Cntlr.LogFormatter("[%(messageCode)s] %(message)s - %(file)s")
        self.setFormatter(formatter)
        self.logRecordBuffer = None
    def startLogBuffering(self):
        if self.logRecordBuffer is None:
            self.logRecordBuffer = []
    def endLogBuffering(self):
        self.logRecordBuffer = None
    def flush(self):
        ''' Nothing to flush '''
    def emit(self, logRecord):
        if self.logRecordBuffer is not None:
            self.logRecordBuffer.append(logRecord)
        # add to logView
        msg = self.format(logRecord)
        try:
            self.cntlr.addToLog(msg, level=logRecord.levelno)
        except:
            pass

class TkinterCallWrapper:
    """Replacement for internal tkinter class. Stores function to call when some user
    defined Tcl function is called e.g. after an event occurred."""
    def __init__(self, func, subst, widget):
        """Store FUNC, SUBST and WIDGET as members."""
        self.func = func
        self.subst = subst
        self.widget = widget
    def __call__(self, *args):
        """Apply first function SUBST to arguments, than FUNC."""
        try:
            if self.subst:
                args = self.subst(*args)
            return self.func(*args)
        except SystemExit as msg:
            raise SystemExit(msg)
        except Exception:
            # this was tkinter's standard coding: self.widget._report_exception()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            msg = ''.join(traceback.format_exception_only(exc_type, exc_value))
            tracebk = ''.join(traceback.format_tb(exc_traceback, limit=30))
            tkinter.messagebox.showerror(_("Exception"),
                                         _("{0}\nCall trace\n{1}").format(msg, tracebk))



def main():
    # this is the entry called by arelleGUI.pyw for windows
    if getattr(sys, 'frozen', False):
        if sys.platform in ("darwin", "linux"): # Use frozen tcl, tk and TkTable libraries
            _resourcesDir = os.path.join(Cntlr.resourcesDir(), "lib")
            for _tcltk in ("tcl", "tk", "Tktable"):
                for _tcltkVer in ("8.5", "8.6", "2.11"): # Tktable ver is 2.11
                    _d = _resourcesDir
                    while len(_d) > 3: # stop at root directory
                        _tcltkDir = os.path.join(_d, _tcltk + _tcltkVer)
                        if os.path.exists(_tcltkDir):
                            os.environ[_tcltk.upper() + "_LIBRARY"] = _tcltkDir
                            break
                        _d = os.path.dirname(_d)
        elif sys.platform == 'win32': # windows requires fake stdout/stderr because no write/flush (e.g., EdgarRenderer LocalViewer pybottle)
            class dummyFrozenStream:
                def __init__(self): pass
                def write(self,data): pass
                def read(self,data): pass
                def flush(self): pass
                def close(self): pass
            sys.stdout = dummyFrozenStream()
            sys.stderr = dummyFrozenStream()
            sys.stdin = dummyFrozenStream()

    global restartMain
    while restartMain:
        restartMain = False
        try:
            application = Tk()
            cntlrWinMain = CntlrWinMain(application)
            application.protocol("WM_DELETE_WINDOW", cntlrWinMain.quit)
            if sys.platform == "darwin" and not __file__.endswith(".app/Contents/MacOS/arelleGUI"):
                # not built app - launches behind python or eclipse
                application.lift()
                application.call('wm', 'attributes', '.', '-topmost', True)
                cntlrWinMain.uiThreadQueue.put((application.call, ['wm', 'attributes', '.', '-topmost', False]))
                os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')
            application.mainloop()
        except Exception: # unable to start Tk or other fatal error
            exc_type, exc_value, exc_traceback = sys.exc_info()
            msg = ''.join(traceback.format_exception_only(exc_type, exc_value))
            tracebk = ''.join(traceback.format_tb(exc_traceback, limit=7))
            logMsg = "{}\nCall Trace\n{}\nEnvironment {}".format(msg, tracebk, os.environ)
            #print(logMsg, file=sys.stderr)
            if syslog is not None:
                syslog.openlog("Arelle")
                syslog.syslog(syslog.LOG_ALERT, logMsg)
            try: # this may crash.  Note syslog has 1k message length
                logMsg = "tcl_pkgPath {} tcl_library {} tcl version {}".format(
                    Tcl().getvar("tcl_pkgPath"), Tcl().getvar("tcl_library"), Tcl().eval('info patchlevel'))
                if syslog is not None:
                    syslog.syslog(syslog.LOG_ALERT, logMsg)
                #print(logMsg, file=sys.stderr)
            except:
                pass
            if syslog is not None:
                syslog.closelog()

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
