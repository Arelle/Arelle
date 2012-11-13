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
import tempfile, os, io, sys, logging, gettext, json, re, subprocess
from arelle import ModelManager
from arelle.Locale import getLanguageCodes
from arelle import PluginManager
from collections import defaultdict
osPrcs = None
isPy3 = (sys.version[0] >= '3')

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
    __version__ = "1.0.0"
    
    def __init__(self, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None):
        self.hasWin32gui = False
        self.hasGui = False
        if sys.platform == "darwin":
            self.isMac = True
            self.isMSW = False
            self.userAppDir = os.path.expanduser("~") + "/Library/Application Support/Arelle"
            self.contextMenuClick = "<Button-2>"
            self.hasClipboard = True
            self.updateURL = "http://arelle.org/downloads/8"
        elif sys.platform.startswith("win"):
            self.isMac = False
            self.isMSW = True
            tempDir = tempfile.gettempdir()
            if tempDir.endswith('local\\temp'):
                impliedAppDir = tempDir[:-10] + 'local'
            else:
                impliedAppDir = tempDir
            self.userAppDir = os.path.join(
                   os.getenv('XDG_CONFIG_HOME', impliedAppDir),
                   "Arelle")
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
            self.contextMenuClick = "<Button-3>"
            if "64 bit" in sys.version:
                self.updateURL = "http://arelle.org/downloads/9"
            else: # 32 bit
                self.updateURL = "http://arelle.org/downloads/10"
        else: # Unix/Linux
            self.isMac = False
            self.isMSW = False
            self.userAppDir = os.path.join(
                   os.getenv('XDG_CONFIG_HOME', os.path.expanduser("~/.config")),
                   "arelle")
            try:
                import gtk
                self.hasClipboard = True
            except ImportError:
                self.hasClipboard = False
            self.contextMenuClick = "<Button-3>"
        self.moduleDir = os.path.dirname(__file__)
        # for python 3.2 remove __pycache__
        if self.moduleDir.endswith("__pycache__"):
            self.moduleDir = os.path.dirname(self.moduleDir)
        if self.moduleDir.endswith("python32.zip/arelle"):
            '''
            distZipFile = os.path.dirname(self.moduleDir)
            d = os.path.join(self.userAppDir, "arelle")
            self.configDir = os.path.join(d, "config")
            self.imagesDir = os.path.join(d, "images")
            import zipfile
            distZip = zipfile.ZipFile(distZipFile, mode="r")
            distNames = distZip.namelist()
            distZip.extractall(path=self.userAppDir,
                               members=[f for f in distNames if "/config/" in f or "/images/" in f]
                               )
            distZip.close()
            '''
            resources = os.path.dirname(os.path.dirname(os.path.dirname(self.moduleDir)))
            self.configDir = os.path.join(resources, "config")
            self.imagesDir = os.path.join(resources, "images")
            self.localeDir = os.path.join(resources, "locale")
        elif self.moduleDir.endswith("library.zip\\arelle") or self.moduleDir.endswith("library.zip/arelle"): # cx_Freexe
            resources = os.path.dirname(os.path.dirname(self.moduleDir))
            self.configDir = os.path.join(resources, "config")
            self.imagesDir = os.path.join(resources, "images")
            self.localeDir = os.path.join(resources, "locale")
        else:
            self.configDir = os.path.join(self.moduleDir, "config")
            self.imagesDir = os.path.join(self.moduleDir, "images")
            self.localeDir = os.path.join(self.moduleDir, "locale")
        try:
            from arelle import webserver
            self.hasWebServer = True
        except ImportError:
            self.hasWebServer = False
        # assert that app dir must exist
        if not os.path.exists(self.userAppDir):
            os.makedirs(self.userAppDir)
        # load config if it exists
        self.configJsonFile = self.userAppDir + os.sep + "config.json"
        self.config = None
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
        self.modelManager = ModelManager.initialize(self)
        
        # start plug in server (requres web cache initialized
        PluginManager.init(self)
 
        self.startLogging(logFileName, logFileMode, logFileEncoding, logFormat)
        
    def setUiLanguage(self, lang, fallbackToDefault=False):
        try:
            gettext.translation("arelle", 
                                self.localeDir, 
                                getLanguageCodes(lang)).install()
        except Exception:
            if fallbackToDefault or (lang and lang.lower().startswith("en")):
                gettext.install("arelle", 
                                self.localeDir)
        
    def startLogging(self, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None, 
                     logLevel=None, logLevelFilter=None, logCodeFilter=None, logHandler=None):
        # add additional logging levels    
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
            if logFileName in ("logToPrint", "logToStdErr"):
                self.logHandler = LogToPrintHandler(logFileName)
            elif logFileName == "logToBuffer":
                self.logHandler = LogToBufferHandler()
                self.logger.logHrefObjectProperties = True
            elif logFileName.endswith(".xml"):
                self.logHandler = LogToXmlHandler(filename=logFileName)
                self.logger.logHrefObjectProperties = True
                logFormat = "%(message)s"
            else:
                self.logHandler = logging.FileHandler(filename=logFileName, 
                                                      mode=logFileMode if logFileMode else "w", 
                                                      encoding=logFileEncoding if logFileEncoding else "utf-8")
            self.logHandler.setFormatter(LogFormatter(logFormat or "%(asctime)s [%(messageCode)s] %(message)s - %(file)s\n"))
            self.logger.addHandler(self.logHandler)
        else:
            self.logger = None
        if self.logger:
            if logLevel and logLevel.upper() not in logging._levelNames.keys():
                self.addToLog(_("Unknown log level name: {0}, please choose from {1}").format(
                    logLevel, ', '.join(logging.getLevelName(l).lower()
                                        for l in sorted([i for i in logging._levelNames.keys()
                                                         if isinstance(i,int) and i > 0]))),
                              level=logging.ERROR, messageCode="arelle:logLevel")
            else:
                self.logger.setLevel(logging.getLevelName((logLevel or "debug").upper()))
            self.logger.messageCodeFilter = re.compile(logCodeFilter) if logCodeFilter else None
            self.logger.messageLevelFilter = re.compile(logLevelFilter) if logLevelFilter else None
                        
    def addToLog(self, message, messageCode="", file="", level=logging.INFO):
        """Add a simple info message to the default logger
           
        :param message: Text of message to add to log.
        :type message: str
        :param messageCode: Message code (e.g., a prefix:id of a standard error)
        :param messageCode: str
        :param file: File name (and optional line numbers) pertaining to message
        :type file: str
        """
        if self.logger is not None:
            self.logger.log(level, message, extra={"messageCode":messageCode,"refs":[{"href": file}]})
        else:
            print(message) # allows printing on standard out
            
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
        if saveConfig:
            self.saveConfig()
        if self.logger is not None:
            try:
                self.logHandler.close()
            except Exception: # fails on some earlier pythons (3.1)
                pass
        
    def saveConfig(self):
        """Save user preferences configuration (in json configuration file)."""
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
                        text = p.stdout.read()
                        return text
                    else:
                        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                        p.stdin.write(text)
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

class LogFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super(LogFormatter, self).__init__(fmt, datefmt)
        
    def format(self, record):
        # provide a file parameter made up from refs entries
        fileLines = defaultdict(set)
        for ref in record.refs:
            fileLines[ref["href"].partition("#")[0]].add(ref.get("sourceLine", 0))
        record.file = ", ".join(file + " " + ', '.join(str(line) 
                                                       for line in sorted(lines, key=lambda l: l)
                                                       if line)
                                for file, lines in sorted(fileLines.items()))
        try:
            formattedMessage = super(LogFormatter, self).format(record)
        except KeyError as ex:
            formattedMessage = "Message: " + record.args.get('error','') + " \nMessage log error: " + str(ex)
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
        if isPy3:
            logEntry = self.format(logRecord)
        else:
            logEntry = self.format(logRecord).encode("utf-8")
        if self.logFile:
            print(logEntry, file=sys.stderr)
        else:
            print(logEntry)

class LogHandlerWithXml(logging.Handler):        
    def __init__(self):
        super(LogHandlerWithXml, self).__init__()
        
    def recordToXml(self, logRec):
        def entityEncode(arg):  # be sure it's a string, vs int, etc, and encode &, <, ".
            return str(arg).replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')
        
        def propElts(properties, indent):
            nestedIndent = indent + ' '
            return indent.join('<property name="{0}" value="{1}"{2}>'.format(
                                    entityEncode(p[0]),
                                    entityEncode(p[1]),
                                    '/' if len(p) == 2 
                                    else '>' + nestedIndent + propElts(p[2],nestedIndent) + indent + '</property')
                                for p in properties 
                                if 2 <= len(p) <= 3)
        
        msg = self.format(logRec)
        if logRec.args:
            args = "".join([' {0}="{1}"'.format(n, entityEncode(v)) 
                            for n, v in logRec.args.items()])
        else:
            args = ""
        refs = "\n ".join('\n <ref href="{0}"{1}{2}>'.format(
                        entityEncode(ref["href"]), 
                        ' sourceLine="{0}"'.format(ref["sourceLine"]) if "sourceLine" in ref else '',
                        (">\n  " + propElts(ref["properties"],"\n  ") + "\n </ref" ) if "properties" in ref else '/')
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
    def __init__(self, filename):
        super(LogToXmlHandler, self).__init__()
        self.filename = filename
        self.logRecordBuffer = []
    def flush(self):
        if self.filename == "logToStdOut.xml":
            print('<?xml version="1.0" encoding="utf-8"?>')
            print('<log>')
            for logRec in self.logRecordBuffer:
                print(self.recordToXml(logRec))
            print('</log>')
        else:
            print ("filename=" + self.filename)
            with open(self.filename, "w", encoding='utf-8') as fh:
                fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
                fh.write('<log>\n')
                for logRec in self.logRecordBuffer:
                    fh.write(self.recordToXml(logRec))
                fh.write('</log>\n')  
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)

