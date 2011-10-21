'''
Open Taxonomy Package Dialog: Reads the metadata and prompts the user to pick an entry point.
'''
from tkinter import *
from tkinter.ttk import *
import re, os
from arelle.CntlrWinTooltip import ToolTip

TAXONOMY_PACKAGE_FILE_NAME = '.taxonomyPackage.xml'


ARCHIVE = 1
DISCLOSURE_SYSTEM = 2

def askForEntryPoint(mainWin, filesource):
    filenames = filesource.dir
    if filenames is not None:   # an IO or other error can return None
        dialog = DialogOpenTaxonomyPackage(mainWin,
                                   ARCHIVE,
                                   filesource,
                                   filenames,
                                   _("Select Entry Point"))
        if dialog.accepted:
            if dialog.webUrl:
                return dialog.webUrl
            else:
                return filesource.url
    return None


class DialogOpenTaxonomyPackage(Toplevel):
    def __init__(self, mainWin, openType, filesource, filenames, title):
        parent = mainWin.parent
        super().__init__(parent)
        self.parent = parent
        parentGeometry = re.match("(\d+)x(\d+)[+]?([-]?\d+)[+]?([-]?\d+)", parent.geometry())
        dialogX = int(parentGeometry.group(3))
        dialogY = int(parentGeometry.group(4))
        self.accepted = False
        self.webUrl = None

        self.transient(self.parent)
        self.title(title)

        frame = Frame(self)

        treeFrame = Frame(frame, width=500)
        vScrollbar = Scrollbar(treeFrame, orient=VERTICAL)
        hScrollbar = Scrollbar(treeFrame, orient=HORIZONTAL)
        self.treeView = Treeview(treeFrame, xscrollcommand=hScrollbar.set, yscrollcommand=vScrollbar.set, columns=2)
        self.treeView.grid(row=0, column=0, sticky=(N, S, E, W))

        hScrollbar["command"] = self.treeView.xview
        hScrollbar.grid(row=1, column=0, sticky=(E, W))
        vScrollbar["command"] = self.treeView.yview
        vScrollbar.grid(row=0, column=1, sticky=(N, S))

        treeFrame.columnconfigure(0, weight=1)

        treeFrame.rowconfigure(0, weight=1)
        treeFrame.grid(row=0, column=0, columnspan=4, sticky=(N, S, E, W), padx=3, pady=3)

        self.treeView.focus_set()

        # set up treeView widget and tabbed pane
        self.treeView.column("#0", width=150, anchor="w")
        self.treeView.heading("#0", text="Name")

        self.treeView.column("#1", width=350, anchor="w")
        self.treeView.heading("#1", text="URL")

        mainWin.showStatus(_("loading archive {0}").format(filesource.url))
        self.filesource = filesource
        self.filenames = filenames
        selectedNode = None

        metadata = filesource.file(filesource.url + os.sep + TAXONOMY_PACKAGE_FILE_NAME)[0]

        try:
            self.nameToUrls = parseTxmyPkg(mainWin, metadata)
        except Exception as e:
            self.close()
            err = _("Failed to parse metadata; the underlying error was: {0}").format(e)
            messagebox.showerror(_("Malformed taxonomy package"), err)
            mainWin.addToLog(err)
            return

        for name, urls in self.nameToUrls.items():
            displayUrl = urls[1] # display the canonical URL
            self.treeView.insert("", "end", name, values=[displayUrl], text=name)

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
        okButton.grid(row=y, column=2, sticky=(S, E, W), pady=3)
        cancelButton.grid(row=y, column=3, sticky=(S, E, W), pady=3, padx=3)

        frame.grid(row=0, column=0, sticky=(N, S, E, W))
        frame.columnconfigure(0, weight=1)
        window = self.winfo_toplevel()
        window.columnconfigure(0, weight=1)
        self.geometry("+{0}+{1}".format(dialogX + 50, dialogY + 100))

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.close)

        self.toolTipText = StringVar()
        self.treeView.bind("<Motion>", self.motion, '+')
        self.treeView.bind("<Leave>", self.leave, '+')
        self.toolTipText = StringVar()
        self.toolTip = ToolTip(self.treeView,
                               textvariable=self.toolTipText,
                               wraplength=640,
                               follow_mouse=True,
                               state="disabled")
        self.toolTipEpName = None

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window(self)

    def ok(self, event=None):
        selection = self.treeView.selection()
        if len(selection) > 0:
            epName = selection[0]
            #index 0 is the remapped Url, as opposed to the canonical one used for display
            urlOrFile = self.nameToUrls[epName][0]

            if not urlOrFile.endswith("/"):
                # check if it's an absolute URL rather than a path into the archive
                if urlOrFile.startswith("http://") or urlOrFile.startswith("https://"):
                    self.webUrl = urlOrFile
                else:
                    # assume it's a path inside the archive:
                    self.filesource.select(urlOrFile)
                self.accepted = True
                self.close()

    def close(self, event=None):
        self.parent.focus_set()
        self.destroy()

    def leave(self, *args):
        self.toolTipRowId = None

    def motion(self, *args):
        epName = self.treeView.identify_row(args[0].y)
        if epName != self.toolTipEpName:
            self.toolTipEpName = epName
            try:
                epUrl = self.nameToUrls[epName][1]
            except KeyError:
                epUrl = None
            self.toolTip._hide()
            if epName and epUrl:
                self.toolTipText.set("{0}\n{1}".format(epName, epUrl))
                self.toolTip.configure(state="normal")
                self.toolTip._schedule()
            else:
                self.toolTipText.set("")
                self.toolTip.configure(state="disabled")

from lxml import etree
from urllib.parse import urljoin
from arelle import Locale

def parseTxmyPkg(mainWin, metadataFile):
    unNamedCounter = 1
    currentLang = Locale.getLanguageCode()

    tree = etree.parse(metadataFile)

    remappings = dict((m.get("prefix"),m.get("replaceWith"))
                      for m in tree.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}remapping"))

    result = {}

    for entryPointSpec in tree.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}entryPoint"):
        name = None
        
        # find closest match name node given xml:lang match to current language or no xml:lang
        for nameNode in entryPointSpec.iter(tag="{http://www.corefiling.com/xbrl/taxonomypackage/v1}name"):
            xmlLang = nameNode.get('{http://www.w3.org/XML/1998/namespace}lang')
            if name is None or not xmlLang or currentLang == xmlLang:
                name = nameNode.text
                if currentLang == xmlLang: # most prefer one with the current locale's language
                    break

        if not name:
            name = _("<unnamed {0}>").format(unNamedCounter)
            unNamedCounter += 1

        epDocCount = 0
        for epDoc in entryPointSpec.iterchildren("{http://www.corefiling.com/xbrl/taxonomypackage/v1}entryPointDocument"):
            if epDocCount:
                mainWin.addToLog(_("WARNING: skipping multiple-document entry point (not supported)"))
                continue
            epDocCount += 1
            epUrl = epDoc.get('href')
            base = epDoc.get('{http://www.w3.org/XML/1998/namespace}base') # cope with xml:base
            if base:
                resolvedUrl = urljoin(base, epUrl)
            else:
                resolvedUrl = epUrl
    
            #perform prefix remappings
            remappedUrl = resolvedUrl
            for prefix, replace in remappings.items():
                remappedUrl = resolvedUrl.replace(prefix, replace, 1)
            result[name] = (remappedUrl, resolvedUrl)

    return result
