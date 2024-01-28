'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import simpledialog, Toplevel, font, messagebox, VERTICAL, HORIZONTAL, N, S, E, W
from tkinter.constants import DISABLED, ACTIVE
try:
    from tkinter.ttk import Treeview, Scrollbar, Frame, Label, Button
except ImportError:
    from ttk import Treeview, Scrollbar, Frame, Label, Button
from arelle import PackageManager, DialogURL, DialogOpenArchive
from arelle.CntlrWinTooltip import ToolTip
import os, time, json, sys, traceback
import regex as re

STANDARD_PACKAGES_URL = "https://taxonomies.xbrl.org/api/v0/taxonomy"

def dialogPackageManager(mainWin):
    # check for updates in background
    import threading
    thread = threading.Thread(target=lambda cntlr=mainWin: backgroundCheckForUpdates(cntlr))
    thread.daemon = True
    thread.start()

def backgroundCheckForUpdates(cntlr):
    cntlr.showStatus(_("Checking for updates to packages")) # clear web loading status
    packageNamesWithNewerFileDates = PackageManager.packageNamesWithNewerFileDates()
    if packageNamesWithNewerFileDates:
        cntlr.showStatus(_("Updates are available for these packages: {0}")
                              .format(', '.join(packageNamesWithNewerFileDates)), clearAfter=5000)
    else:
        cntlr.showStatus(_("No updates found for packages."), clearAfter=5000)
    time.sleep(0.1) # Mac locks up without this, may be needed for empty ui queue?
    cntlr.uiThreadQueue.put((DialogPackageManager, [cntlr, packageNamesWithNewerFileDates]))