class LogToBufferHandler(LogHandlerWithXml):
    """
    .. class:: LogToBufferHandler()
    
    A log handler that writes log entries to a memory buffer for later retrieval (to a string) in XML, JSON, or text lines,
    usually for return to a web service or web page call.
    """
    def __init__(self):
        super(LogToBufferHandler, self).__init__()
        self.logRecordBuffer = []
        
    def flush(self):
        pass # do nothing
    
    def getXml(self):
        """Returns an XML document (as a string) representing the messages in the log buffer, and clears the buffer.
        
        :reeturns: str -- XML document string of messages in the log buffer.
        """
        xml = ['<?xml version="1.0" encoding="utf-8"?>\n',
               '<log>']
        for logRec in self.logRecordBuffer:
            xml.append(self.recordToXml(logRec))
        xml.append('</log>')  
        self.logRecordBuffer = []
        return '\n'.join(xml)
    
    def getJson(self):
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
        self.logRecordBuffer = []
        return json.dumps( {"log": entries} )
    
    def getLines(self):
        """Returns a list of the message strings in the log buffer, and clears the buffer.
        
        :returns: [str] -- list of strings representing messages corresponding to log buffer entries
        """
        lines = [self.format(logRec) for logRec in self.logRecordBuffer]
        self.logRecordBuffer = []
        return lines
    
    def getText(self, separator='\n'):
        """Returns a string of the lines in the log buffer, separated by newline or provided separator.
        
        :param separator: Line separator (default is platform os newline character)
        :type separator: str
        :returns: str -- joined lines of the log buffer.
        """
        return separator.join(self.getLines())
    
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)


