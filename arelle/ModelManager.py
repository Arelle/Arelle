'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
import gc, sys, traceback, logging
from arelle import ModelXbrl, Validate, DisclosureSystem, PackageManager, ValidateXbrlCalcs, ValidateDuplicateFacts
from arelle.ModelFormulaObject import FormulaOptions
from arelle.PluginManager import pluginClassMethods
from arelle.typing import LocaleDict

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.ModelValue import QName

def initialize(cntlr: Cntlr) -> ModelManager:
    modelManager = ModelManager(cntlr)
    modelManager.modelXbrl = None
    return modelManager

class ModelManager:
    """ModelManager provides an interface between modelXbrl's and the controller.  Model manager is a
    singleton object, one is created in initialization of a controller.

    The ModelManager coordinates ModelXbrl instances for the Controller, and is the interface to utility
    functions (such as the Python web cache), and application specific formalisms (such as the SEC
    restrictions on referencable base taxonomies).

        .. attribute:: validateDisclosureSystem

        True if disclosure system is to be validated (e.g., EFM)

        .. attribute:: disclosureSystem

        Disclosure system object.  To select the disclosure system, e.g., 'gfm', moduleManager.disclosureSystem.select('gfm').

        .. attribute:: validateCalcs

        ValidateXbrlCalcs.ValidateCalcsMode

        .. attribute:: validateUTR

        True for validation of unit type registry

        .. attribute:: defaultLang

        The default language code for labels selection and views (e.g. 'en-US'), set from the operating system defaults on startup.
    """
    defaultLang: str
    formulaOptions: FormulaOptions
    locale: LocaleDict

    def __init__(self, cntlr: Cntlr):
        self.cntlr = cntlr
        self.validateDisclosureSystem = False
        self.disclosureSystem = DisclosureSystem.DisclosureSystem(self)
        self.validateCalcs = 0 # ValidateXbrlCalcs.ValidateCalcsMode
        self.validateInfoset = False
        self.validateUtr = False
        self.validateTestcaseSchema = True
        self.skipDTS = False
        self.skipLoading = None
        self.abortOnMajorError = False
        self.collectProfileStats = False
        self.loadedModelXbrls = []
        self.customTransforms: dict[QName, Callable[[str], str]] | None = None
        self.isLocaleSet = False
        self.validateDuplicateFacts = ValidateDuplicateFacts.DuplicateType.NONE
        self.setLocale()
        ValidateXbrlCalcs.init() # required due to circular dependencies in module

    def shutdown(self):
        self.status = "shutdown"

    def setLocale(self) -> str | None:
        from arelle import Locale
        self.locale, localeSetupMessage = Locale.getUserLocale(self.cntlr.uiLocale)
        self.defaultLang = Locale.getLanguageCode()
        self.isLocaleSet = True
        return localeSetupMessage

    def addToLog(self, message, messageCode="", file="", refs=[], level=logging.INFO) -> None:
        """Add a simple info message to the default logger

        :param message: Text of message to add to log.
        :type message: str
        :param messageCode: Message code (e.g., a prefix:id of a standard error)
        :param messageCode: str
        :param file: File name (and optional line numbers) pertaining to message
        :param refs: [{"href":file,"sourceLine":lineno},...] pertaining to message
        :type file: str
        """
        self.cntlr.addToLog(message, messageCode=messageCode, file=file, refs=refs, level=level)

    def showStatus(self, message: str | None, clearAfter: int | None = None) -> None:
        """Provide user feedback on status line of GUI or web page according to type of controller.

        :param message: Message to display on status widget.
        :param clearAfter: Time, in ms., after which to clear the message (e.g., 5000 for 5 sec.)
        """
        self.cntlr.showStatus(message, clearAfter)

    def viewModelObject(self, modelXbrl, objectId):
        """Notify any active views to show and highlight selected object.  Generally used
        to scroll list control to object and highlight it, or if tree control, to find the object
        and open tree branches as needed for visibility, scroll to and highlight the object.

        :param modelXbrl: ModelXbrl (DTS) whose views are to be notified
        :type modelXbrl: ModelXbrl
        :param objectId: Selected object id (string format corresponding to ModelObject.objectId() )
        :type objectId: str
        """
        self.cntlr.viewModelObject(modelXbrl, objectId)

    def reloadViews(self, modelXbrl: ModelXbrl) -> None:
        """Notify all active views to reload and redisplay their entire contents.  May be used
        when loaded model is changed significantly, or when individual object change notifications
        (by viewModelObject) would be difficult to identify or too numerous.

        :param modelXbrl: ModelXbrl (DTS) whose views are to be reloaded
        """
        self.cntlr.reloadViews(modelXbrl)

    def load(self, filesource, nextaction=None, taxonomyPackages=None, **kwargs):
        """Load an entry point modelDocument object(s), which in turn load documents they discover
        (for the case of instance, taxonomies, and versioning reports), but defer loading instances
        for test case and RSS feeds.

        The modelXbrl that is loaded is 'stacked', by this class, so that any modelXbrl operations such as validate,
        and close, operate on the most recently loaded modelXbrl, and compareDTSes operates on the two
        most recently loaded modelXbrl's.

        :param filesource: may be a FileSource object, with the entry point selected, or string file name (or web URL).
        :type filesource: FileSource or str
        :param nextAction: status line text string, if any, to show upon completion
        :type nextAction: str
        :param taxonomyPackages: array of URLs of taxonomy packages required for load operation
        """
        if taxonomyPackages:
            resetPackageMappings = False
            for pkgUrl in taxonomyPackages:
                if PackageManager.addPackage(self.cntlr, pkgUrl):
                    resetPackageMappings = True
            if resetPackageMappings:
                PackageManager.rebuildRemappings(self.cntlr)
        try:
            if filesource.url.startswith("urn:uuid:"): # request for an open modelXbrl
                for modelXbrl in self.loadedModelXbrls:
                    if not modelXbrl.isClosed and modelXbrl.uuid == filesource.url:
                        return modelXbrl
                raise IOError(_("Open file handle is not open: {0}").format(filesource.url))
        except AttributeError:
            pass # filesource may be a string, which has no url attribute
        self.filesource = filesource
        modelXbrl = None # loaded modelXbrl
        for customLoader in pluginClassMethods("ModelManager.Load"):
            modelXbrl = customLoader(self, filesource, **kwargs)
            if modelXbrl is not None:
                break # custom loader did the loading
        if modelXbrl is None:  # use default xbrl loader
            modelXbrl = ModelXbrl.load(self, filesource, nextaction, **kwargs)
        self.modelXbrl = modelXbrl
        self.loadedModelXbrls.append(self.modelXbrl)
        return self.modelXbrl

    def saveDTSpackage(self, allDTSes=False):
        if allDTSes:
            for modelXbrl in self.loadedModelXbrls:
                modelXbrl.saveDTSpackage()
        elif self.modelXbrl is not None:
            self.modelXbrl.saveDTSpackage()

    def create(self, newDocumentType=None, url=None, schemaRefs=None, createModelDocument=True, isEntry=False, errorCaptureLevel=None, initialXml=None, base=None) -> ModelXbrl:
        self.modelXbrl = ModelXbrl.create(self, newDocumentType=newDocumentType, url=url, schemaRefs=schemaRefs, createModelDocument=createModelDocument,
                                          isEntry=isEntry, errorCaptureLevel=errorCaptureLevel, initialXml=initialXml, base=base)
        self.loadedModelXbrls.append(self.modelXbrl)
        return self.modelXbrl

    def validate(self):
        """Validates the most recently loaded modelXbrl (according to validation properties).

        Results of validation will be in log.
        """
        try:
            if self.modelXbrl:
                Validate.validate(self.modelXbrl)
        except Exception as err:
            self.addToLog(_("[exception] Validation exception: {0} at {1}").format(
                           err,
                           traceback.format_tb(sys.exc_info()[2])))

    def compareDTSes(self, versReportFile, writeReportFile=True):
        """Compare two most recently loaded DTSes, saving versioning report in to the file name provided.

        :param versReportFile: file name in which to save XBRL Versioning Report
        :type versReportFile: str
        :param writeReportFile: False to prevent writing XBRL Versioning Report file
        :type writeReportFile: bool
        """
        from arelle.ModelVersReport import ModelVersReport
        if len(self.loadedModelXbrls) >= 2:
            fromDTS = self.loadedModelXbrls[-2]
            toDTS = self.loadedModelXbrls[-1]
            from arelle.ModelDocument import Type
            modelVersReport = self.create(newDocumentType=Type.VERSIONINGREPORT,
                                          url=versReportFile,
                                          createModelDocument=False)
            ModelVersReport(modelVersReport).diffDTSes(versReportFile, fromDTS, toDTS)
            return modelVersReport
        return None

    def close(self, modelXbrl=None):
        """Closes the specified or most recently loaded modelXbrl

        :param modelXbrl: Specific ModelXbrl to be closed (defaults to last opened ModelXbrl)
        :type modelXbrl: ModelXbrl
        """
        if modelXbrl is None: modelXbrl = self.modelXbrl
        if modelXbrl:
            while modelXbrl in self.loadedModelXbrls:
                self.loadedModelXbrls.remove(modelXbrl)
            if (modelXbrl == self.modelXbrl): # dereference modelXbrl from this instance
                if len(self.loadedModelXbrls) > 0:
                    self.modelXbrl = self.loadedModelXbrls[0]
                else:
                    self.modelXbrl = None
            modelXbrl.close()
            gc.collect()

    def loadCustomTransforms(self):
        if self.customTransforms is None:
            self.customTransforms = {}
            for pluginMethod in pluginClassMethods("ModelManager.LoadCustomTransforms"):
                pluginMethod(self.customTransforms)
