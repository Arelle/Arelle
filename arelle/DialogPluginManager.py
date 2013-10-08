'''
Created on March 1, 2012

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

based on pull request 4

'''
from tkinter import Toplevel, font, messagebox, VERTICAL, HORIZONTAL, N, S, E, W
from tkinter.constants import DISABLED, ACTIVE
try:
    from tkinter.ttk import Treeview, Scrollbar, Frame, Label, Button
except ImportError:
    from ttk import Treeview, Scrollbar, Frame, Label, Button
from arelle import PluginManager, DialogURL
from arelle.CntlrWinTooltip import ToolTip
import re, os, time

def dialogPluginManager(mainWin):
    # check for updates in background
    import threading
    thread = threading.Thread(target=lambda cntlr=mainWin: backgroundCheckForUpdates(cntlr))
    thread.daemon = True
    thread.start()

def backgroundCheckForUpdates(cntlr):
    cntlr.showStatus(_("Checking for updates to plug-ins")) # clear web loading status
    modulesWithNewerFileDates = PluginManager.modulesWithNewerFileDates()
    if modulesWithNewerFileDates:
        cntlr.showStatus(_("Updates are available for these plug-ins: {0}")
                              .format(', '.join(modulesWithNewerFileDates)), clearAfter=5000)
    else:
        cntlr.showStatus(_("No updates found for plug-ins."), clearAfter=5000)
    time.sleep(0.1) # Mac locks up without this, may be needed for empty ui queue? 
    cntlr.uiThreadQueue.put((DialogPluginManager, [cntlr, modulesWithNewerFileDates]))

