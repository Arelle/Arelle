from arelle import apf
from . import _
__author__ = 'Régis Décamps'

class SaveDtsMenu(apf.GUIMenu):
    ''' Menu item for the savedts plugin
    '''
    label = _("Package DTS in a zip")
    def execute(self):
        if self.modelManager is None or self.modelManager.modelXbrl is None:
            self.controller.addToLog(_("No taxonomy loaded"))
            return
        #self.modelManager.saveDTSpackage(allDTSes=True)
        packager=DTSPackager(self.modelManager.modelXbrl)
        packager.package()
        #self.modelManager.modelXbrl.packageDTS = package

class SaveDtsCli(apf.CommandLineOption):
    name="package-dts"
    action="store_true"
    dest="packageDTS"
    help=_("Package the DTS into a zip file")

    def execute(self):
        packager=DTSPackager(self.modelManager.modelXbrl)
        packager.package()

class DTSPackager(object):
    ''' The DTSPackager is the core of the savedts plugin.
    '''
    def __init__(self,modelXbrl):
        self.dts=modelXbrl

    def package(self):
        if self.dts.fileSource.isArchive:
            return
        import os
        import zipfile
        try:
            import zlib
            compression = zipfile.ZIP_DEFLATED
        except:
            compression = zipfile.ZIP_STORED
        entryFilename = self.dts.fileSource.url
        pkgFilename = entryFilename + ".zip"
        with zipfile.ZipFile(pkgFilename, 'w') as zip:
            numFiles = 0
            for fileUri in sorted(self.dts.urlDocs.keys()):
                if not (fileUri.startswith("http://") or fileUri.startswith("https://")):
                    numFiles += 1
                    # this has to be a relative path because the hrefs will break
                    zip.write(fileUri, os.path.basename(fileUri))
        self.dts.info("info",_("DTS of %(entryFile)s has %(numberOfFiles)s files packaged into %(packageOutputFile)s"),entryFile=entryFilename,numberOfFiles=numFiles,packageOutputFile=pkgFilename)

