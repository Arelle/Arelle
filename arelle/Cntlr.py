# -*- coding: utf-8 -*-
"""
:mod:`arelle.cntlr`
~~~~~~~~~~~~~~~~~~~

.. py:module:: arelle.cntlr
   :copyright: See COPYRIGHT.md for copyright information.
   :license: Apache-2.
   :synopsis: Common controller class to initialize for platform and setup common logger functions
"""
from __future__ import annotations

import gettext
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Any, TYPE_CHECKING, cast

import regex as re

from arelle import Locale, ModelManager, PackageManager, PluginManager, XbrlConst
from arelle.BetaFeatures import BETA_FEATURES_AND_DESCRIPTIONS
from arelle.ErrorManager import ErrorManager
from arelle.FileSource import FileSource
from arelle.SystemInfo import PlatformOS, getSystemWordSize, hasFileSystem, hasWebServer, isCGI, isGAE
from arelle.WebCache import WebCache
from arelle.logging.formatters.LogFormatter import LogFormatter, logRefsFileLines  # noqa: F401 - for reimport
from arelle.logging.handlers.LogHandlerWithXml import LogHandlerWithXml  # noqa: F401 - for reimport
from arelle.logging.handlers.LogToBufferHandler import LogToBufferHandler
from arelle.logging.handlers.LogToPrintHandler import LogToPrintHandler
from arelle.logging.handlers.LogToXmlHandler import LogToXmlHandler
from arelle.logging.handlers.StructuredMessageLogHandler import StructuredMessageLogHandler
from arelle.typing import TypeGetText
from arelle.utils.PluginData import PluginData

_: TypeGetText

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl

osPrcs: Any = None
LOG_TEXT_MAX_LENGTH = 32767
cxFrozen = getattr(sys, 'frozen', False)


def resourcesDir() -> str:
    if cxFrozen: # Check if frozen by cx_Freeze
        _resourcesDir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(_resourcesDir,"images")):
            return _resourcesDir
        if sys.platform == "darwin" and _resourcesDir.endswith("/MacOS") and os.path.exists(_resourcesDir[:-6] + "/Resources/images"):
            return _resourcesDir[:-6] + "/Resources"
    _moduleDir = os.path.dirname(__file__)
    if not os.path.isabs(_moduleDir):
        _moduleDir = os.path.abspath(_moduleDir)
    # for python 3.2 remove __pycache__
    if _moduleDir.endswith("__pycache__"):
        _moduleDir = os.path.dirname(_moduleDir)
    if (re.match(r".*[\\/](library|python{0.major}{0.minor}).zip[\\/]arelle$".format(sys.version_info),
                   _moduleDir)): # cx_Freexe uses library up to 3.4 and python35 after 3.5
        _resourcesDir = os.path.dirname(os.path.dirname(_moduleDir))
    else:
        _resourcesDir = _moduleDir
    if not os.path.exists(os.path.join(_resourcesDir,"images")) and \
       os.path.exists(os.path.join(os.path.dirname(_resourcesDir),"images")):
        _resourcesDir = os.path.dirname(_resourcesDir)
    return _resourcesDir


