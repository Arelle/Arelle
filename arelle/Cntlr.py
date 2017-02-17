# -*- coding: utf-8 -*-
"""
:mod:`arelle.cntlr`
~~~~~~~~~~~~~~~~~~~

.. py:module:: arelle.cntlr
   :copyright: Copyright 2010-2012 Mark V Systems Limited, All rights reserved.
   :license: Apache-2.
   :synopsis: Common controller class to initialize for platform and setup common logger functions
"""
from arelle import PythonUtil # define 2.x or 3.x string types
import tempfile, os, io, sys, logging, gettext, json, re, subprocess, math
from arelle import ModelManager
from arelle.Locale import getLanguageCodes
from arelle import PluginManager, PackageManager
from collections import defaultdict
osPrcs = None
isPy3 = (sys.version[0] >= '3')

def resourcesDir():
    if getattr(sys, 'frozen', False): # Check if frozen by cx_Freeze
        _resourcesDir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(_resourcesDir,"images")):
            return _resourcesDir
    _moduleDir = os.path.dirname(__file__)
    if not os.path.isabs(_moduleDir):
        _moduleDir = os.path.abspath(_moduleDir)
    # for python 3.2 remove __pycache__
    if _moduleDir.endswith("__pycache__"):
        _moduleDir = os.path.dirname(_moduleDir)
    if _moduleDir.endswith("python32.zip/arelle"): # older cx_Freezes use this
        _resourcesDir = os.path.dirname(os.path.dirname(os.path.dirname(_moduleDir)))
    elif (re.match(r".*[\\/](library|python{0.major}{0.minor}).zip[\\/]arelle$".format(sys.version_info),
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
        
        .. attribute:: updateURL
        URL string of application download file (on arelle.org server).  Usually redirected to latest released application installable module.
        
    """
    __version__ = "1.6.0"
    
    def __init__(self, hasGui=False, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None):
        self.hasWin32gui = False
        self.hasGui = hasGui
        self.hasFileSystem = True # no file system on Google App Engine servers
        self.isGAE = False
        self.isCGI = False
        self.systemWordSize = int(round(math.log(sys.maxsize, 2)) + 1) # e.g., 32 or 64

        _resourcesDir = resourcesDir()
        self.configDir = os.path.join(_resourcesDir, "config")
        self.imagesDir = os.path.join(_resourcesDir, "images")
        self.localeDir = os.path.join(_resourcesDir, "locale")
        self.pluginDir = os.path.join(_resourcesDir, "plugin")
        _mplDir = os.path.join(_resourcesDir, "mpl-data")
        if os.path.exists(_mplDir): # set matplotlibdata for cx_Freeze with local directory
            os.environ["MATPLOTLIBDATA"] = _mplDir
        
        serverSoftware = os.getenv("SERVER_SOFTWARE", "")
        if serverSoftware.startswith("Google App Engine/") or serverSoftware.startswith("Development/"):
            self.hasFileSystem = False # no file system, userAppDir does not exist
            self.isGAE = True
        else:
            gatewayInterface = os.getenv("GATEWAY_INTERFACE", "")
            if gatewayInterface.startswith("CGI/"):
                self.isCGI = True
            
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
        if sys.platform == "darwin":
            self.isMac = True
            self.isMSW = False
            if self.hasFileSystem and not configHomeDir:
                self.userAppDir = os.path.expanduser("~") + "/Library/Application Support/Arelle"
            # note that cache is in ~/Library/Caches/Arelle
            self.contextMenuClick = "<Button-2>"
            self.hasClipboard = hasGui  # clipboard always only if Gui (not command line mode)
            self.updateURL = "http://arelle.org/downloads/8"
        elif sys.platform.startswith("win"):
            self.isMac = False
            self.isMSW = True
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
            if "64 bit" in sys.version:
                self.updateURL = "http://arelle.org/downloads/9"
            else: # 32 bit
                self.updateURL = "http://arelle.org/downloads/10"
        else: # Unix/Linux
            self.isMac = False
            self.isMSW = False
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
        try:
            from arelle import webserver
            self.hasWebServer = True
        except ImportError:
            self.hasWebServer = False
        # assert that app dir must exist
        self.config = None
        if self.hasFileSystem:
            if not os.path.exists(self.userAppDir):
                os.makedirs(self.userAppDir)
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
        self.setUiLanguage(self.config.get("userInterfaceLangOverride",None), fallbackToDefault=True)
            
        from arelle.WebCache import WebCache
        self.webCache = WebCache(self, self.config.get("proxySettings"))
        
        # start plug in server (requres web cache initialized, but not logger)
        PluginManager.init(self, loadPluginConfig=hasGui)

        # requires plug ins initialized
        self.modelManager = ModelManager.initialize(self)
 
        # start taxonomy package server (requres web cache initialized, but not logger)
        PackageManager.init(self, loadPackagesConfig=hasGui)
 
        self.startLogging(logFileName, logFileMode, logFileEncoding, logFormat)
        
        # Cntlr.Init after logging started
        for pluginMethod in PluginManager.pluginClassMethods("Cntlr.Init"):
            pluginMethod(self)
            
    def setUiLanguage(self, lang, fallbackToDefault=False):
        try:
            gettext.translation("arelle", 
                                self.localeDir, 
                                getLanguageCodes(lang)).install()
            if not isPy3: # 2.7 gettext provides string instead of unicode from .mo files
                installedGettext = __builtins__['_']
                def convertGettextResultToUnicode(msg):
                    translatedMsg = installedGettext(msg)
                    if isinstance(translatedMsg, _STR_UNICODE):
                        return translatedMsg
                    return translatedMsg.decode('utf-8')
                __builtins__['_'] = convertGettextResultToUnicode
        except Exception:
            if fallbackToDefault or (lang and lang.lower().startswith("en")):
                gettext.install("arelle", 
                                self.localeDir)
        
    def startLogging(self, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None, 
                     logLevel=None, logHandler=None, logToBuffer=False):
        # add additional logging levels (for python 2.7, all of these are ints)
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
                self.logger.logRefObjectProperties = True
            elif logFileName.endswith(".xml") or logFileName.endswith(".json") or logToBuffer:
                self.logHandler = LogToXmlHandler(filename=logFileName, mode=logFileMode or "a")  # should this be "w" mode??
                self.logger.logRefObjectProperties = True
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
            try:
                self.logger.setLevel((logLevel or "debug").upper())
            except ValueError:
                loggingLevelNums = logging._levelNames if sys.version < '3.4' else logging._levelToName
                self.addToLog(_("Unknown log level name: {0}, please choose from {1}").format(
                    logLevel, ', '.join(logging.getLevelName(l).lower()
                                        for l in sorted([i for i in logging.loggingLevelNums.keys()
                                                         if isinstance(i,_INT_TYPES) and i > 0]))),
                              level=logging.ERROR, messageCode="arelle:logLevel")
            self.logger.messageCodeFilter = None
            self.logger.messageLevelFilter = None
                
    def setLogLevelFilter(self, logLevelFilter):
        if self.logger:
            self.logger.messageLevelFilter = re.compile(logLevelFilter) if logLevelFilter else None
            
    def setLogCodeFilter(self, logCodeFilter):
        if self.logger:
            self.logger.messageCodeFilter = re.compile(logCodeFilter) if logCodeFilter else None

    def addToLog(self, message, messageCode="", messageArgs=None, file="", refs=None, level=logging.INFO):
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
            elif isinstance(file, _STR_BASE):
                refs.append( {"href": file} )
            if isinstance(level, _STR_BASE):
                level = logging._checkLevel(level)
            self.logger.log(level, *args, extra={"messageCode":messageCode,"refs":refs})
        else:
            try:
                print(message % (messageArgs or {}))
            except UnicodeEncodeError:
                # extra parentheses in print to allow for 3-to-2 conversion
                print((message
                       .encode(sys.stdout.encoding, 'backslashreplace')
                       .decode(sys.stdout.encoding, 'strict')))
            
    def showStatus(self, message, clearAfter=None):
        """Dummy method for specialized controller classes to specialize, 
        provides user feedback on status line of GUI or web page
        
        :param message: Message to display on status widget.
        :type message: str
        :param clearAfter: Time, in ms., after which to clear the message (e.g., 5000 for 5 sec.)
        :type clearAfter: int
        """
        pass
    
    def close(self, saveConfig=False):
        """Closes the controller and its logger, optionally saving the user preferences configuration
           
           :param saveConfig: save the user preferences configuration
           :type saveConfig: bool
        """
        PluginManager.save(self)
        PackageManager.save(self)
        if saveConfig:
            self.saveConfig()
        if self.logger is not None:
            try:
                self.logHandler.close()
            except Exception: # fails on some earlier pythons (3.1)
                pass
        
    def saveConfig(self):
        """Save user preferences configuration (in json configuration file)."""
        if self.hasFileSystem:
            with io.open(self.configJsonFile, 'wt', encoding='utf-8') as f:
                jsonStr = _STR_UNICODE(json.dumps(self.config, ensure_ascii=False, indent=2)) # might not be unicode in 2.7
                f.write(jsonStr)  # 2.7 getss unicode this way
            
    # default non-threaded viewModelObject                 
    def viewModelObject(self, modelXbrl, objectId):
        """Notify any watching views to show and highlight selected object.  Generally used
        to scroll list control to object and highlight it, or if tree control, to find the object
        and open tree branches as needed for visibility, scroll to and highlight the object.
           
        :param modelXbrl: ModelXbrl (DTS) whose views are to be notified
        :type modelXbrl: ModelXbrl
        :param objectId: Selected object id (string format corresponding to ModelObject.objectId() )
        :type objectId: str
        """
        modelXbrl.viewModelObject(objectId)
            
    def reloadViews(self, modelXbrl):
        """Notification to reload views (probably due to change within modelXbrl).  Dummy
        for subclasses to specialize when they have a GUI or web page.
           
        :param modelXbrl: ModelXbrl (DTS) whose views are to be notified
        :type modelXbrl: ModelXbrl
        """
        pass
    
    def rssWatchUpdateOption(self, **args):
        """Notification to change rssWatch options, as passed in, usually from a modal dialog."""
        pass
    
    def onPackageEnablementChanged(self):
        """Notification that package enablement changed, usually from a modal dialog."""
        pass
        
    # default web authentication password
    def internet_user_password(self, host, realm):
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
    def internet_logon(self, url, quotedUrl, dialogCaption, dialogText):
        """Web file retieval results in html that appears to require user logon,
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
    def clipboardData(self, text=None):
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
                        text = p.stdout.read().decode('utf-8')  # default utf8 may not be right for mac
                        return text
                    else:
                        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
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
    def memoryUsed(self):
        try:
            global osPrcs
            if self.isMSW:
                if osPrcs is None:
                    import win32process as osPrcs
                return osPrcs.GetProcessMemoryInfo(osPrcs.GetCurrentProcess())['WorkingSetSize'] / 1024
            elif sys.platform == "sunos5": # ru_maxrss is broken on sparc
                if osPrcs is None:
                    import resource as osPrcs
                return int(subprocess.getoutput("ps -p {0} -o rss".format(os.getpid())).rpartition('\n')[2])
            else: # unix or linux where ru_maxrss works
                import resource as osPrcs
                return osPrcs.getrusage(osPrcs.RUSAGE_SELF).ru_maxrss # in KB
        except Exception:
            pass
        return 0
    
def logRefsFileLines(refs):
    fileLines = defaultdict(set)
    for ref in refs:
        href = ref.get("href")
        if href:
            fileLines[href.partition("#")[0]].add(ref.get("sourceLine", 0))
    return ", ".join(file + " " + ', '.join(str(line) 
                                            for line in sorted(lines, key=lambda l: l)
                                            if line)
                    for file, lines in sorted(fileLines.items()))

class LogFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super(LogFormatter, self).__init__(fmt, datefmt)
        
    def fileLines(self, record):
        # provide a file parameter made up from refs entries
        return logRefsFileLines(record.refs)
        
    def format(self, record):
        record.file = self.fileLines(record)
        try:
            formattedMessage = super(LogFormatter, self).format(record)
        except (KeyError, TypeError, ValueError) as ex:
            formattedMessage = "Message: "
            if getattr(record, "messageCode", ""):
                formattedMessage += "[{0}] ".format(record.messageCode)
            if getattr(record, "msg", ""):
                formattedMessage += record.msg + " "
            if isinstance(record.args, dict) and 'error' in record.args: # args may be list or empty
                formattedMessage += record.args['error']
            formattedMessage += " \nMessage log error: " + str(ex)
        del record.file
        return formattedMessage

class LogToPrintHandler(logging.Handler):
    """
    .. class:: LogToPrintHandler()
    
    A log handler that emits log entries to standard out as they are logged.
    
    CAUTION: Output is utf-8 encoded, which is fine for saving to files, but may not display correctly in terminal windows.

    :param logOutput: 'logToStdErr' to cause log printint to stderr instead of stdout
    :type logOutput: str
    """
    def __init__(self, logOutput):
        super(LogToPrintHandler, self).__init__()
        if logOutput == "logToStdErr":
            self.logFile = sys.stderr
        else:
            self.logFile = None
        
    def emit(self, logRecord):
        file = sys.stderr if self.logFile else None
        logEntry = self.format(logRecord)
        if not isPy3:
            logEntry = logEntry.encode("utf-8", "replace")
        try:
            print(logEntry, file=file)
        except UnicodeEncodeError:
            # extra parentheses in print to allow for 3-to-2 conversion
            print((logEntry
                   .encode(sys.stdout.encoding, 'backslashreplace')
                   .decode(sys.stdout.encoding, 'strict')), 
                  file=file)

class LogHandlerWithXml(logging.Handler):        
    def __init__(self):
        super(LogHandlerWithXml, self).__init__()
        
    def recordToXml(self, logRec):
        def entityEncode(arg, truncateAt=32767):  # be sure it's a string, vs int, etc, and encode &, <, ".
            s = str(arg)
            s = s if len(s) <= truncateAt else s[:truncateAt] + '...'
            return s.replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')
        
        def ncNameEncode(arg):
            s = []
            for c in arg:
                if c.isalnum() or c in ('.','-','_'):
                    s.append(c)
                else: # covers : and any other non-allowed character
                    s.append('_') # change : into _ for xml correctness
            return "".join(s)
        
        def propElts(properties, indent, truncatAt=128):
            nestedIndent = indent + ' '
            return indent.join('<property name="{0}" value="{1}"{2}>'.format(
                                    entityEncode(p[0]),
                                    entityEncode(p[1], truncateAt=truncatAt),
                                    '/' if len(p) == 2 
                                    else '>' + nestedIndent + propElts(p[2],nestedIndent) + indent + '</property')
                                for p in properties 
                                if 2 <= len(p) <= 3)
        
        msg = self.format(logRec)
        if logRec.args:
            args = "".join([' {0}="{1}"'.format(ncNameEncode(n), entityEncode(v, truncateAt=128)) 
                            for n, v in logRec.args.items()])
        else:
            args = ""
        refs = "\n ".join('\n <ref href="{0}"{1}{2}{3}>'.format(
                        entityEncode(ref["href"]), 
                        ' sourceLine="{0}"'.format(ref["sourceLine"]) if "sourceLine" in ref else '',
                        ''.join(' {}="{}"'.format(ncNameEncode(k),entityEncode(v)) 
                                                  for k,v in ref["customAttributes"].items())
                             if 'customAttributes' in ref else '',
                        (">\n  " + propElts(ref["properties"],"\n  ", 32767) + "\n </ref" ) if "properties" in ref else '/')
                       for ref in logRec.refs)
        return ('<entry code="{0}" level="{1}">'
                '\n <message{2}>{3}</message>{4}'
                '</entry>\n'.format(logRec.messageCode, 
                                    logRec.levelname.lower(), 
                                    args, 
                                    entityEncode(msg), 
                                    refs))
    
class LogToXmlHandler(LogHandlerWithXml):
    """
    .. class:: LogToXmlHandler(filename)
    
    A log handler that writes log entries to named XML file (utf-8 encoded) upon closing the application.
    """
    def __init__(self, filename=None, mode='w'):
        super(LogToXmlHandler, self).__init__()
        self.filename = filename # may be none if buffer is retrieved by get methods below and not written anywhere
        self.logRecordBuffer = []
        self.filemode = mode
        
    def flush(self):
        if self.filename == "logToStdOut.xml":
            print('<?xml version="1.0" encoding="utf-8"?>')
            print('<log>')
            for logRec in self.logRecordBuffer:
                logRecXml = self.recordToXml(logRec)
                try:
                    print(logRecXml)
                except UnicodeEncodeError:
                    # extra parentheses in print to allow for 3-to-2 conversion
                    print((logRecXml
                           .encode(sys.stdout.encoding, 'backslashreplace')
                           .decode(sys.stdout.encoding, 'strict')))
            print('</log>')
        elif self.filename is not None:
            if self.filename.endswith(".xml"):
                # print ("filename=" + self.filename)
                with open(self.filename, self.filemode, encoding='utf-8') as fh:
                    fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
                    fh.write('<log>\n')
                    for logRec in self.logRecordBuffer:
                        fh.write(self.recordToXml(logRec))
                    fh.write('</log>\n')
            elif self.filename.endswith(".json"):
                with open(self.filename, self.filemode, encoding='utf-8') as fh:
                    fh.write(self.getJson())
            elif self.filename in ("logToPrint", "logToStdErr"):
                _file = sys.stderr if self.filename == "logToStdErr" else None
                for logRec in self.logRecordBuffer:
                    logEntry = self.format(logRec)
                    if not isPy3:
                        logEntry = logEntry.encode("utf-8", "replace")
                    try:
                        print(logEntry, file=_file)
                    except UnicodeEncodeError:
                        # extra parentheses in print to allow for 3-to-2 conversion
                        print((logEntry
                               .encode(sys.stdout.encoding, 'backslashreplace')
                               .decode(sys.stdout.encoding, 'strict')), 
                              file=_file)
            else:
                with open(self.filename, self.filemode, encoding='utf-8') as fh:
                    for logRec in self.logRecordBuffer:
                        fh.write(self.format(logRec) + "\n")
        self.clearLogBuffer()
                
    def clearLogBuffer(self):
        del self.logRecordBuffer[:]
        
    def getXml(self, clearLogBuffer=True):
        """Returns an XML document (as a string) representing the messages in the log buffer, and clears the buffer.
        
        :reeturns: str -- XML document string of messages in the log buffer.
        """
        xml = ['<?xml version="1.0" encoding="utf-8"?>\n',
               '<log>']
        for logRec in self.logRecordBuffer:
            xml.append(self.recordToXml(logRec))
        xml.append('</log>')  
        if clearLogBuffer:
            self.clearLogBuffer()
        return '\n'.join(xml)
    
    def getJson(self, clearLogBuffer=True):
        """Returns an JSON string representing the messages in the log buffer, and clears the buffer.
        
        :returns: str -- json representation of messages in the log buffer
        """
        entries = []
        for logRec in self.logRecordBuffer:
            message = { "text": self.format(logRec) }
            if logRec.args:
                for n, v in logRec.args.items():
                    message[n] = v
            entry = {"code": logRec.messageCode,
                     "level": logRec.levelname.lower(),
                     "refs": logRec.refs,
                     "message": message}
            entries.append(entry)
        if clearLogBuffer:
            self.clearLogBuffer()
        return json.dumps( {"log": entries}, ensure_ascii=False, indent=1, default=str )
    
    def getLines(self, clearLogBuffer=True):
        """Returns a list of the message strings in the log buffer, and clears the buffer.
        
        :returns: [str] -- list of strings representing messages corresponding to log buffer entries
        """
        lines = [self.format(logRec) for logRec in self.logRecordBuffer]
        if clearLogBuffer:
            self.clearLogBuffer()
        return lines
    
    def getText(self, separator='\n', clearLogBuffer=True):
        """Returns a string of the lines in the log buffer, separated by newline or provided separator.
        
        :param separator: Line separator (default is platform os newline character)
        :type separator: str
        :returns: str -- joined lines of the log buffer.
        """
        return separator.join(self.getLines(clearLogBuffer=clearLogBuffer))
    
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)

class LogToBufferHandler(LogToXmlHandler):
    """
    .. class:: LogToBufferHandler()
    
    A log handler that writes log entries to a memory buffer for later retrieval (to a string) in XML, JSON, or text lines,
    usually for return to a web service or web page call.
    """
    def __init__(self):
        super(LogToBufferHandler, self).__init__()
        
    def flush(self):
        pass # do nothing -- overrides LogToXmlHandler's flush
    

