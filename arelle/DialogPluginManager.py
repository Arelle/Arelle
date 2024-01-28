'''
See COPYRIGHT.md for copyright information.

based on pull request 4

'''
from __future__ import annotations

from importlib.metadata import EntryPoint
from tkinter import Toplevel, font, messagebox, VERTICAL, HORIZONTAL, N, S, E, W
from tkinter.constants import DISABLED, ACTIVE

from arelle.PluginManager import EntryPointRef

try:
    from tkinter.ttk import Treeview, Scrollbar, Frame, Label, Button
except ImportError:
    from ttk import Treeview, Scrollbar, Frame, Label, Button
from arelle import PluginManager, DialogURL, DialogOpenArchive
from arelle.CntlrWinTooltip import ToolTip
import os, time
import regex as re
EMPTYLIST = []
GROUPSEP = '\x01d'

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
        self.customTransformsChanged = False
        self.disclosureSystemTypesChanged = False
        self.hostSystemFeaturesChanged = False
        self.modulesWithNewerFileDates = modulesWithNewerFileDates

        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", self.parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))

        self.title(_("Plug-in Manager"))
        frame = Frame(self)

        # left button frame
        buttonFrame = Frame(frame, width=40)
        buttonFrame.columnconfigure(0, weight=1)
        addLabel = Label(buttonFrame, text=_("Find plug-in modules:"), wraplength=60, justify="center")
        addSelectLocalButton = Button(buttonFrame, text=_("Select"), command=self.selectLocally)
        ToolTip(addSelectLocalButton, text=_("Select python module files from the local plugin directory."), wraplength=240)
        addBrowseLocalButton = Button(buttonFrame, text=_("Browse"), command=self.browseLocally)
        ToolTip(addBrowseLocalButton, text=_("File chooser allows browsing and selecting python module files to add (or reload) plug-ins, from the local file system."), wraplength=240)
        addWebButton = Button(buttonFrame, text=_("On Web"), command=self.findOnWeb)
        ToolTip(addWebButton, text=_("Dialog to enter URL full path to load (or reload) plug-ins, from the web or local file system."), wraplength=240)
        addLabel.grid(row=0, column=0, pady=4)
        addSelectLocalButton.grid(row=1, column=0, pady=4)
        addBrowseLocalButton.grid(row=2, column=0, pady=4)
        addWebButton.grid(row=3, column=0, pady=4)
        buttonFrame.grid(row=0, column=0, rowspan=3, sticky=(N, S, W), padx=3, pady=3)

        # right tree frame (plugins already known to arelle)
        modulesFrame = Frame(frame, width=720)
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
        self.modulesView.column("ver", width=60, anchor="w", stretch=False)
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
        self.moduleVersionHdr = Label(moduleInfoFrame, text=_("version:"), state=DISABLED)
        self.moduleVersionHdr.grid(row=4, column=0, sticky=W)
        self.moduleVersionLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleVersionLabel.grid(row=4, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleVersionLabel, text=_("Version of plug-in module."), wraplength=240)
        self.moduleUrlHdr = Label(moduleInfoFrame, text=_("URL:"), state=DISABLED)
        self.moduleUrlHdr.grid(row=5, column=0, sticky=W)
        self.moduleUrlLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleUrlLabel.grid(row=5, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleUrlLabel, text=_("URL of plug-in module (local file path or web loaded file)."), wraplength=240)
        self.moduleDateHdr = Label(moduleInfoFrame, text=_("date:"), state=DISABLED)
        self.moduleDateHdr.grid(row=6, column=0, sticky=W)
        self.moduleDateLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleDateLabel.grid(row=6, column=1, columnspan=3, sticky=W)
        ToolTip(self.moduleDateLabel, text=_("Date of currently loaded module file (with parenthetical node when an update is available)."), wraplength=240)
        self.moduleLicenseHdr = Label(moduleInfoFrame, text=_("license:"), state=DISABLED)
        self.moduleLicenseHdr.grid(row=7, column=0, sticky=W)
        self.moduleLicenseLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleLicenseLabel.grid(row=7, column=1, columnspan=3, sticky=W)
        self.moduleImportsHdr = Label(moduleInfoFrame, text=_("imports:"), state=DISABLED)
        self.moduleImportsHdr.grid(row=8, column=0, sticky=W)
        self.moduleImportsLabel = Label(moduleInfoFrame, wraplength=600, justify="left")
        self.moduleImportsLabel.grid(row=8, column=1, columnspan=3, sticky=W)
        self.moduleEnableButton = Button(moduleInfoFrame, text=self.ENABLE, state=DISABLED, command=self.moduleEnable)
        ToolTip(self.moduleEnableButton, text=_("Enable/disable plug in."), wraplength=240)
        self.moduleEnableButton.grid(row=9, column=1, sticky=E)
        self.moduleReloadButton = Button(moduleInfoFrame, text=_("Reload"), state=DISABLED, command=self.moduleReload)
        ToolTip(self.moduleReloadButton, text=_("Reload/update plug in."), wraplength=240)
        self.moduleReloadButton.grid(row=9, column=2, sticky=E)
        self.moduleRemoveButton = Button(moduleInfoFrame, text=_("Remove"), state=DISABLED, command=self.moduleRemove)
        ToolTip(self.moduleRemoveButton, text=_("Remove plug in from plug in table (does not erase the plug in's file)."), wraplength=240)
        self.moduleRemoveButton.grid(row=9, column=3, sticky=E)
        moduleInfoFrame.grid(row=2, column=0, columnspan=5, sticky=(N, S, E, W), padx=3, pady=3)
        moduleInfoFrame.config(borderwidth=4, relief="groove")

        okButton = Button(frame, text=_("Close"), command=self.ok)
        ToolTip(okButton, text=_("Accept and changes (if any) and close dialog."), wraplength=240)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        ToolTip(cancelButton, text=_("Cancel changes (if any) and close dialog."), wraplength=240)
        okButton.grid(row=3, column=3, sticky=(S,E), pady=3)
        cancelButton.grid(row=3, column=4, sticky=(S,E), pady=3, padx=3)

        enableDisableFrame = Frame(frame)
        enableDisableFrame.grid(row=3, column=1, sticky=(S,W), pady=3)
        enableAllButton = Button(enableDisableFrame, text=_("Enable All"), command=self.enableAll)
        ToolTip(enableAllButton, text=_("Enable all plug ins."), wraplength=240)
        disableAllButton = Button(enableDisableFrame, text=_("Disable All"), command=self.disableAll)
        ToolTip(disableAllButton, text=_("Disable all plug ins."), wraplength=240)
        enableAllButton.grid(row=1, column=1)
        disableAllButton.grid(row=1, column=2)

        self.loadTreeViews()

        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))
        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

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

        def loadSubtree(parentNode, moduleItems):
            for moduleItem in sorted(moduleItems, key=lambda item: item[0]):
                moduleInfo = moduleItem[1]
                if parentNode or not moduleInfo.get("isImported"):
                    nodeName = moduleItem[0]
                    if parentNode:
                        nodeName = parentNode + GROUPSEP + nodeName
                    name = moduleInfo.get("name", nodeName)
                    node = self.modulesView.insert(parentNode, "end", nodeName, text=name)
                    self.modulesView.set(node, "author", moduleInfo.get("author"))
                    self.modulesView.set(node, "ver", moduleInfo.get("version"))
                    self.modulesView.set(node, "status", moduleInfo.get("status"))
                    self.modulesView.set(node, "date", moduleInfo.get("fileDate"))
                    if name in self.modulesWithNewerFileDates:
                        self.modulesView.set(node, "update", _("available"))
                    self.modulesView.set(node, "descr", moduleInfo.get("description"))
                    self.modulesView.set(node, "license", moduleInfo.get("license"))
                    if moduleInfo.get("imports"):
                        loadSubtree(node, [(importModuleInfo["name"],importModuleInfo)
                                           for importModuleInfo in moduleInfo["imports"]])

        loadSubtree("", self.pluginConfig.get("modules", {}).items())

        # clear previous treeview entries
        for previousNode in self.classesView.get_children(""):
            self.classesView.delete(previousNode)

        for i, classItem in enumerate(sorted(self.pluginConfig.get("classes", {}).items())):
            className, moduleList = classItem
            node = self.classesView.insert("", "end", className, text=className)
            self.classesView.set(node, "modules", ', '.join(moduleList))

        self.moduleSelect()  # clear out prior selection

    def ok(self, event=None):
        # check for orphaned classes (for which there is no longer a corresponding module)
        _moduleNames = self.pluginConfig.get("modules", {}).keys()
        _orphanedClassNames = set()
        for className, moduleList in self.pluginConfig.get("classes", {}).items():
            for _moduleName in moduleList.copy():
                if _moduleName not in _moduleNames: # it's orphaned
                    moduleList.remove(_moduleName)
                    self.pluginConfigChanged = True
            if not moduleList: # now orphaned
                _orphanedClassNames.add(className)
                self.pluginConfigChanged = True
        for _orphanedClassName in _orphanedClassNames:
            del self.pluginConfig["classes"][_orphanedClassName]

        if self.pluginConfigChanged:
            PluginManager.pluginConfig = self.pluginConfig
            PluginManager.pluginConfigChanged = True
            PluginManager.reset()  # force reloading of modules
        if self.uiClassMethodsChanged or self.modelClassesChanged or self.customTransformsChanged or self.disclosureSystemTypesChanged or self.hostSystemFeaturesChanged:  # may require reloading UI
            affectedItems = ""
            if self.uiClassMethodsChanged:
                affectedItems += _("menus of the user interface")
            if self.modelClassesChanged:
                if affectedItems:
                    affectedItems += _(" and ")
                affectedItems += _("model objects of the processor")
            if self.customTransformsChanged:
                if affectedItems:
                    affectedItems += _(" and ")
                affectedItems += _("custom transforms")
            if self.disclosureSystemTypesChanged:
                if affectedItems:
                    affectedItems += _(" and ")
                affectedItems += _("disclosure system types")
            if self.hostSystemFeaturesChanged:
                if affectedItems:
                    affectedItems += _(" and ")
                affectedItems += _("host system features")
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
        if node:
            node = node.rpartition(GROUPSEP)[2] # drop leading path names for module name
        moduleInfo = self.pluginConfig.get("modules", {}).get(node)
        if moduleInfo:
            self.selectedModule = node
            name = moduleInfo["name"]
            self.moduleNameLabel.config(text=name)
            self.moduleAuthorHdr.config(state=ACTIVE)
            self.moduleAuthorLabel.config(text=moduleInfo.get("author"))
            self.moduleDescrHdr.config(state=ACTIVE)
            self.moduleDescrLabel.config(text=moduleInfo.get("description"))
            self.moduleClassesHdr.config(state=ACTIVE)
            self.moduleClassesLabel.config(text=', '.join(moduleInfo["classMethods"]))
            self.moduleVersionHdr.config(state=ACTIVE)
            self.moduleVersionLabel.config(text=moduleInfo.get("version"))
            self.moduleUrlHdr.config(state=ACTIVE)
            self.moduleUrlLabel.config(text=moduleInfo["moduleURL"])
            self.moduleDateHdr.config(state=ACTIVE)
            self.moduleDateLabel.config(text=moduleInfo["fileDate"] + " " +
                    (_("(an update is available)") if name in self.modulesWithNewerFileDates else ""))
            self.moduleLicenseHdr.config(state=ACTIVE)
            self.moduleLicenseLabel.config(text=moduleInfo.get("license"))
            if moduleInfo.get("imports"):
                self.moduleImportsHdr.config(state=ACTIVE)
                _text = ", ".join(mi["name"] for mi in moduleInfo["imports"][:3])
                if len(moduleInfo["imports"]) >= 3:
                    _text += ", ..."
                self.moduleImportsLabel.config(text=_text)
            _buttonState = DISABLED if moduleInfo.get("isImported") else ACTIVE
            self.moduleEnableButton.config(state=_buttonState,
                                           text={"enabled":self.DISABLE,
                                                 "disabled":self.ENABLE}[moduleInfo["status"]])
            self.moduleReloadButton.config(state=_buttonState)
            self.moduleRemoveButton.config(state=_buttonState)
        else:
            self.selectedModule = None
            self.moduleNameLabel.config(text="")
            self.moduleAuthorHdr.config(state=DISABLED)
            self.moduleAuthorLabel.config(text="")
            self.moduleDescrHdr.config(state=DISABLED)
            self.moduleDescrLabel.config(text="")
            self.moduleClassesHdr.config(state=DISABLED)
            self.moduleClassesLabel.config(text="")
            self.moduleVersionHdr.config(state=DISABLED)
            self.moduleVersionLabel.config(text="")
            self.moduleUrlHdr.config(state=DISABLED)
            self.moduleUrlLabel.config(text="")
            self.moduleDateHdr.config(state=DISABLED)
            self.moduleDateLabel.config(text="")
            self.moduleLicenseHdr.config(state=DISABLED)
            self.moduleLicenseLabel.config(text="")
            self.moduleImportsHdr.config(state=DISABLED)
            self.moduleImportsLabel.config(text="")
            self.moduleEnableButton.config(state=DISABLED, text=self.ENABLE)
            self.moduleReloadButton.config(state=DISABLED)
            self.moduleRemoveButton.config(state=DISABLED)

    @staticmethod
    def _choiceSortOrder(entryPointRef: EntryPointRef):
        moduleInfoMap = entryPointRef.moduleInfo
        key = moduleInfoMap["name"]
        group = {
            "ixbrl-viewer": "1",  # pip installed Arelle viewer
            "iXBRLViewerPlugin": "2",  # git clone installed Arelle viewer
            "Edgar Renderer": "3",
        }.get(key)
        if not group:
            if key.startswith("Validate"):
                group = "4"
            elif key.startswith("xbrlDB"):
                group = "5"
            else:
                group = "6"
        return group + key.lower()

    @staticmethod
    def _generateChoiceTuples(entryPointRefs: list[EntryPointRef]):
        """
        Generate list of choice tuples from list of entry point refs.
        :param entryPointRefs: List of entry point refs to convert to choice tuples.
        :return: List of choice tuples.
        """
        choiceTuples = []
        for entryPointRef in sorted(entryPointRefs, key=DialogPluginManager._choiceSortOrder):
            moduleInfo = entryPointRef.moduleInfo
            name = moduleInfo.get("name")
            path = moduleInfo.get("path")
            description = moduleInfo.get("description")
            version = moduleInfo.get("version")
            lic = moduleInfo.get("license")
            tooltip = "name: {}\ndescription: {}\nversion: {}\nlocation: {}\nlicense: {}".format(
                name, description, version, path, lic)
            choiceTuple = (name, tooltip, path, name, version, description, lic)
            choiceTuples.append(choiceTuple)
        return choiceTuples

    def selectLocally(self):
        entryPointRefs = EntryPointRef.discoverAll()
        choiceTuples = self._generateChoiceTuples(entryPointRefs)

        selectedPath = DialogOpenArchive.selectPlugin(self, choiceTuples)
        if selectedPath:
            if selectedPath.startswith(self.cntlr.pluginDir):
                selectedPath = selectedPath[len(self.cntlr.pluginDir)+1:]
            moduleInfo = PluginManager.moduleModuleInfo(moduleURL=selectedPath)
            self.loadFoundModuleInfo(moduleInfo, selectedPath)

    def browseLocally(self):
        initialdir = self.cntlr.pluginDir # default plugin directory
        if not self.cntlr.isMac: # can't navigate within app easily, always start in default directory
            initialdir = self.cntlr.config.setdefault("pluginOpenDir", initialdir)
        filename = self.cntlr.uiFileDialog("open",
                                           parent=self,
                                           title=_("Choose plug-in module file"),
                                           initialdir=initialdir,
                                           filetypes=[(_("Python files"), "*.py")],
                                           defaultextension=".py")
        if filename:
            # check if a package is selected (any file in a directory containing an __init__.py
            #if (os.path.basename(filename) == "__init__.py" and os.path.isdir(os.path.dirname(filename)) and
            #    os.path.isfile(filename)):
            #    filename = os.path.dirname(filename) # refer to the package instead
            self.cntlr.config["pluginOpenDir"] = os.path.dirname(filename)
            moduleInfo = PluginManager.moduleModuleInfo(moduleURL=filename)
            self.loadFoundModuleInfo(moduleInfo, filename)


    def findOnWeb(self):
        url = DialogURL.askURL(self)
        if url:  # url is the in-cache or local file
            moduleInfo = PluginManager.moduleModuleInfo(moduleURL=url)
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

    def checkIfImported(self, moduleInfo):
        if moduleInfo.get("isImported"):
            messagebox.showwarning(_("Plug-in is imported by a parent plug-in.  "),
                                   _("Plug-in has a parent, please request operation on the parent: \n\n{0}")
                                   .format(moduleInfo.get("name")),
                                   parent=self)
            return True
        return False

    def checkClassMethodsChanged(self, moduleInfo):
        for classMethod in moduleInfo["classMethods"]:
            if classMethod.startswith("CntlrWinMain.Menu"):
                self.uiClassMethodsChanged = True  # may require reloading UI
            elif classMethod == "ModelObjectFactory.ElementSubstitutionClasses":
                self.modelClassesChanged = True # model object factor classes changed
            elif classMethod == "ModelManager.LoadCustomTransforms":
                self.customTransformsChanged = True
            elif classMethod == "DisclosureSystem.Types":
                self.disclosureSystemTypesChanged = True # disclosure system types changed
            elif classMethod.startswith("Proxy."):
                self.hostSystemFeaturesChanged = True # system features (e.g., proxy) changed

    def removePluginConfigModuleInfo(self, name):
        moduleInfo = self.pluginConfig["modules"].get(name)
        if moduleInfo:
            if self.checkIfImported(moduleInfo):
                return;
            def _removePluginConfigModuleInfo(moduleInfo):
                _name = moduleInfo.get("name")
                if _name:
                    self.checkClassMethodsChanged(moduleInfo)
                    for classMethod in moduleInfo["classMethods"]:
                        classMethods = self.pluginConfig["classes"].get(classMethod)
                        if classMethods and _name in classMethods:
                            classMethods.remove(_name)
                            if not classMethods: # list has become unused
                                del self.pluginConfig["classes"][classMethod] # remove class
                    for importModuleInfo in moduleInfo.get("imports", EMPTYLIST):
                        _removePluginConfigModuleInfo(importModuleInfo)
                    self.pluginConfig["modules"].pop(_name, None)
            _removePluginConfigModuleInfo(moduleInfo)
            if not self.pluginConfig["modules"] and self.pluginConfig["classes"]:
                self.pluginConfig["classes"].clear() # clean orphan classes
            self.pluginConfigChanged = True

    def addPluginConfigModuleInfo(self, moduleInfo):
        if self.checkIfImported(moduleInfo):
            return;
        name = moduleInfo.get("name")
        self.removePluginConfigModuleInfo(name)  # remove any prior entry for this module
        def _addPlugin(moduleInfo):
            _name = moduleInfo.get("name")
            if _name:
                self.modulesWithNewerFileDates.discard(_name) # no longer has an update available
                self.pluginConfig["modules"][_name] = moduleInfo
                # add classes
                for classMethod in moduleInfo["classMethods"]:
                    classMethods = self.pluginConfig["classes"].setdefault(classMethod, [])
                    if name not in classMethods:
                        classMethods.append(_name)
                self.checkClassMethodsChanged(moduleInfo)
            for importModuleInfo in moduleInfo.get("imports", EMPTYLIST):
                _addPlugin(importModuleInfo)
        _addPlugin(moduleInfo)
        self.pluginConfigChanged = True

    def moduleEnable(self):
        if self.selectedModule in self.pluginConfig["modules"]:
            moduleInfo = self.pluginConfig["modules"][self.selectedModule]
            if self.checkIfImported(moduleInfo):
                return;
            def _moduleEnable(moduleInfo):
                if self.moduleEnableButton['text'] == self.ENABLE:
                    moduleInfo["status"] = "enabled"
                elif self.moduleEnableButton['text'] == self.DISABLE:
                    moduleInfo["status"] = "disabled"
                self.checkClassMethodsChanged(moduleInfo)
                for importModuleInfo in moduleInfo.get("imports", EMPTYLIST):
                    _moduleEnable(importModuleInfo) # set status on nested moduleInfo
                    if importModuleInfo['name'] in self.pluginConfig["modules"]: # set status on top level moduleInfo
                        _moduleEnable(self.pluginConfig["modules"][importModuleInfo['name']])
            _moduleEnable(moduleInfo)
            if self.moduleEnableButton['text'] == self.ENABLE:
                self.moduleEnableButton['text'] = self.DISABLE
            elif self.moduleEnableButton['text'] == self.DISABLE:
                self.moduleEnableButton['text'] = self.ENABLE
            self.pluginConfigChanged = True
            self.loadTreeViews()

    def moduleReload(self):
        if self.selectedModule in self.pluginConfig["modules"]:
            url = self.pluginConfig["modules"][self.selectedModule].get("moduleURL")
            if url:
                moduleInfo = PluginManager.moduleModuleInfo(moduleURL=url, reload=True)
                if moduleInfo:
                    if self.checkIfImported(moduleInfo):
                        return;
                    self.addPluginConfigModuleInfo(moduleInfo)
                    self.loadTreeViews()
                    self.cntlr.showStatus(_("{0} reloaded").format(moduleInfo["name"]), clearAfter=5000)
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

    def enableAll(self):
        self.enableDisableAll(True)

    def disableAll(self):
        self.enableDisableAll(False)

    def enableDisableAll(self, doEnable):
        for module in self.pluginConfig["modules"]:
            moduleInfo = self.pluginConfig["modules"][module]
            if not moduleInfo.get("isImported"):
                def _enableDisableAll(moduleInfo):
                    if doEnable:
                        moduleInfo["status"] = "enabled"
                    else:
                        moduleInfo["status"] = "disabled"
                    for importModuleInfo in moduleInfo.get("imports", EMPTYLIST):
                        _enableDisableAll(importModuleInfo)
                _enableDisableAll(moduleInfo)
                if doEnable:
                    self.moduleEnableButton['text'] = self.DISABLE
                else:
                    self.moduleEnableButton['text'] = self.ENABLE
        self.pluginConfigChanged = True
        self.loadTreeViews()
