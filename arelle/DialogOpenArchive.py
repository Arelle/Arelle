'''
See COPYRIGHT.md for copyright information.
'''
from tkinter import Toplevel, StringVar, VERTICAL, HORIZONTAL, N, S, E, W, messagebox
try:
    from tkinter.ttk import Frame, Button, Treeview, Scrollbar
except ImportError:
    from ttk import Frame, Button, Treeview, Scrollbar
import os, sys
from collections import defaultdict
import regex as re
from arelle.Cntlr import Cntlr
from arelle.CntlrWinTooltip import ToolTip
from arelle.UrlUtil import isHttpUrl
from arelle.PackageManager import parsePackage
from arelle.PythonUtil import attrdict
from arelle import PluginManager

'''
caller checks accepted, if True, caller retrieves url
'''

ARCHIVE = 1
ENTRY_POINTS = 2
DISCLOSURE_SYSTEM = 3
PLUGIN = 4
PACKAGE = 5

reportIxdsPattern = re.compile(r"^([^/]+/reports/[^/]+)/[^/]+$")

def askArchiveFile(parent, filesource, multiselect=False):
    try:
        filenames = filesource.dir
        if filenames is not None:   # an IO or other error can return None
            if filesource.isTaxonomyPackage:
                dialog = DialogOpenArchive(parent,
                                           ENTRY_POINTS,
                                           filesource,
                                           filenames,
                                           _("Select Entry Point"),
                                           _("File"),
                                           showAltViewButton=True,
                                           multiselect=multiselect)
            else:
                dialog = DialogOpenArchive(parent,
                                           ARCHIVE,
                                           filesource,
                                           filenames,
                                           _("Select Archive File"),
                                           _("File"),
                                           multiselect=multiselect)
            if dialog.accepted:
                return filesource.url
    except Exception as e:
        err = _("Unable to open archive; the underlying error was: {0}").format(e)
        parent.addToLog(err)
        messagebox.showerror(_("Unable to open archive"), err)
    return None

def selectDisclosureSystem(parent, disclosureSystem):

    disclosureSystemSelections = disclosureSystem.dir

    # if no disclosure system to select, user may need to enable applicable plugin(s)
    if not disclosureSystemSelections and messagebox.askokcancel(
        _("Load disclosure systems"),
        _("Disclosure systems are provided by plug-ins, no applicable plug-in(s) have been enabled. \n\n"
          "Press OK to open the plug-in manager and select plug-in(s) (e.g., validate or EdgarRenderer).")):
        from arelle import DialogPluginManager
        DialogPluginManager.dialogPluginManager(parent)
        return None

    dialog = DialogOpenArchive(parent,
                               DISCLOSURE_SYSTEM,
                               disclosureSystem,
                               disclosureSystemSelections,
                               _("Select Disclosure System"),
                               _("Disclosure System"))
    if dialog and dialog.accepted:
        return disclosureSystem.selection
    return None

def selectPlugin(parent, pluginChoices):

    filesource = attrdict(isRss=False, url="Plug-ins", selection="") # emulates a filesource object for the selection return
    dialog = DialogOpenArchive(parent,
                               PLUGIN,
                               filesource,
                               pluginChoices,
                               _("File"),
                               _("Select Plug-in Module"))
    if dialog and dialog.accepted:
        return filesource.selection
    return None

def selectPackage(parent, packageChoices):

    filesource = attrdict(isRss=False, url="Packages", selection="") # emulates a filesource object for the selection return
    dialog = DialogOpenArchive(parent,
                               PACKAGE,
                               filesource,
                               packageChoices,
                               _("Name"),
                               _("Select Package"))
    if dialog and dialog.accepted:
        return filesource.selection
    return None