class DialogPackageManager(Toplevel):
    def __init__(self, mainWin, packageNamesWithNewerFileDates):
        super(DialogPackageManager, self).__init__(mainWin.parent)

        self.ENABLE = _("Enable")
        self.DISABLE = _("Disable")
        self.parent = mainWin.parent
        self.cntlr = mainWin
        self.webCache = mainWin.webCache

        # copy plugins for temporary display
        self.packagesConfig = PackageManager.packagesConfig
        self.packagesConfigChanged = False
        self.packageNamesWithNewerFileDates = packageNamesWithNewerFileDates

        parentGeometry = re.match(r"(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", self.parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))

        self.title(_("Taxonomy Packages Manager"))
        frame = Frame(self)

        # left button frame
        buttonFrame = Frame(frame, width=40)
        buttonFrame.columnconfigure(0, weight=1)
        addLabel = Label(buttonFrame, text=_("Find taxonomy packages:"), wraplength=64, justify="center")
        if not self.webCache.workOffline:
            addSelectFromRegistryButton = Button(buttonFrame, text=_("Select"), command=self.selectFromRegistry)
            ToolTip(addSelectFromRegistryButton, text=_("Select package from the XBRL Package Registry."), wraplength=240)
        addLocalButton = Button(buttonFrame, text=_("Locally"), command=self.findLocally)
        ToolTip(addLocalButton, text=_("File chooser allows selecting taxonomy packages to add (or reload), from the local file system.  "
                                       "Select either a PWD or prior taxonomy package zip file, or a taxonomy manifest (.taxonomyPackage.xml) within an unzipped taxonomy package.  "), wraplength=360)
        addWebButton = Button(buttonFrame, text=_("On Web"), command=self.findOnWeb)
        ToolTip(addWebButton, text=_("Dialog to enter URL full path to load (or reload) package, from the web or local file system.  "
                                     "URL may be either a PWD or prior taxonomy package zip file, or a taxonomy manifest (.taxonomyPackage.xml) within an unzipped taxonomy package.  "), wraplength=360)
        manifestNameButton = Button(buttonFrame, text=_("Manifest"), command=self.manifestName)
        ToolTip(manifestNameButton, text=_("Provide pre-PWD non-standard archive manifest file name pattern (e.g., *taxonomyPackage.xml).  "
                                           "Uses unix file name pattern matching.  "
                                           "Multiple manifest files are supported in pre-PWD archives (such as oasis catalogs).  "
                                           "(Replaces pre-PWD search for either .taxonomyPackage.xml or catalog.xml).  "), wraplength=480)
        self.manifestNamePattern = ""
        addLabel.grid(row=0, column=0, pady=4)
        selBtnRow = 1
        if not self.webCache.workOffline:
            addSelectFromRegistryButton.grid(row=selBtnRow, column=0, pady=4)
            selBtnRow += 1
        addLocalButton.grid(row=selBtnRow, column=0, pady=4)
        selBtnRow += 1
        addWebButton.grid(row=selBtnRow, column=0, pady=4)
        selBtnRow += 1
        manifestNameButton.grid(row=selBtnRow, column=0, pady=4)
        selBtnRow += 1
        buttonFrame.grid(row=0, column=0, rowspan=3, sticky=(N, S, W), padx=3, pady=3)

        # right tree frame (packages already known to arelle)
        packagesFrame = Frame(frame, width=700)
        vScrollbar = Scrollbar(packagesFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(packagesFrame, orient=HORIZONTAL)
        self.packagesView = Treeview(packagesFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set, height=7)
        self.packagesView.grid(row=0, column=0, sticky=(N, S, E, W))
        self.packagesView.bind('<<TreeviewSelect>>', self.packageSelect)
        hScrollbar["command"] = self.packagesView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.packagesView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        packagesFrame.columnconfigure(0, weight=1)
        packagesFrame.rowconfigure(0, weight=1)
        packagesFrame.grid(row=0, column=1, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.packagesView.focus_set()

        self.packagesView.column("#0", width=190, anchor="w")
        self.packagesView.heading("#0", text=_("Name"))
        self.packagesView["columns"] = ("ver", "status", "date", "update", "descr")
        self.packagesView.column("ver", width=80, anchor="w", stretch=False)
        self.packagesView.heading("ver", text=_("Version"))
        self.packagesView.column("status", width=50, anchor="w", stretch=False)
        self.packagesView.heading("status", text=_("Status"))
        self.packagesView.column("date", width=170, anchor="w", stretch=False)
        self.packagesView.heading("date", text=_("File Date"))
        self.packagesView.column("update", width=50, anchor="w", stretch=False)
        self.packagesView.heading("update", text=_("Update"))
        self.packagesView.column("descr", width=200, anchor="w", stretch=False)
        self.packagesView.heading("descr", text=_("Description"))

        remappingsFrame = Frame(frame)
        vScrollbar = Scrollbar(remappingsFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(remappingsFrame, orient=HORIZONTAL)
        self.remappingsView = Treeview(remappingsFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set, height=5)
        self.remappingsView.grid(row=0, column=0, sticky=(N, S, E, W))
        hScrollbar["command"] = self.remappingsView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.remappingsView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        remappingsFrame.columnconfigure(0, weight=1)
        remappingsFrame.rowconfigure(0, weight=1)
        remappingsFrame.grid(row=1, column=1, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.remappingsView.focus_set()

        self.remappingsView.column("#0", width=200, anchor="w")
        self.remappingsView.heading("#0", text=_("Prefix"))
        self.remappingsView["columns"] = ("remapping")
        self.remappingsView.column("remapping", width=500, anchor="w", stretch=False)
        self.remappingsView.heading("remapping", text=_("Remapping"))

        # bottom frame package info details
        packageInfoFrame = Frame(frame, width=700)
        packageInfoFrame.columnconfigure(1, weight=1)

        self.packageNameLabel = Label(packageInfoFrame, wraplength=600, justify="left",
                                      font=font.Font(family='Helvetica', size=12, weight='bold'))
        self.packageNameLabel.grid(row=0, column=0, columnspan=6, sticky=W)
        self.packageVersionHdr = Label(packageInfoFrame, text=_("version:"), state=DISABLED)
        self.packageVersionHdr.grid(row=1, column=0, sticky=W)
        self.packageVersionLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packageVersionLabel.grid(row=1, column=1, columnspan=5, sticky=W)
        self.packageLicenseHdr = Label(packageInfoFrame, text=_("license:"), state=DISABLED)
        self.packageLicenseHdr.grid(row=2, column=0, sticky=W)
        self.packageLicenseLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packageLicenseLabel.grid(row=2, column=1, columnspan=5, sticky=W)
        self.packageDescrHdr = Label(packageInfoFrame, text=_("description:"), state=DISABLED)
        self.packageDescrHdr.grid(row=3, column=0, sticky=W)
        self.packageDescrLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packageDescrLabel.grid(row=3, column=1, columnspan=5, sticky=W)
        self.packagePrefixesHdr = Label(packageInfoFrame, text=_("prefixes:"), state=DISABLED)
        self.packagePrefixesHdr.grid(row=4, column=0, sticky=W)
        self.packagePrefixesLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packagePrefixesLabel.grid(row=4, column=1, columnspan=5, sticky=W)
        ToolTip(self.packagePrefixesLabel, text=_("List of prefixes that this package remaps."), wraplength=240)
        self.packageUrlHdr = Label(packageInfoFrame, text=_("URL:"), state=DISABLED)
        self.packageUrlHdr.grid(row=5, column=0, sticky=W)
        self.packageUrlLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packageUrlLabel.grid(row=5, column=1, columnspan=5, sticky=W)
        ToolTip(self.packageUrlLabel, text=_("URL of taxonomy package (local file path or web loaded file)."), wraplength=240)
        self.packageDateHdr = Label(packageInfoFrame, text=_("date:"), state=DISABLED)
        self.packageDateHdr.grid(row=6, column=0, sticky=W)
        self.packageDateLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.packageDateLabel.grid(row=6, column=1, columnspan=5, sticky=W)
        ToolTip(self.packageDateLabel, text=_("Filesystem date of currently loaded package file (with parenthetical node when an update is available)."), wraplength=240)
        self.publisherHdr = Label(packageInfoFrame, text=_("publisher:"), state=DISABLED)
        self.publisherHdr.grid(row=7, column=0, sticky=W)
        self.publisherLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.publisherLabel.grid(row=7, column=1, columnspan=5, sticky=W)
        ToolTip(self.publisherLabel, text=_("Publisher of currently loaded package file."), wraplength=240)
        self.publicationDateHdr = Label(packageInfoFrame, text=_("publication date:"), state=DISABLED)
        self.publicationDateHdr.grid(row=8, column=0, sticky=W)
        self.publicationDateLabel = Label(packageInfoFrame, wraplength=600, justify="left")
        self.publicationDateLabel.grid(row=8, column=1, columnspan=5, sticky=W)
        ToolTip(self.publicationDateLabel, text=_("Publication date"), wraplength=240)
        self.packageEnableButton = Button(packageInfoFrame, text=self.ENABLE, state=DISABLED, command=self.packageEnable)
        ToolTip(self.packageEnableButton, text=_("Enable/disable package."), wraplength=240)
        self.packageEnableButton.grid(row=9, column=1, sticky=E)
        self.packageMoveUpButton = Button(packageInfoFrame, text=_("Move Up"), state=DISABLED, command=self.packageMoveUp)
        ToolTip(self.packageMoveUpButton, text=_("Move package up (above other remappings)."), wraplength=240)
        self.packageMoveUpButton.grid(row=9, column=2, sticky=E)
        self.packageMoveDownButton = Button(packageInfoFrame, text=_("Move Down"), state=DISABLED, command=self.packageMoveDown)
        ToolTip(self.packageMoveDownButton, text=_("Move package down (below other remappings)."), wraplength=240)
        self.packageMoveDownButton.grid(row=9, column=3, sticky=E)
        self.packageReloadButton = Button(packageInfoFrame, text=_("Reload"), state=DISABLED, command=self.packageReload)
        ToolTip(self.packageReloadButton, text=_("Reload/update package."), wraplength=240)
        self.packageReloadButton.grid(row=9, column=4, sticky=E)
        self.packageRemoveButton = Button(packageInfoFrame, text=_("Remove"), state=DISABLED, command=self.packageRemove)
        ToolTip(self.packageRemoveButton, text=_("Remove package from packages table (does not erase the package file)."), wraplength=240)
        self.packageRemoveButton.grid(row=9, column=5, sticky=E)
        packageInfoFrame.grid(row=2, column=0, columnspan=5, sticky=(N, S, E, W), padx=3, pady=3)
        packageInfoFrame.config(borderwidth=4, relief="groove")

        okButton = Button(frame, text=_("Close"), command=self.ok)
        ToolTip(okButton, text=_("Accept and changes (if any) and close dialog."), wraplength=240)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        ToolTip(cancelButton, text=_("Cancel changes (if any) and close dialog."), wraplength=240)
        okButton.grid(row=3, column=3, sticky=(S,E), pady=3)
        cancelButton.grid(row=3, column=4, sticky=(S,E), pady=3, padx=3)

        enableDisableFrame = Frame(frame)
        enableDisableFrame.grid(row=3, column=1, sticky=(S,W), pady=3)
        enableAllButton = Button(enableDisableFrame, text=_("Enable All"), command=self.enableAll)
        ToolTip(enableAllButton, text=_("Enable all packages."), wraplength=240)
        disableAllButton = Button(enableDisableFrame, text=_("Disable All"), command=self.disableAll)
        ToolTip(disableAllButton, text=_("Disable all packages."), wraplength=240)
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
        for previousNode in self.packagesView.get_children(""):
            self.packagesView.delete(previousNode)

        for i, packageInfo in enumerate(self.packagesConfig.get("packages", [])):
            name = packageInfo.get("name", "package{}".format(i))
            node = self.packagesView.insert("", "end", "_{}".format(i), text=name)
            self.packagesView.set(node, "ver", packageInfo.get("version"))
            self.packagesView.set(node, "status", packageInfo.get("status"))
            self.packagesView.set(node, "date", packageInfo.get("fileDate"))
            if name in self.packageNamesWithNewerFileDates:
                self.packagesView.set(node, "update", _("available"))
            self.packagesView.set(node, "descr", packageInfo.get("description"))

        # clear previous treeview entries
        for previousNode in self.remappingsView.get_children(""):
            self.remappingsView.delete(previousNode)

        for i, remappingItem in enumerate(sorted(self.packagesConfig.get("remappings", {}).items())):
            prefix, remapping = remappingItem
            node = self.remappingsView.insert("", "end", prefix, text=prefix)
            self.remappingsView.set(node, "remapping", remapping)

        self.packageSelect()  # clear out prior selection

    def ok(self, event=None):
        if self.packagesConfigChanged:
            PackageManager.packagesConfig = self.packagesConfig
            PackageManager.packagesConfigChanged = True
            self.cntlr.onPackageEnablementChanged()
        self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()

    def packageSelect(self, *args):
        node = (self.packagesView.selection() or (None,))[0]
        try:
            nodeIndex = int(node[1:])
        except (ValueError, TypeError):
            nodeIndex = -1
        if 0 <= nodeIndex < len(self.packagesConfig["packages"]):
            packageInfo = self.packagesConfig["packages"][nodeIndex]
            self.selectedPackageIndex = nodeIndex
            name = packageInfo["name"]
            self.packageNameLabel.config(text=name)
            self.packageVersionHdr.config(state=ACTIVE)
            self.packageVersionLabel.config(text=packageInfo["version"])
            self.packageLicenseHdr.config(state=ACTIVE)
            self.packageLicenseLabel.config(text=packageInfo.get("license"))
            self.packageDescrHdr.config(state=ACTIVE)
            self.packageDescrLabel.config(text=packageInfo["description"])
            self.packagePrefixesHdr.config(state=ACTIVE)
            self.packagePrefixesLabel.config(text=', '.join(packageInfo["remappings"].keys()))
            self.packageUrlHdr.config(state=ACTIVE)
            self.packageUrlLabel.config(text=packageInfo["URL"])
            self.packageDateHdr.config(state=ACTIVE)
            self.packageDateLabel.config(text=packageInfo["fileDate"] + " " +
                    (_("(an update is available)") if name in self.packageNamesWithNewerFileDates else ""))
            self.publisherHdr.config(state=ACTIVE)
            _publisher = ''
            if packageInfo.get("publisher"):
                _publisher += packageInfo["publisher"]
            if packageInfo.get("publisherCountry"):
                _publisher += ", " + packageInfo["publisherCountry"]
            if packageInfo.get("publisherURL"):
                _publisher += ". " + packageInfo["publisherURL"]
            self.publisherLabel.config(text=_publisher)
            self.publicationDateHdr.config(state=ACTIVE)
            self.publicationDateLabel.config(text=packageInfo.get("publicationDate",''))
            self.packageEnableButton.config(state=ACTIVE,
                                           text={"enabled":self.DISABLE,
                                                 "disabled":self.ENABLE}[packageInfo["status"]])
            self.packageMoveUpButton.config(state=ACTIVE if 0 < nodeIndex else DISABLED)
            self.packageMoveDownButton.config(state=ACTIVE if nodeIndex < (len(self.packagesConfig["packages"]) - 1) else DISABLED)
            self.packageReloadButton.config(state=ACTIVE)
            self.packageRemoveButton.config(state=ACTIVE)
        else:
            self.selectedPackageIndex = -1
            self.packageNameLabel.config(text="")
            self.packageVersionHdr.config(state=DISABLED)
            self.packageVersionLabel.config(text="")
            self.packageLicenseHdr.config(state=DISABLED)
            self.packageLicenseLabel.config(text="")
            self.packageDescrHdr.config(state=DISABLED)
            self.packageDescrLabel.config(text="")
            self.packagePrefixesHdr.config(state=DISABLED)
            self.packagePrefixesLabel.config(text="")
            self.packageUrlHdr.config(state=DISABLED)
            self.packageUrlLabel.config(text="")
            self.packageDateHdr.config(state=DISABLED)
            self.packageDateLabel.config(text="")
            self.publisherHdr.config(state=DISABLED)
            self.publisherLabel.config(text="")
            self.publicationDateHdr.config(state=DISABLED)
            self.publicationDateLabel.config(text="")

            self.packageEnableButton.config(state=DISABLED, text=self.ENABLE)
            self.packageMoveUpButton.config(state=DISABLED)
            self.packageMoveDownButton.config(state=DISABLED)
            self.packageReloadButton.config(state=DISABLED)
            self.packageRemoveButton.config(state=DISABLED)


    def selectFromRegistry(self):
        choices = [] # list of tuple of (file name, description)
        uiLang = (self.cntlr.config.get("userInterfaceLangOverride") or self.cntlr.modelManager.defaultLang or "en")[:2]
        def langLabel(labels):
            if not labels:
                return ""
            for _lang in uiLang, "en":
                for label in labels:
                    if label["Language"].startswith(_lang):
                         return label["Label"]
            for label in labels:
                 return label["Label"]
            return ""
        try:
            with open(self.webCache.getfilename(STANDARD_PACKAGES_URL, reload=True), 'r', errors='replace') as fh:
                regPkgs = json.load(fh) # always reload
            for pkgTxmy in regPkgs.get("taxonomies", []):
                _name = langLabel(pkgTxmy["Name"])
                _description = langLabel(pkgTxmy.get("Description"))
                _version = pkgTxmy.get("Version")
                _license = pkgTxmy.get("License",{}).get("Name")
                _url = pkgTxmy.get("Links",{}).get("AuthoritativeURL")
                choices.append((_name,
                                "name: {}\ndescription: {}\nversion: {}\nlicense: {}".format(
                                        _name, _description, _version, _license),
                                _url,  _version, _description, _license))
            self.loadPackageUrl(DialogOpenArchive.selectPackage(self, choices))
        except (TypeError) as err:
            messagebox.showwarning(_("Unable to retrieve standard packages.  "),
                                   _("Standard packages URL is not accessible, please check if online:\n\n{0}.")
                                   .format(STANDARD_PACKAGES_URL),
                                   parent=self)


    def findLocally(self):
        initialdir = self.cntlr.pluginDir # default plugin directory
        #if not self.cntlr.isMac: # can't navigate within app easily, always start in default directory
        initialdir = self.cntlr.config.setdefault("packageOpenDir", initialdir)
        filename = self.cntlr.uiFileDialog("open",
                                           parent=self,
                                           title=_("Choose taxonomy package file"),
                                           initialdir=initialdir,
                                           filetypes=[(_("Taxonomy package files (*.zip)"), "*.zip"),
                                                      (_("PWD Manifest (taxonomyPackage.xml)"), "taxonomyPackage.xml"),
                                                      (_("pre-PWD Manifest (*.taxonomyPackage.xml)"), "*.taxonomyPackage.xml"),
                                                      (_("pre-PWD Oasis Catalog (*catalog.xml)"), "*catalog.xml")],
                                           defaultextension=".zip")
        if filename:
            # check if a package is selected (any file in a directory containing an __init__.py
            self.cntlr.config["packageOpenDir"] = os.path.dirname(filename)
            packageInfo = PackageManager.packageInfo(self.cntlr, filename, packageManifestName=self.manifestNamePattern)
            self.loadFoundPackageInfo(packageInfo, filename)


    def findOnWeb(self):
        self.loadPackageUrl(DialogURL.askURL(self))

    def loadPackageUrl(self, url):
        if url:  # url is the in-cache or local file
            packageInfo = PackageManager.packageInfo(self.cntlr, url, packageManifestName=self.manifestNamePattern)
            self.cntlr.showStatus("") # clear web loading status
            self.loadFoundPackageInfo(packageInfo, url)

    def manifestName(self):
        self.manifestNamePattern = simpledialog.askstring(_("Archive manifest file name pattern"),
                                                          _("Provide non-standard archive manifest file name pattern (e.g., *taxonomyPackage.xml).  \n"
                                                            "Uses unix file name pattern matching.  \n"
                                                            "Multiple manifest files are supported in archive (such as oasis catalogs).  \n"
                                                            "(If blank, search for either .taxonomyPackage.xml or catalog.xml).  "),
                                                          initialvalue=self.manifestNamePattern,
                                                          parent=self)

    def loadFoundPackageInfo(self, packageInfo, url):
        if packageInfo and packageInfo.get("name"):
            self.addPackageInfo(packageInfo)
            self.loadTreeViews()
        else:
            messagebox.showwarning(_("Package is not itself a taxonomy package.  "),
                                   _("File does not itself contain a manifest file: \n\n{0}\n\n  "
                                     "If opening an archive file, the manifest file search pattern currently is \"\", please press \"Manifest\" to change manifest file name pattern, e.g.,, \"*.taxonomyPackage.xml\", if needed.  ")
                                   .format(url),
                                   parent=self)

    def removePackageInfo(self, name, version):
        # find package entry
        packagesList = self.packagesConfig["packages"]
        j = -1
        for i, packageInfo in enumerate(packagesList):
            if packageInfo['name'] == name and packageInfo['version'] == version:
                j = i
                break
        if 0 <= j < len(packagesList):
            del self.packagesConfig["packages"][i]
            self.packagesConfigChanged = True

    def addPackageInfo(self, packageInfo):
        name = packageInfo["name"]
        version = packageInfo["version"]
        self.removePackageInfo(name, version)  # remove any prior entry for this package
        self.packageNamesWithNewerFileDates.discard(name) # no longer has an update available
        self.packagesConfig["packages"].append(packageInfo)
        PackageManager.rebuildRemappings(self.cntlr)
        self.packagesConfigChanged = True

    def packageEnable(self):
        if 0 <= self.selectedPackageIndex < len(self.packagesConfig["packages"]):
            packageInfo = self.packagesConfig["packages"][self.selectedPackageIndex]
            if self.packageEnableButton['text'] == self.ENABLE:
                packageInfo["status"] = "enabled"
                self.packageEnableButton['text'] = self.DISABLE
            elif self.packageEnableButton['text'] == self.DISABLE:
                packageInfo["status"] = "disabled"
                self.packageEnableButton['text'] = self.ENABLE
            self.packagesConfigChanged = True
            PackageManager.rebuildRemappings(self.cntlr)
            self.loadTreeViews()

    def packageMoveUp(self):
        if 1 <= self.selectedPackageIndex < len(self.packagesConfig["packages"]):
            packages = self.packagesConfig["packages"]
            packageInfo = packages[self.selectedPackageIndex]
            del packages[self.selectedPackageIndex]
            packages.insert(self.selectedPackageIndex -1, packageInfo)
            self.packagesConfigChanged = True
            PackageManager.rebuildRemappings(self.cntlr)
            self.loadTreeViews()

    def packageMoveDown(self):
        if 0 <= self.selectedPackageIndex < len(self.packagesConfig["packages"]) - 1:
            packages = self.packagesConfig["packages"]
            packageInfo = packages[self.selectedPackageIndex]
            del packages[self.selectedPackageIndex]
            packages.insert(self.selectedPackageIndex + 1, packageInfo)
            self.packagesConfigChanged = True
            PackageManager.rebuildRemappings(self.cntlr)
            self.loadTreeViews()

    def packageReload(self):
        if 0 <= self.selectedPackageIndex < len(self.packagesConfig["packages"]):
            packageInfo = self.packagesConfig["packages"][self.selectedPackageIndex]
            url = packageInfo.get("URL")
            if url:
                packageInfo = PackageManager.packageInfo(self.cntlr, url, reload=True, packageManifestName=packageInfo.get("manifestName"))
                if packageInfo:
                    self.addPackageInfo(packageInfo)
                    PackageManager.rebuildRemappings(self.cntlr)
                    self.loadTreeViews()
                    self.cntlr.showStatus(_("{0} reloaded").format(packageInfo.get("name")), clearAfter=5000)
                else:
                    messagebox.showwarning(_("Package error"),
                                           _("File or package cannot be reloaded: \n\n{0}")
                                           .format(url),
                                           parent=self)

    def packageRemove(self):
        if 0 <= self.selectedPackageIndex < len(self.packagesConfig["packages"]):
            packageInfo = self.packagesConfig["packages"][self.selectedPackageIndex]
            self.removePackageInfo(packageInfo["name"], packageInfo["version"])
            self.packagesConfigChanged = True
            PackageManager.rebuildRemappings(self.cntlr)
            self.loadTreeViews()

    def enableAll(self):
        self.enableDisableAll(True)

    def disableAll(self):
        self.enableDisableAll(False)

    def enableDisableAll(self, doEnable):
        for iPkg in range(len(self.packagesConfig["packages"])):
            packageInfo = self.packagesConfig["packages"][iPkg]
            if doEnable:
                packageInfo["status"] = "enabled"
                self.packageEnableButton['text'] = self.DISABLE
            else:
                packageInfo["status"] = "disabled"
                self.packageEnableButton['text'] = self.ENABLE
        self.packagesConfigChanged = True
        PackageManager.rebuildRemappings(self.cntlr)
        self.loadTreeViews()
