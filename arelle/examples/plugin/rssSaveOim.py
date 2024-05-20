'''
Rss Save OIM is a plug-in to the RSS GUI menu that will load an RSS filing's
instances and save them as OIM files.

See COPYRIGHT.md for copyright information.

ViewWinRssFeed allows the GUI user to right-click on a filing.  This plugin
adds a menu item to save the filing as OIM Json files.

The identified filing is loaded in a separate thread (so the GUI is not blocked)
and each (of possibly multiple) instances are saved to OIM JSON files.

If there is only one instance it saves to the file name provided by the Save Dialog.
If there are multiple instances (such as a multi-IXDS inline filing), the additional
instances are saved under their base file name with replaced suffix json, in the
directory chosen by the Save Dialog.

This plug-in imports the following plug-ins:
  saveLoadableOIM to save the xBRL-JSON instances
  inlineXbrlDocumentSet for multi-doc or multi-IXDS filings
  validate/EFM for isolation of multi-IXDS filings into primary and supplemental modelXbrl objects
'''

import os
from arelle import ModelXbrl
from arelle.FileSource import openFileSource
from arelle.PluginManager import pluginClassMethods
from arelle.Version import authorLabel, copyrightLabel

def saveFilingOim(cntlr, zippedUrl, oimFile):
    # load filing
    modelXbrl = ModelXbrl.load(cntlr.modelManager,
                               openFileSource(zippedUrl, cntlr))
    if modelXbrl is not None:
        for saveLoadableOIM in pluginClassMethods("SaveLoadableOim.Save"):
            saveLoadableOIM(modelXbrl, oimFile)
            modelXbrl.info("arelle:savedOIM", _("Saved OIM File {}").format(oimFile))
        # check for supplemental instances
        if hasattr(modelXbrl, "supplementalModelXbrls"):
            oimFileDir = os.path.dirname(oimFile)
            for supplementalModelXbrl in modelXbrl.supplementalModelXbrls:
                # use basename for the json file
                supplementalOimFile = os.path.join(oimFileDir, os.path.splitext(supplementalModelXbrl.basename)[0] + ".json")
                for saveLoadableOIM in pluginClassMethods("SaveLoadableOim.Save"):
                    saveLoadableOIM(supplementalModelXbrl, supplementalOimFile)
                    modelXbrl.info("arelle:savedOIM",_("Saved OIM File {}").format(supplementalOimFile))
                supplementalModelXbrl.close()
        modelXbrl.close()


def rssFeedFilingMenuExtender(viewRssFeed, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Filing OIM",
                     underline=0,
                     command=lambda: saveFilingOimMenuCommand(viewRssFeed) )

def saveFilingOimMenuCommand(viewRssFeed):
    # save DTS menu item has been invoked
    cntlr = viewRssFeed.modelXbrl.modelManager.cntlr
    # get rssItemObj for the currently active row (if any)
    rssItemObj = viewRssFeed.modelXbrl.modelObject(viewRssFeed.menuRow)
    if rssItemObj is None:
        return
    # get file name into which to save log file while in foreground thread
    oimFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Filing OIM JSON file"),
            initialdir=cntlr.config.setdefault("loadableExcelFileDir","."),
            filetypes=[(_("JSON file .json"), "*.json")],
            defaultextension=".json")
    if not oimFile:
        return False
    import os
    cntlr.config["loadableOIMFileDir"] = os.path.dirname(oimFile)
    cntlr.saveConfig()

    import threading
    thread = threading.Thread(target=lambda
                                  _cntlr=cntlr,
                                  _zippedUrl=rssItemObj.zippedUrl,
                                  _oimFile=oimFile:
                                        saveFilingOim(_cntlr, _zippedUrl, _oimFile))
    thread.daemon = True
    thread.start()


__pluginInfo__ = {
    'name': 'Load RSS item and save OIM file',
    'version': '1.0',
    'description': "This plug-in saves an RSS-identified XBRL filing in OIM JSON files, for each instance of the filing.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('saveLoadableOIM', 'inlineXbrlDocumentSet', 'validate/EFM'), # import dependent modules
    # classes of mount points (required)
    'RssFeed.Menu.Filing': rssFeedFilingMenuExtender
}