class Cntlr:
    """
    Initialization sets up for platform

    - Platform directories for application, configuration, locale, and cache
    - Context menu click event (TKinter)
    - Clipboard presence
    - Update URL
    - Reloads prior config user preferences (saved in json file)
    - Sets up proxy and web cache
    - Sets up logging

    A controller subclass object is instantiated, CntlrWinMain for the GUI and CntlrCmdLine for command
    line batch operation.  (Other controller modules and/or objects may be subordinate to a CntlrCmdLine,
    such as CntlrWebMain, and CntlrQuickBooks).

    This controller base class initialization sets up specifics such as directory paths,
    for its environment (Mac, Windows, or Unix), sets up a web file cache, and retrieves a
    configuration dictionary of prior user choices (such as window arrangement, validation choices,
    and proxy settings).

    The controller sub-classes (such as CntlrWinMain, CntlrCmdLine, and CntlrWebMain) most likely will
    load an XBRL related object, such as an XBRL instance, taxonomy,
    testcase file, versioning report, or RSS feed, by requesting the model manager to load and
    return a reference to its modelXbrl object.  The modelXbrl object loads the entry modelDocument
    object(s), which in turn load documents they discover (for the case of instance, taxonomies, and
    versioning reports), but defer loading instances for test case and RSS feeds.  The model manager
    may be requested to validate the modelXbrl object, or views may be requested as below.
    (Validating a testcase or RSS feed will validate the test case variations or RSS feed items, one by one.)

        .. attribute:: isMac
        True if system is MacOS

        .. attribute:: isMSW
        True if system is Microsoft Windows

        .. attribute:: userAppDir
        Full pathname to application directory (for persistent json files, cache, etc).

        .. attribute:: configDir
        Full pathname to config directory as installed (validation options, redirection URLs, common xsds).

        .. attribute:: imagesDir
        Full pathname to images directory as installed (images for GUI and web server).

        .. attribute:: localeDir
        Full pathname to locale directory as installed (for support of gettext localization feature).

        .. attribute:: hasClipboard
        True if a system platform clipboard is implemented on current platform

    """
    __version__ = "1.6.0"
    betaFeatures: dict[str, bool]
    errorManager: ErrorManager | None
    hasWin32gui: bool
    hasGui: bool
    hasFileSystem: bool
    isGAE: bool
    isCGI: bool
    systemWordSize: int
    uiLang: str
    configDir: str
    imagesDir: str
    localeDir: str
    pluginDir: str
    userAppDir: str
    isMac: bool
    isMSW: bool
    hasClipboard: bool
    contextMenuClick: str
    hasWebServer: bool
    config: dict[str, Any] | None
    configJsonFile: str
    webCache: WebCache
    modelManager: ModelManager.ModelManager
    logger: logging.Logger | None
    logHandler: logging.Handler

    def __init__(
        self,
        hasGui: bool = False,
        logFileName: str | None = None,
        logFileMode: str | None = None,
        logFileEncoding: str | None = None,
        logFormat: str | None = None,
        uiLang: str | None = None,
        disable_persistent_config: bool = False,
        betaFeatures: dict[str, bool] | None = None
    ) -> None:
        if betaFeatures is None:
            betaFeatures = {}
        self.betaFeatures = {
            b: betaFeatures.get(b, False)
            for b in BETA_FEATURES_AND_DESCRIPTIONS.keys()
        }
        self.errorManager = None
        self.hasWin32gui = False
        self.hasGui = hasGui
        self.hasFileSystem = hasFileSystem() # no file system on Google App Engine servers
        self.isGAE = isGAE()
        self.isCGI = isCGI()
        platformOS = PlatformOS.getPlatformOS()
        self.isMac = platformOS == PlatformOS.MACOS
        self.isMSW = platformOS == PlatformOS.WINDOWS
        self.systemWordSize = getSystemWordSize()  # e.g., 32 or 64
        self._uiLocale: str | None = None
        self.disablePersistentConfig = disable_persistent_config

        # sys.setrecursionlimit(10000) # 1000 default exceeded in some inline documents

        _resourcesDir = resourcesDir()
        self.configDir = os.path.join(_resourcesDir, "config")
        self.imagesDir = os.path.join(_resourcesDir, "images")
        self.localeDir = os.path.join(_resourcesDir, "locale")
        self.pluginDir = os.path.join(_resourcesDir, "plugin")
        self.__pluginData: dict[str, PluginData] = {}
        if cxFrozen:
            # some cx_freeze versions set this variable, which is incompatible with matplotlib after v3.1
            os.environ.pop("MATPLOTLIBDATA", None)
        configHomeDir = None  # look for path configDir/CONFIG_HOME in argv and environment parameters
        for i, arg in enumerate(sys.argv):  # check if config specified in a argv
            if arg.startswith("--xdgConfigHome="):
                configHomeDir = arg[16:]
                break
            elif arg == "--xdgConfigHome" and i + 1 < len(sys.argv):
                configHomeDir = sys.argv[i + 1]
                break
        if not configHomeDir: # not in argv, may be an environment parameter
            configHomeDir = os.getenv('XDG_CONFIG_HOME')
        if not configHomeDir:  # look for path configDir/CONFIG_HOME
            configHomeDirFile = os.path.join(self.configDir, "XDG_CONFIG_HOME")
            if os.path.exists(configHomeDirFile):
                try:
                    with io.open(configHomeDirFile, 'rt', encoding='utf-8') as f:
                        configHomeDir = f.read().strip()
                    if configHomeDir and not os.path.isabs(configHomeDir):
                        configHomeDir = os.path.abspath(configHomeDir)  # make into a full path if relative
                except EnvironmentError:
                    configHomeDir = None
        if self.hasFileSystem and configHomeDir and os.path.exists(configHomeDir):
            # check if a cache exists in this directory (e.g. from XPE or other tool)
            impliedAppDir = os.path.join(configHomeDir, "arelle")
            if os.path.exists(impliedAppDir):
                self.userAppDir = impliedAppDir
            elif os.path.exists(os.path.join(configHomeDir, "cache")):
                self.userAppDir = configHomeDir # use the XDG_CONFIG_HOME because cache is already a subdirectory
            else:
                self.userAppDir = impliedAppDir
        if self.isMac:
            if self.hasFileSystem and not configHomeDir:
                self.userAppDir = os.path.expanduser("~") + "/Library/Application Support/Arelle"
            # note that cache is in ~/Library/Caches/Arelle
            self.contextMenuClick = "<Button-2>"
            self.hasClipboard = hasGui  # clipboard always only if Gui (not command line mode)
        elif self.isMSW:
            if self.hasFileSystem and not configHomeDir:
                tempDir = tempfile.gettempdir()
                if tempDir.lower().endswith('local\\temp'):
                    impliedAppDir = tempDir[:-10] + 'local'
                else:
                    impliedAppDir = tempDir
                self.userAppDir = os.path.join( impliedAppDir, "Arelle")
            if hasGui:
                try:
                    import win32clipboard
                    self.hasClipboard = True
                except ImportError:
                    self.hasClipboard = False
                try:
                    import win32gui
                    self.hasWin32gui = True # active state for open file dialogs
                except ImportError:
                    pass
            else:
                self.hasClipboard = False
            self.contextMenuClick = "<Button-3>"
        else:  # Unix/Linux
            if self.hasFileSystem and not configHomeDir:
                    self.userAppDir = os.path.join( os.path.expanduser("~/.config"), "arelle")
            if hasGui:
                try:
                    import gtk
                    self.hasClipboard = True
                except ImportError:
                    self.hasClipboard = False
            else:
                self.hasClipboard = False
            self.contextMenuClick = "<Button-3>"
        self.hasWebServer = hasWebServer()
        # assert that app dir must exist
        self.config = None
        if self.hasFileSystem and not self.disablePersistentConfig:
            os.makedirs(self.userAppDir, exist_ok=True)
            # load config if it exists
            self.configJsonFile = self.userAppDir + os.sep + "config.json"
            if os.path.exists(self.configJsonFile):
                try:
                    with io.open(self.configJsonFile, 'rt', encoding='utf-8') as f:
                        self.config = json.load(f)
                except Exception as ex:
                    self.config = None # restart with a new config
        if not self.config:
            self.config = {
                'fileHistory': [],
                'windowGeometry': "{0}x{1}+{2}+{3}".format(800, 500, 200, 100),
            }

        # start language translation for domain
        self.setUiLanguage(uiLang or self.config.get("userInterfaceLangOverride",None), fallbackToDefault=True)
        Locale.setDisableRTL(self.config.get('disableRtl', False))

        self.webCache = WebCache(self, self.config.get("proxySettings"))

        # start plug in server (requres web cache initialized, but not logger)
        PluginManager.init(self, loadPluginConfig=hasGui)

        # requires plug ins initialized
        self.modelManager = ModelManager.initialize(self)

        # start taxonomy package server (requres web cache initialized, but not logger)
        PackageManager.init(self, loadPackagesConfig=hasGui)

        self.startLogging(logFileName, logFileMode, logFileEncoding, logFormat)
        self.errorManager = ErrorManager(self.modelManager, logging._checkLevel("INCONSISTENCY")) # type: ignore[attr-defined]

    def error(self, codes: Any, msg: str, level: str = "ERROR", fileSource: FileSource | None = None, **args: Any) -> None:
        if self.logger is None or self.errorManager is None:
            self.addToLog(
                message=msg,
                messageCode=str(codes),
                messageArgs=args,
                level=level
            )
            return
        self.errorManager.log(
            self.logger,
            level,
            codes,
            msg,
            fileSource=fileSource,
            logRefObjectProperties=getattr(self.logger, "logRefObjectProperties", False),
            **args
        )

    @property
    def errors(self) -> list[str | None]:
        if self.errorManager is None:
            return []
        return self.errorManager.errors

    @property
    def uiLangDir(self) -> str:
        return 'rtl' if getattr(self, 'uiLang', '')[0:2].lower() in {"ar", "he"} else 'ltr'

    @property
    def uiLocale(self) -> str | None:
        return self._uiLocale

    @uiLocale.setter
    def uiLocale(self, uiLocale: str | None) -> None:
        self._uiLocale = Locale.findCompatibleLocale(uiLocale)

    def postLoggingInit(self, localeSetupMessage: str | None = None) -> None:
        if not self.modelManager.isLocaleSet:
            localeSetupMessage = self.modelManager.setLocale() # set locale after logger started
        if localeSetupMessage:
            Cntlr.addToLog(self, localeSetupMessage, messageCode="arelle:uiLocale", level=logging.WARNING)

        # Cntlr.Init after logging started
        for pluginMethod in PluginManager.pluginClassMethods("Cntlr.Init"):
            pluginMethod(self)

    def setUiLanguage(self, locale: str | None, fallbackToDefault: bool = False) -> None:
        langCodes = Locale.getLanguageCodes(locale)
        try:
            gettext.translation("arelle", self.localeDir, langCodes).install()
            self.uiLang = langCodes[0]
        except OSError:
            if fallbackToDefault and not locale:
                locale = langCodes[0]
            isEnglishLocale = locale and locale.lower().startswith('en')
            if fallbackToDefault or isEnglishLocale:
                self.uiLang = cast(str, locale) if isEnglishLocale else XbrlConst.defaultLocale
                gettext.install("arelle", self.localeDir)
        self.uiLocale = locale or getattr(self, "uiLang", None)

    def startLogging(
        self,
        logFileName: str | None = None,
        logFileMode: str | None = None,
        logFileEncoding:str | None = None,
        logFormat: str | None = None,
        logLevel: str | None = None,
        logFilters: list[logging.Filter] | None = None,
        logHandler: logging.Handler | None = None,
        logToBuffer: bool = False,
        logTextMaxLength: int | None = None,
        logRefObjectProperties: bool = True,
        logXmlMaxAttributeLength: int | None = None,
        logPropagate: bool | None = None,
    ) -> None:
        if logFilters is None:
            logFilters = []
        # add additional logging levels (for python 2.7, all of these are ints)
        logging.addLevelName(logging.INFO - 1, "INFO-RESULT") # result data, has @name, @value, optional href to source and readable message
        logging.addLevelName(logging.INFO + 1, "INFO-SEMANTIC")
        logging.addLevelName(logging.WARNING + 1, "WARNING-SEMANTIC")
        logging.addLevelName(logging.WARNING + 2, "ASSERTION-SATISFIED")
        logging.addLevelName(logging.WARNING + 3, "INCONSISTENCY")
        logging.addLevelName(logging.ERROR - 2, "ERROR-SEMANTIC")
        logging.addLevelName(logging.ERROR - 1, "ASSERTION-NOT-SATISFIED")

        if logHandler is not None:
            self.logger = logging.getLogger("arelle")
            self.logHandler = logHandler
            self.logger.addHandler(logHandler)
        elif logFileName: # use default logging
            self.logger = logging.getLogger("arelle")
            if logFileName in ("logToPrint", "logToStdErr") and not logToBuffer:
                self.logHandler = LogToPrintHandler(logFileName)
            elif logFileName == "logToBuffer":
                self.logHandler = LogToBufferHandler()
                setattr(self.logger, "logRefObjectProperties", logRefObjectProperties)
            elif logFileName == "logToStructuredMessage":
                self.logHandler = StructuredMessageLogHandler()
                setattr(self.logger, "logRefObjectProperties", logRefObjectProperties)
            elif logFileName.endswith(".xml") or logFileName.endswith(".json") or logToBuffer:
                self.logHandler = LogToXmlHandler(
                    filename=logFileName,
                    mode=logFileMode or "a",
                    logXmlMaxAttributeLength=logXmlMaxAttributeLength
                )  # should this be "w" mode??
                setattr(self.logger, "logRefObjectProperties", logRefObjectProperties)
                if not logFormat:
                    logFormat = "%(message)s"
            else:
                self.logHandler = logging.FileHandler(filename=logFileName,
                                                      mode=logFileMode or "a",  # should this be "w" mode??
                                                      encoding=logFileEncoding or "utf-8")
            self.logHandler.setFormatter(LogFormatter(logFormat or "%(asctime)s [%(messageCode)s] %(message)s - %(file)s\n"))
            self.logger.addHandler(self.logHandler)
        else:
            self.logger = None
        if self.logger:
            if logPropagate is not None:
                self.logger.propagate = logPropagate
            for logFilter in logFilters:
                self.logger.addFilter(logFilter)
            try:
                self.logger.setLevel((logLevel or "debug").upper())
            except ValueError:
                self.addToLog(_("Unknown log level name: {0}, please choose from {1}").format(
                    logLevel, ', '.join(logging.getLevelName(l).lower()
                                        for l in sorted([i for i in logging._levelToName.keys()
                                                         if isinstance(i, int) and i > 0]))),
                              level=logging.ERROR, messageCode="arelle:logLevel")
            setattr(self.logger, "messageCodeFilter", None)
            setattr(self.logger, "messageLevelFilter", None)
            setattr(self.logHandler, "logTextMaxLength", (logTextMaxLength or LOG_TEXT_MAX_LENGTH))

    def setLogLevelFilter(self, logLevelFilter: str) -> None:
        if self.logger:
            setattr(self.logger, "messageLevelFilter", re.compile(logLevelFilter) if logLevelFilter else None)

    def setLogCodeFilter(self, logCodeFilter: str) -> None:
        if self.logger:
            setattr(self.logger, "messageCodeFilter", re.compile(logCodeFilter) if logCodeFilter else None)

    def addToLog(
        self,
        message: str,
        messageCode: str = "",
        messageArgs: dict[str, Any] | None = None,
        file: str = "",
        refs: list[dict[str, Any]] | None = None,
        level: int | str = logging.INFO
    ) -> None:
        """Add a simple info message to the default logger

        :param message: Text of message to add to log.
        :type message: str
        : param messageArgs: optional dict of message format-string key-value pairs
        :type messageArgs: dict
        :param messageCode: Message code (e.g., a prefix:id of a standard error)
        :param messageCode: str
        :param file: File name (and optional line numbers) pertaining to message
        :type file: str
        """
        args: tuple[str] | tuple[str, dict[str, Any]]
        if self.logger is not None:
            if messageArgs:
                args = (message, messageArgs)
            else:
                args = (message,)  # pass no args if none provided
            if refs is None:
                refs = []
            if isinstance(file, (tuple,list,set)):
                for _file in file:
                    refs.append( {"href": _file} )
            elif isinstance(file, str):
                refs.append( {"href": file} )
            if isinstance(level, str):
                # given level is str at this point, level_int will always
                # be an int but logging.getLevelName returns Any (int if
                # input is str, and str if input is int)
                level = logging.getLevelName(level)
            assert isinstance(level, int)
            self.logger.log(level, *args, extra={"messageCode":messageCode,"refs":refs})
        else:
            try:
                print(message % (messageArgs or {}))
            except UnicodeEncodeError:
                # extra parentheses in print to allow for 3-to-2 conversion
                print((message
                       .encode(sys.stdout.encoding, 'backslashreplace')
                       .decode(sys.stdout.encoding, 'strict')))

    def showStatus(self, message: str, clearAfter: int | None = None) -> None:
        """Dummy method for specialized controller classes to specialize,
        provides user feedback on status line of GUI or web page

        :param message: Message to display on status widget.
        :type message: str
        :param clearAfter: Time, in ms., after which to clear the message (e.g., 5000 for 5 sec.)
        :type clearAfter: int
        """
        pass

    def close(self, saveConfig: bool = False) -> None:
        """Closes the controller and its logger, optionally saving the user preferences configuration

           :param saveConfig: save the user preferences configuration
           :type saveConfig: bool
        """
        PluginManager.save(self)

        if self.hasGui:
            PackageManager.save(self)
        if saveConfig:
            self.saveConfig()
        if self.logger is not None:
            try:
                self.logHandler.close()
            except Exception: # fails on some earlier pythons (3.1)
                pass

    def saveConfig(self) -> None:
        """Save user preferences configuration (in json configuration file)."""
        if self.hasFileSystem and not self.disablePersistentConfig:
            with io.open(self.configJsonFile, 'wt', encoding='utf-8') as f:
                # might not be unicode in 2.7
                jsonStr = str(json.dumps(self.config, ensure_ascii=False, indent=2, sort_keys=True))
                f.write(jsonStr)  # 2.7 getss unicode this way

    # default non-threaded viewModelObject
    def viewModelObject(self, modelXbrl: ModelXbrl, objectId: str) -> None:
        """Notify any watching views to show and highlight selected object.  Generally used
        to scroll list control to object and highlight it, or if tree control, to find the object
        and open tree branches as needed for visibility, scroll to and highlight the object.

        :param modelXbrl: ModelXbrl (DTS) whose views are to be notified
        :type modelXbrl: ModelXbrl
        :param objectId: Selected object id (string format corresponding to ModelObject.objectId() )
        :type objectId: str
        """
        modelXbrl.viewModelObject(objectId)

    def reloadViews(self, modelXbrl: ModelXbrl) -> None:
        """Notification to reload views (probably due to change within modelXbrl).  Dummy
        for subclasses to specialize when they have a GUI or web page.

        :param modelXbrl: ModelXbrl (DTS) whose views are to be notified
        :type modelXbrl: ModelXbrl
        """
        pass

    def rssWatchUpdateOption(self, **args: Any) -> None:
        """Notification to change rssWatch options, as passed in, usually from a modal dialog."""
        pass

    def onPackageEnablementChanged(self) -> None:
        """Notification that package enablement changed, usually from a modal dialog."""
        pass

    # default web authentication password
    def internet_user_password(self, host: str, realm: str) -> tuple[str, str]:
        """Request (for an interactive UI or web page) to obtain user ID and password (usually for a proxy
        or when getting a web page that requires entry of a password).  This function must be overridden
        in a subclass that provides interactive user interface, as the superclass provides only a dummy
        method.

        :param host: The host that is requesting the password
        :type host: str
        :param realm: The domain on the host that is requesting the password
        :type realm: str
        :returns: tuple -- ('myusername','mypassword')
        """
        return ('myusername','mypassword')

    # default web authentication password
    def internet_logon(
        self,
        url: str,
        quotedUrl: str,
        dialogCaption: str,
        dialogText: str
    ) -> str:
        """Web file retrieval results in html that appears to require user logon,
        if interactive allow the user to log on.

        :url: The URL as requested (by an import, include, href, schemaLocation, ...)
        :quotedUrl: The processed and retrievable URL
        :dialogCaption: The dialog caption for the situation
        :dialogText:  The dialog text for the situation at hand
        :returns: string -- 'retry' if user logged on and file can be retried,
                            'cancel' to abandon retrieval
                            'no' if the file is expected and valid contents (not a logon request)
        """
        return 'cancel'

    # if no text, then return what is on the clipboard, otherwise place text onto clipboard
    def clipboardData(self, text: str | None = None) -> Any:
        """Places text onto the clipboard (if text is not None), otherwise retrieves and returns text from the clipboard.
        Only supported for those platforms that have clipboard support in the current python implementation (macOS
        or ActiveState Windows Python).

        :param text: Text to place onto clipboard if not None, otherwise retrieval of text from clipboard.
        :type text: str
        :returns: str -- text from clipboard if parameter text is None, otherwise returns None if text is provided
        """
        if self.hasClipboard:
            try:
                if sys.platform == "darwin":
                    import subprocess
                    if text is None:
                        p = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
                        retcode = p.wait()
                        assert p.stdout is not None
                        text = p.stdout.read().decode('utf-8')  # default utf8 may not be right for mac type:ignore[union-attr]
                        return text
                    else:
                        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                        assert p.stdin is not None
                        p.stdin.write(text.encode('utf-8'))  # default utf8 may not be right for mac
                        p.stdin.close()
                        retcode = p.wait()
                elif sys.platform.startswith("win"):
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    if text is None:
                        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                            return win32clipboard.GetClipboardData().decode("utf8")
                    else:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32clipboard.CF_TEXT, text.encode("utf8"))
                    win32clipboard.CloseClipboard()
                else: # Unix/Linux
                    import gtk
                    clipbd = gtk.Clipboard(display=gtk.gdk.display_get_default(), selection="CLIPBOARD")
                    if text is None:
                        return clipbd.wait_for_text().decode("utf8")
                    else:
                        clipbd.set_text(text.encode("utf8"), len=-1)
            except Exception:
                pass
        return None

    @property
    def memoryUsed(self) -> float | int:
        try:
            global osPrcs # is this needed?
            # to tell mypy this is for windows
            if sys.platform.startswith("win"):
                if osPrcs is None:
                    import win32process as osPrcs

                process_memory = osPrcs.GetProcessMemoryInfo(osPrcs.GetCurrentProcess())['WorkingSetSize']
                if isinstance(process_memory, int):
                    return process_memory / 1024
            elif sys.platform == "sunos5": # ru_maxrss is broken on sparc
                if osPrcs is None:
                    import resource as osPrcs
                return int(subprocess.getoutput("ps -p {0} -o rss".format(os.getpid())).rpartition('\n')[2])
            else: # unix or linux where ru_maxrss works
                import resource as osPrcs  # is this needed?
                # in KB
                return float(osPrcs.getrusage(osPrcs.RUSAGE_SELF).ru_maxrss)
        except Exception:
            pass
        return 0

    def workingOnlineOrInCache(self, url: str) -> bool:
        """
        Determines if the given URL should be requested based on the web cache's internet connectivity status
        and whether the URL already exists in the cache.
        :param url: Web URL
        :return: True if the URL should be requested, False if not
        """
        if not self.webCache.workOffline:
            # Working online, can proceed regardless of presence in cache
            return True
        cacheDirs = (self.webCache.cacheDir, self.webCache.builtInCacheDir)
        for cacheDir in cacheDirs:
            cacheFilepath = self.webCache.urlToCacheFilepath(url, cacheDir=cacheDir)
            normalizedCacheFilepath = self.webCache.normalizeFilepath(cacheFilepath, url)
            if os.path.exists(normalizedCacheFilepath):
                # The file exists in cache, we can proceed despite working offline
                return True
        return False

    def getPluginData(self, pluginName: str) -> PluginData | None:
        return self.__pluginData.get(pluginName)

    def setPluginData(self, pluginData: PluginData) -> None:
        if pluginData.name in self.__pluginData:
            raise RuntimeError(f"PluginData already set on Cntlr for {pluginData.name}.")
        self.__pluginData[pluginData.name] = pluginData

    def _clearPluginData(self) -> None:
        self.__pluginData.clear()

    def testcaseVariationReset(self) -> None:
        self._clearPluginData()
        if self.errorManager is not None:
            self.errorManager.clear()