class DialogOpenArchive(Toplevel):
    def __init__(self, parent, openType, filesource, filenames, title, colHeader, showAltViewButton=False, multiselect=False):
        if isinstance(parent, Cntlr):
            cntlr = parent
            parent = parent.parent # parent is cntlrWinMain
        else: # parent is a Toplevel dialog
            cntlr = parent.cntlr
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
        self.treeView.config(selectmode="extended" if multiselect else "browse")
        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E,W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N,S))
        treeFrame.columnconfigure(0, weight=1)
        treeFrame.rowconfigure(0, weight=1)
        treeFrame.grid(row=0, column=0, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)
        self.treeView.focus_set()

        if openType not in (PLUGIN, PACKAGE):
            cntlr.showStatus(_("loading archive {0}").format(filesource.url))
        self.filesource = filesource
        self.filenames = filenames
        self.selection = filesource.selection
        self.hasToolTip = False
        self.multiselect = multiselect
        selectedNode = None

        if openType == ENTRY_POINTS:
            try:
                metadataFiles = filesource.taxonomyPackageMetadataFiles
                ''' take first for now
                if len(metadataFiles) != 1:
                    raise IOError(_("Taxonomy package contained more than one metadata file: {0}.")
                                  .format(', '.join(metadataFiles)))
                '''
                metadataFile = metadataFiles[0]
                metadata = filesource.url + os.sep + metadataFile
                self.metadataFilePrefix = os.sep.join(os.path.split(metadataFile)[:-1])
                if self.metadataFilePrefix:
                    self.metadataFilePrefix += "/"  # zip contents have /, never \ file seps
                self.taxonomyPkgMetaInf = '{}/META-INF/'.format(
                            os.path.splitext(os.path.basename(filesource.url))[0])


                self.taxonomyPackage = parsePackage(cntlr, filesource, metadata,
                                                    os.sep.join(os.path.split(metadata)[:-1]) + os.sep)


                if self.taxonomyPackage["entryPoints"]:
                    # may have instance documents too
                    self.packageContainedInstances = []
                    self.packageContainedIXDSes = defaultdict(list)
                    packageContentInstanceCounts = {}
                    packageContentTypeCounts = {}
                    for suffix in (".xhtml", ".htm", ".html", ".xbrl"): # try for suffixes in order of likelihood to have instance
                        for potentialInstance in filesource.dir:
                            if potentialInstance.endswith(suffix):
                                m = reportIxdsPattern.match(potentialInstance) # IXDS
                                if multiselect and m: # only in ixds multiselect mode
                                    _type = "Inline Doc Set"
                                    self.packageContainedIXDSes[m.group(1)].append(potentialInstance)
                                    potentialInstance = m.group(1) # use package name only
                                elif suffix == ".xbrl":
                                    _type = "xBRL-XML Instance"
                                else:
                                    _type = "Inline Instance"
                                if not self.packageContainedInstances or self.packageContainedInstances[-1][0] != potentialInstance:
                                    self.packageContainedInstances.append([potentialInstance, _type])
                                    packageContentInstanceCounts[potentialInstance] = packageContentInstanceCounts.get(potentialInstance, 0) + 1
                                    packageContentTypeCounts[_type] = packageContentTypeCounts.get(_type, 0) + 1
                        if self.packageContainedInstances:
                            break
                    if self.packageContainedInstances: # add sequences to any duplicated entry types
                        for _type, count in packageContentTypeCounts.items():
                            if count > 1:
                                _dupNo = 0
                                for i in range(len(self.packageContainedInstances)):
                                    if self.packageContainedInstances[i][1] == _type:
                                        _dupNo += 1
                                        self.packageContainedInstances[i][1] = "{} {}".format(_type, _dupNo)
                        for _instance, count in packageContentInstanceCounts.items():
                            if count > 1:
                                _dupNo = 0
                                for i in range(len(self.packageContainedInstances)):
                                    if self.packageContainedInstances[i][0] == _instance:
                                        _dupNo += 1
                                        self.packageContainedInstances[i][0] = "{} {}".format(_instance, _dupNo)

                else:
                    # may be a catalog file with no entry oint names
                    openType = ARCHIVE  # no entry points to show, just archive
                    self.showAltViewButton = False
            except Exception as e:
                self.close()
                err = _("Failed to parse metadata; the underlying error was: {0}").format(e)
                messagebox.showerror(_("Malformed taxonomy package"), err)
                cntlr.addToLog(err)
                return

        if openType not in (PLUGIN, PACKAGE):
            cntlr.showStatus(None)

        if openType in (DISCLOSURE_SYSTEM, PLUGIN, PACKAGE):
            y = 3
        else:
            y = 1

        okButton = Button(frame, text=_("OK"), command=self.ok)
        cancelButton = Button(frame, text=_("Cancel"), command=self.close)
        okButton.grid(row=y, column=2, sticky=(S,E,W), pady=3)
        cancelButton.grid(row=y, column=3, sticky=(S,E,W), pady=3, padx=3)

        if self.showAltViewButton:
            self.altViewButton = Button(frame, command=self.showAltView)
            self.altViewButton.grid(row=y, column=0, sticky=(S,W), pady=3, padx=3)

        self.loadTreeView(openType, colHeader, title)

        self.geometry("+{0}+{1}".format(dialogX+50,dialogY+100))
        frame.grid(row=0, column=0, sticky=(N,S,E,W))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

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
        if openType in (ARCHIVE, DISCLOSURE_SYSTEM, PLUGIN, PACKAGE):
            if openType in (PLUGIN, PACKAGE): width = 770
            else: width = 500
            self.treeView.column("#0", width=width, anchor="w")
            self.treeView.heading("#0", text=colHeader)
            self.isRss = getattr(self.filesource, "isRss", False)
            if self.isRss:
                self.treeView.column("#0", width=350, anchor="w")
                self.treeView["columns"] = ("descr", "date", "instDoc")
                self.treeView.column("descr", width=50, anchor="center", stretch=False)
                self.treeView.heading("descr", text="Form")
                self.treeView.column("date", width=170, anchor="w", stretch=False)
                self.treeView.heading("date", text="Pub Date")
                self.treeView.column("instDoc", width=200, anchor="w", stretch=False)
                self.treeView.heading("instDoc", text="Instance Document")
            elif openType == PLUGIN:
                self.treeView.column("#0", width=150, anchor="w")
                self.treeView["columns"] = ("name", "vers", "descr", "license")
                self.treeView.column("name", width=150, anchor="w", stretch=False)
                self.treeView.heading("name", text="Name")
                self.treeView.column("vers", width=60, anchor="w", stretch=False)
                self.treeView.heading("vers", text="Version")
                self.treeView.column("descr", width=300, anchor="w", stretch=False)
                self.treeView.heading("descr", text="Description")
                self.treeView.column("license", width=60, anchor="w", stretch=False)
                self.treeView.heading("license", text="License")
            elif openType == PACKAGE:
                self.treeView.column("#0", width=200, anchor="w")
                self.treeView["columns"] = ("vers", "descr", "license")
                self.treeView.column("vers", width=100, anchor="w", stretch=False)
                self.treeView.heading("vers", text="Version")
                self.treeView.column("descr", width=400, anchor="w", stretch=False)
                self.treeView.heading("descr", text="Description")
                self.treeView.column("license", width=70, anchor="w", stretch=False)
                self.treeView.heading("license", text="License")
            else:
                self.treeView["columns"] = tuple()

            loadedPaths = []
            for i, filename in enumerate(self.filenames):
                if isinstance(filename,tuple):
                    if self.isRss:
                        form, date, instDoc = filename[2:5]
                    elif openType == PLUGIN:
                        name, vers, descr, license = filename[3:7]
                    elif openType == PACKAGE:
                        vers, descr, license = filename[3:6]
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
                elif openType == PLUGIN:
                    self.treeView.set(node, "name", name)
                    self.treeView.set(node, "vers", vers)
                    self.treeView.set(node, "descr", descr)
                    self.treeView.set(node, "license", license)
                elif openType == PACKAGE:
                    self.treeView.set(node, "vers", vers)
                    self.treeView.set(node, "descr", descr)
                    self.treeView.set(node, "license", license)
                if self.selection == filename:
                    selectedNode = node
                loadedPaths.append(path)

        elif openType == ENTRY_POINTS:
            self.treeView.column("#0", width=200, anchor="w")
            self.treeView.heading("#0", text="Name")

            self.treeView["columns"] = ("url",)
            self.treeView.column("url", width=300, anchor="w")
            self.treeView.heading("url", text="URL")

            for fileType, fileUrl in getattr(self, "packageContainedInstances", ()):
                self.treeView.insert("", "end", fileUrl,
                                     values=fileType,
                                     text=fileUrl or urls[0][2])
            for name, urls in sorted(self.taxonomyPackage["entryPoints"].items(), key=lambda i:i[0][2]):
                self.treeView.insert("", "end", name,
                                     values="\n".join(url[1] for url in urls),
                                     text=name or urls[0][2])

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
            filename = None
            if self.openType in (ARCHIVE, DISCLOSURE_SYSTEM):
                if self.multiselect:
                    filenames = []
                for _selection in selection:
                    filename = self.filenames[int(_selection[4:])]
                    if isinstance(filename,tuple):
                        if self.isRss:
                            filename = filename[4]
                        else:
                            filename = filename[0]
                    if self.multiselect:
                        filenames.append(filename)
                    else:
                        break
                if self.multiselect and filenames:
                    self.filesource.select(filenames) # array of file names
                    self.accepted = True
                    self.close()
            elif self.openType == ENTRY_POINTS:
                epName = selection[0]
                #index 0 is the remapped Url, as opposed to the canonical one used for display
                # Greg Acsone reports [0] does not work for Corep 1.6 pkgs, need [1], old style packages
                filenames = []
                for _url, _type in self.packageContainedInstances: # check if selection was an inline instance
                    if _type in selection:
                        if _url in self.packageContainedIXDSes: # taxonomy package
                            filenames.extend(self.packageContainedIXDSes[_url])
                        else: # single instance
                            filenames.append(_url)
                if not filenames: # else if it's a named taxonomy entry point of an installed package
                    for url in self.taxonomyPackage["entryPoints"][epName]:
                        filename = url[1] # use unmapped file name
                        if not filename.endswith("/"):
                            # check if it's an absolute URL rather than a path into the archive
                            if not isHttpUrl(filename) and self.metadataFilePrefix != self.taxonomyPkgMetaInf:
                                # assume it's a path inside the archive:
                                filename = self.metadataFilePrefix + filename
                        filenames.append(filename)
                if filenames:
                    self.filesource.select(filenames)
                    self.accepted = True
                    self.close()
                return
            elif self.openType in (PLUGIN, PACKAGE):
                filename = self.filenames[int(selection[0][4:])][2]
            if filename is not None and not self.multiselect and not filename.endswith("/"):
                if hasattr(self, "taxonomyPackage"):
                    # attempt to unmap the filename to original file
                    # will be mapped again in loading, but this allows schemaLocation to be unmapped
                    for prefix, remapping in self.taxonomyPackage["remappings"].items():
                        if isHttpUrl(remapping):
                            remapStart = remapping
                        else:
                            remapStart = self.metadataFilePrefix + remapping
                        if filename.startswith(remapStart):
                            # set unmmapped file
                            filename = prefix + filename[len(remapStart):]
                            break
                        if (self.metadataFilePrefix.endswith("/META-INF/") and isHttpUrl(prefix) and
                            filename.startswith(self.metadataFilePrefix[:-10]) and
                            filename.startswith(remapping[len(self.filesource.url)+1:])):
                            # recover unmapped file name for chosen in-archive relative file
                            filename = prefix + filename[len(remapping) - len(self.filesource.url) - 1:]
                if self.openType in (PLUGIN, PACKAGE):
                    self.filesource.selection = filename
                else:
                    self.filesource.select(filename)
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
            if self.openType in (ARCHIVE, DISCLOSURE_SYSTEM, PLUGIN, PACKAGE):
                self.toolTipRowId = tvRowId
                if tvRowId and len(tvRowId) > 4:
                    try:
                        text = self.filenames[ int(tvRowId[4:]) ]
                        if isinstance(text, tuple):
                            text = (text[1] or "").replace("\\n","\n")
                    except (KeyError, ValueError):
                        pass
            elif self.openType == ENTRY_POINTS:
                try:
                    text = "{0}\n{1}".format(tvRowId,
                             "\n".join(url[1] for url in self.taxonomyPackage["entryPoints"][tvRowId]))
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