class DialogPluginManager(Toplevel):
    def __init__(self, mainWin, modulesWithNewerFileDates):
        super(DialogPluginManager, self).__init__(mainWin.parent)
        
        self.ENABLE = _("Enable")
        self.DISABLE = _("Disable")
        self.parent = mainWin.parent
        self.cntlr = mainWin
        
        # copy plugins for temporary display
        self.pluginConfig = PluginManager.pluginConfig
        self.pluginConfigChanged = False
        self.uiClassMethodsChanged = False
        self.modelClassesChanged = False
        self.modulesWithNewerFileDates = modulesWithNewerFileDates
        
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", self.parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))

        self.title(_("Plug-in Manager"))
        frame = Frame(self)
        
        # left button frame
        buttonFrame = Frame(frame, width=40)
        buttonFrame.columnconfigure(0, weight=1)
        addLabel = Label(buttonFrame, text=_("Find plug-in modules:"), wraplength=60, justify="center")
        addLocalButton = Button(buttonFrame, text=_("Locally"), command=self.findLocally)
        ToolTip(addLocalButton, text=_("File chooser allows selecting python module files to add (or reload) plug-ins, from the local file system."), wraplength=240)
        addWebButton = Button(buttonFrame, text=_("On Web"), command=self.findOnWeb)
        ToolTip(addWebButton, text=_("Dialog to enter URL full path to load (or reload) plug-ins, from the web or local file system."), wraplength=240)
        addLabel.grid(row=0, column=0, pady=4)
        addLocalButton.grid(row=1, column=0, pady=4)
        addWebButton.grid(row=2, column=0, pady=4)
        buttonFrame.grid(row=0, column=0, rowspan=2, sticky=(N, S, W), padx=3, pady=3)
        
        # right tree frame (plugins already known to arelle)
        modulesFrame = Frame(frame, width=700)
        vScrollbar = Scrollbar(modulesFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(modulesFrame, orient=HORIZONTAL)
        self.modulesView = Treeview(modulesFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set, height=7)
        self.modulesView.grid(row=0, column=0, sticky=(N, S, E, W))
        self.modulesView.bind('<<TreeviewSelect>>', self.moduleSelect)
        hScrollbar["command"] = self.modulesView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.modulesView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        modulesFrame.columnconfigure(0, weight=1)
        modulesFrame.rowconfigure(0, weight=1)
        modulesFrame.grid(row=0, column=1, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.modulesView.focus_set()

        self.modulesView.column("#0", width=120, anchor="w")
        self.modulesView.heading("#0", text=_("Name"))
        self.modulesView["columns"] = ("author", "ver", "status", "date", "update", "descr", "license")
        self.modulesView.column("author", width=100, anchor="w", stretch=False)
        self.modulesView.heading("author", text=_("Author"))
        self.modulesView.column("ver", width=50, anchor="w", stretch=False)
        self.modulesView.heading("ver", text=_("Version"))
        self.modulesView.column("status", width=50, anchor="w", stretch=False)
        self.modulesView.heading("status", text=_("Status"))
        self.modulesView.column("date", width=70, anchor="w", stretch=False)
        self.modulesView.heading("date", text=_("File Date"))
        self.modulesView.column("update", width=50, anchor="w", stretch=False)
        self.modulesView.heading("update", text=_("Update"))
        self.modulesView.column("descr", width=200, anchor="w", stretch=False)
        self.modulesView.heading("descr", text=_("Description"))
        self.modulesView.column("license", width=70, anchor="w", stretch=False)
        self.modulesView.heading("license", text=_("License"))

        classesFrame = Frame(frame)
        vScrollbar = Scrollbar(classesFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(classesFrame, orient=HORIZONTAL)
        self.classesView = Treeview(classesFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set, height=5)
        self.classesView.grid(row=0, column=0, sticky=(N, S, E, W))
        hScrollbar["command"] = self.classesView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.classesView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        classesFrame.columnconfigure(0, weight=1)
        classesFrame.rowconfigure(0, weight=1)
        classesFrame.grid(row=1, column=1, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.classesView.focus_set()
        
        self.classesView.column("#0", width=200, anchor="w")
        self.classesView.heading("#0", text=_("Class"))
        self.classesView["columns"] = ("modules",)
        self.classesView.column("modules", width=500, anchor="w", stretch=False)
        self.classesView.heading("modules", text=_("Modules"))
        
        # bottom frame module info details
        moduleInfoFrame = Frame(frame, width=700)
        moduleInfoFrame.columnconfigure(1, weight=1)
        
        self.moduleNameLabel = Label(moduleInfoFrame, wraplength=600, justify="left", 
                                     font=font.Font(family='Helvetica', size=12, weight='bold'))
        self.moduleNameLabel.grid(row=0, column=0, columnspan=4, sticky=W)
        self.moduleAuthorHdr = Label(moduleInfoFrame, text=_("author:"), state=DISABLED)
        self.moduleAuthorHdr.grid(row=1, column=0, sticky=W)
        self.moduleAuthorLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleAuthorLabel.grid(row=1, column=1, columnspan=3, sticky=W)
        self.moduleDescrHdr = Label(moduleInfoFrame, text=_("description:"), state=DISABLED)
        self.moduleDescrHdr.grid(row=2, column=0, sticky=W)
        self.moduleDescrLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleDescrLabel.grid(row=2, column=1, columnspan=3, sticky=W)
        self.moduleClassesHdr = Label(moduleInfoFrame, text=_("classes:"), state=DISABLED)
        self.moduleClassesHdr.grid(row=3, column=0, sticky=W)
        self.moduleClassesLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleClassesLabel.grid(row=3, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleClassesLabel, text=_("List of classes that this plug-in handles."), wraplength=240)
        self.moduleUrlHdr = Label(moduleInfoFrame, text=_("URL:"), state=DISABLED)
        self.moduleUrlHdr.grid(row=4, column=0, sticky=W)
        self.moduleUrlLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleUrlLabel.grid(row=4, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleUrlLabel, text=_("URL of plug-in module (local file path or web loaded file)."), wraplength=240)
        self.moduleDateHdr = Label(moduleInfoFrame, text=_("date:"), state=DISABLED)
        self.moduleDateHdr.grid(row=5, column=0, sticky=W)
        self.moduleDateLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleDateLabel.grid(row=5, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleDateLabel, text=_("Date of currently loaded module file (with parenthetical node when an update is available)."), wraplength=240)
        self.moduleLicenseHdr = Label(moduleInfoFrame, text=_("license:"), state=DISABLED)
        self.moduleLicenseHdr.grid(row=6, column=0, sticky=W)
        self.moduleLicenseLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleLicenseLabel.grid(row=6, column=1, columnspan=3, sticky=W)
        self.moduleEnableButton = Button(moduleInfoFrame, text=self.ENABLE, state=DISABLED, command=self.moduleEnable)
        ToolTip(self.moduleEnableButton, text=_("Enable/disable plug in."), wraplength=240)
        self.moduleEnableButton.grid(row=7, column=1, sticky=E)
        self.moduleReloadButton = Button(moduleInfoFrame, text=_("Reload"), state=DISABLED, command=self.moduleReload)
        ToolTip(self.moduleReloadButton, text=_("Reload/update plug in."), wraplength=240)
        self.moduleReloadButton.grid(row=7, column=2, sticky=E)
        self.moduleRemoveButton = Button(moduleInfoFrame, text=_("Remove"), state=DISABLED, command=self.moduleRemove)
        ToolTip(self.moduleRemoveButton, text=_("Remove plug in from plug in table (does not erase the plug in's file)."), wraplength=240)
        self.moduleRemoveButton.grid(row=7, column=3, sticky=E)
        moduleInfoFrame.grid(row=2, column=0, columnspan=5, sticky=(N, S, E, W), padx=3, pady=3)
        moduleInfoFrame.config(borderwidth=4, relief="groove")
        
        okButton = Button(frame, text=_("Close"), command=self.ok)
        ToolTip(okButton, text=_("Accept and changes (if any) and close dialog."), wraplength=240)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        ToolTip(cancelButton, text=_("Cancel changes (if any) and close dialog."), wraplength=240)
        okButton.grid(row=3, column=3, sticky=(S,E), pady=3)
        cancelButton.grid(row=3, column=4, sticky=(S,E), pady=3, padx=3)
        
        self.loadTreeViews()

        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))
        
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)
        
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)
        
    def loadTreeViews(self):
        self.selectedModule = None

        # clear previous treeview entries
        for previousNode in self.modulesView.get_children(""): 
            self.modulesView.delete(previousNode)

        for i, moduleItem in enumerate(sorted(self.pluginConfig.get("modules", {}).items())):
            moduleInfo = moduleItem[1]
            name = moduleInfo.get("name", moduleItem[0])
            node = self.modulesView.insert("", "end", name, text=name)
            self.modulesView.set(node, "author", moduleInfo.get("author"))
            self.modulesView.set(node, "ver", moduleInfo.get("version"))
            self.modulesView.set(node, "status", moduleInfo.get("status"))
            self.modulesView.set(node, "date", moduleInfo.get("fileDate"))
            if name in self.modulesWithNewerFileDates:
                self.modulesView.set(node, "update", _("available"))
            self.modulesView.set(node, "descr", moduleInfo.get("description"))
            self.modulesView.set(node, "license", moduleInfo.get("license"))
        
        # clear previous treeview entries
        for previousNode in self.classesView.get_children(""): 
            self.classesView.delete(previousNode)

        for i, classItem in enumerate(sorted(self.pluginConfig.get("classes", {}).items())):
            className, moduleList = classItem
            node = self.classesView.insert("", "end", className, text=className)
            self.classesView.set(node, "modules", ', '.join(moduleList))
            
        self.moduleSelect()  # clear out prior selection

    def ok(self, event=None):
        if self.pluginConfigChanged:
            PluginManager.pluginConfig = self.pluginConfig
            PluginManager.pluginConfigChanged = True
            PluginManager.reset()  # force reloading of modules
        if self.uiClassMethodsChanged or self.modelClassesChanged:  # may require reloading UI
            affectedItems = ""
            if self.uiClassMethodsChanged:
                affectedItems += _("menus of the user interface")
            if self.uiClassMethodsChanged and self.modelClassesChanged:
                affectedItems += _(" and ")
            if self.modelClassesChanged:
                affectedItems += _("model objects of the processor")
            if messagebox.askyesno(_("User interface plug-in change"),
                                   _("A change in plug-in class methods may have affected {0}.  " 
                                     "Please restart Arelle to due to these changes.  \n\n"
                                     "Should Arelle restart itself now "
                                     "(if there are any unsaved changes they would be lost!)?"
                                     ).format(affectedItems),
                                   parent=self):
                self.cntlr.uiThreadQueue.put((self.cntlr.quit, [None, True]))
        self.close()
        
    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()
                
    def moduleSelect(self, *args):
        node = (self.modulesView.selection() or (None,))[0]
        moduleInfo = self.pluginConfig.get("modules", {}).get(node)
        if moduleInfo:
            self.selectedModule = node
            name = moduleInfo["name"]
            self.moduleNameLabel.config(text=name)
            self.moduleAuthorHdr.config(state=ACTIVE)
            self.moduleAuthorLabel.config(text=moduleInfo["author"])
            self.moduleDescrHdr.config(state=ACTIVE)
            self.moduleDescrLabel.config(text=moduleInfo["description"])
            self.moduleClassesHdr.config(state=ACTIVE)
            self.moduleClassesLabel.config(text=', '.join(moduleInfo["classMethods"]))
            self.moduleUrlHdr.config(state=ACTIVE)
            self.moduleUrlLabel.config(text=moduleInfo["moduleURL"])
            self.moduleDateHdr.config(state=ACTIVE)
            self.moduleDateLabel.config(text=moduleInfo["fileDate"] + " " +
                    (_("(an update is available)") if name in self.modulesWithNewerFileDates else ""))
            self.moduleLicenseHdr.config(state=ACTIVE)
            self.moduleLicenseLabel.config(text=moduleInfo["license"])
            self.moduleEnableButton.config(state=ACTIVE,
                                           text={"enabled":self.DISABLE,
                                                 "disabled":self.ENABLE}[moduleInfo["status"]])
            self.moduleReloadButton.config(state=ACTIVE)
            self.moduleRemoveButton.config(state=ACTIVE)
        else:
            self.selectedModule = None
            self.moduleNameLabel.config(text="")
            self.moduleAuthorHdr.config(state=DISABLED)
            self.moduleAuthorLabel.config(text="")
            self.moduleDescrHdr.config(state=DISABLED)
            self.moduleDescrLabel.config(text="")
            self.moduleClassesHdr.config(state=DISABLED)
            self.moduleClassesLabel.config(text="")
            self.moduleUrlHdr.config(state=DISABLED)
            self.moduleUrlLabel.config(text="")
            self.moduleDateHdr.config(state=DISABLED)
            self.moduleDateLabel.config(text="")
            self.moduleLicenseHdr.config(state=DISABLED)
            self.moduleLicenseLabel.config(text="")
            self.moduleEnableButton.config(state=DISABLED, text=self.ENABLE)
            self.moduleReloadButton.config(state=DISABLED)
            self.moduleRemoveButton.config(state=DISABLED)
        
    def findLocally(self):
        initialdir = self.cntlr.pluginDir # default plugin directory
        if not self.cntlr.isMac: # can't navigate within app easily, always start in default directory
            initialdir = self.cntlr.config.setdefault("pluginOpenDir", initialdir)
        filename = self.cntlr.uiFileDialog("open",
                                           owner=self,
                                           title=_("Choose plug-in module file"),
                                           initialdir=initialdir,
                                           filetypes=[(_("Python files"), "*.py")],
                                           defaultextension=".py")
        if filename:
            # check if a package is selected (any file in a directory containing an __init__.py
            if (os.path.isdir(os.path.dirname(filename)) and
                os.path.isfile(os.path.join(os.path.dirname(filename), "__init__.py"))):
                filename = os.path.dirname(filename) # refer to the package instead
            self.cntlr.config["pluginOpenDir"] = os.path.dirname(filename)
            moduleInfo = PluginManager.moduleModuleInfo(filename)
            self.loadFoundModuleInfo(moduleInfo, filename)
                

    def findOnWeb(self):
        url = DialogURL.askURL(self)
        if url:  # url is the in-cache or local file
            moduleInfo = PluginManager.moduleModuleInfo(url)
            self.cntlr.showStatus("") # clear web loading status
            self.loadFoundModuleInfo(moduleInfo, url)
                
    def loadFoundModuleInfo(self, moduleInfo, url):
        if moduleInfo and moduleInfo.get("name"):
            self.addPluginConfigModuleInfo(moduleInfo)
            self.loadTreeViews()
        else:
            messagebox.showwarning(_("Module is not itself a plug-in or in a directory with package __init__.py plug-in.  "),
                                   _("File does not itself contain a python program with an appropriate __pluginInfo__ declaration: \n\n{0}")
                                   .format(url),
                                   parent=self)
            
    def removePluginConfigModuleInfo(self, name):
        moduleInfo = self.pluginConfig["modules"].get(name)
        if moduleInfo:
            for classMethod in moduleInfo["classMethods"]:
                classMethods = self.pluginConfig["classes"].get(classMethod)
                if classMethods and name in classMethods:
                    classMethods.remove(name)
                    if not classMethods: # list has become unused
                        del self.pluginConfig["classes"][classMethod] # remove class
                    if classMethod.startswith("CntlrWinMain.Menu"):
                        self.uiClassMethodsChanged = True  # may require reloading UI
                    elif classMethod == "ModelObjectFactory.ElementSubstitutionClasses":
                        self.modelClassesChanged = True # model object factor classes changed
            del self.pluginConfig["modules"][name]
            self.pluginConfigChanged = True

    def addPluginConfigModuleInfo(self, moduleInfo):
        name = moduleInfo["name"]
        self.removePluginConfigModuleInfo(name)  # remove any prior entry for this module
        self.modulesWithNewerFileDates.discard(name) # no longer has an update available
        self.pluginConfig["modules"][name] = moduleInfo
        # add classes
        for classMethod in moduleInfo["classMethods"]:
            classMethods = self.pluginConfig["classes"].setdefault(classMethod, [])
            if name not in classMethods:
                classMethods.append(name)
            if classMethod.startswith("CntlrWinMain.Menu"):
                self.uiClassMethodsChanged = True  # may require reloading UI
            elif classMethod == "ModelObjectFactory.ElementSubstitutionClasses":
                self.modelClassesChanged = True # model object factor classes changed
        self.pluginConfigChanged = True

    def moduleEnable(self):
        if self.selectedModule in self.pluginConfig["modules"]:
            moduleInfo = self.pluginConfig["modules"][self.selectedModule]
            if self.moduleEnableButton['text'] == self.ENABLE:
                moduleInfo["status"] = "enabled"
                self.moduleEnableButton['text'] = self.DISABLE
            elif self.moduleEnableButton['text'] == self.DISABLE:
                moduleInfo["status"] = "disabled"
                self.moduleEnableButton['text'] = self.ENABLE
            self.pluginConfigChanged = True
            self.loadTreeViews()
            
    def moduleReload(self):
        if self.selectedModule in self.pluginConfig["modules"]:
            url = self.pluginConfig["modules"][self.selectedModule].get("moduleURL")
            if url:
                moduleInfo = PluginManager.moduleModuleInfo(url, reload=True)
                if moduleInfo:
                    self.addPluginConfigModuleInfo(moduleInfo)
                    self.loadTreeViews()
                    self.cntlr.showStatus(_("{0} reloaded").format(moduleInfo.get("name")), clearAfter=5000)
                else:
                    messagebox.showwarning(_("Module error"),
                                           _("File or module cannot be reloaded: \n\n{0}")
                                           .format(url),
                                           parent=self)

    def moduleRemove(self):
        if self.selectedModule in self.pluginConfig["modules"]:
            self.removePluginConfigModuleInfo(self.selectedModule)
            self.pluginConfigChanged = True
            self.loadTreeViews()
                    
