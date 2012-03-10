# -*- coding: utf-8 -*-
"""
:mod:`arelle.cntlr`
~~~~~~~~~~~~~~~~~~~

.. module:: arelle.cntlr
   :copyright: Copyright 2010-2012 Mark V Systems Limited, All rights reserved.
   :license: Apache-2.
   :synopsis: Common controller class to initialize for platform and setup common logger functions
"""
from __future__ import print_function
from arelle import PythonUtil # define 2.x or 3.x string types
import tempfile, os, io, sys, logging, gettext, json
from arelle import ModelManager
from arelle.Locale import getLanguageCodes
from arelle import PluginManager
from collections import defaultdict
isPy3 = (sys.version[0] >= '3')

class Cntlr:
    """
    .. class:: Cntlr(logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None)
    
    Initialization sets up for platform
    
    - Platform directories for application, configuration, locale, and cache
    - Context menu click event (TKinter)
    - Clipboard presence
    - Update URL
    - Reloads proir config (pickled) user preferences
    - Sets up proxy and web cache
    - Sets up logging
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
                self.userAppDir = tempDir[:-10] + 'local\\Arelle'
            else:
                self.userAppDir = tempDir + os.sep + 'arelle'
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
        try:
            gettext.translation("arelle", self.localeDir, getLanguageCodes()).install()
        except Exception as msg:
            gettext.install("arelle", self.localeDir)
            
        from arelle.WebCache import WebCache
        self.webCache = WebCache(self, self.config.get("proxySettings"))
        self.modelManager = ModelManager.initialize(self)
        
        # start plug in server (requres web cache initialized
        PluginManager.init(self)
 
        self.startLogging(logFileName, logFileMode, logFileEncoding, logFormat)
        
    def startLogging(self, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None):
        if logFileName: # use default logging
            self.logger = logging.getLogger("arelle")
            if logFileName == "logToPrint":
                self.logHandler = LogToPrintHandler()
            elif logFileName == "logToBuffer":
                self.logHandler = LogToBufferHandler()
            elif logFileName.endswith(".xml"):
                self.logHandler = LogToXmlHandler(filename=logFileName)
                logFormat = "%(message)s"
            else:
                self.logHandler = logging.FileHandler(filename=logFileName, 
                                                      mode=logFileMode if logFileMode else "w", 
                                                      encoding=logFileEncoding if logFileEncoding else "utf-8")
            self.logHandler.level = logging.DEBUG
            self.logHandler.setFormatter(LogFormatter(logFormat if logFormat else "%(asctime)s [%(messageCode)s] %(message)s - %(file)s\n"))
            self.logger.addHandler(self.logHandler)
        else:
            self.logger = None
                        
    def addToLog(self, message, messageCode="", file=""):
        """.. method:: addToLog(message, messageCode="", file="")
           Add a simple info message to the default logger"""
        if self.logger is not None:
            self.logger.info(message, extra={"messageCode":messageCode,"refs":[{"href": file}]})
        else:
            print(message) # allows printing on standard out
            
    def showStatus(self, message, clearAfter=None):
        """.. method:: addToLog(message, clearAfter=None)
           Dummy for subclasses to specialize, provides user feedback on status line of GUI or web page"""
        pass
    
    def close(self, saveConfig=False):
        """.. method:: close(saveConfig=False)
           Close controller and its logger, optionally saaving the user preferences configuration
           :param saveConfig: save the user preferences configuration"""
        PluginManager.save(self)
        if saveConfig:
            self.saveConfig()
        if self.logger is not None:
            self.logHandler.close()
        
    def saveConfig(self):
        """.. method:: saveConfig()
           Save user preferences configuration (in a pickle file)."""
        with io.open(self.configJsonFile, 'wt', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
            
    # default non-threaded viewModelObject                 
    def viewModelObject(self, modelXbrl, objectId):
        """.. method:: viewModelObject(modelXbrl, objectId)
           Notification to watching views to show and highlight selected object
           :param modelXbrl: ModelXbrl whose views are to be notified
           :param objectId: Selected object."""
        modelXbrl.viewModelObject(objectId)
            
    def reloadViews(self, modelXbrl):
        """.. method:: reloadViews(modelXbrl)
           Notification to reload views (probably due to change within modelXbrl).  Dummy
           for subclasses to specialize when they have a GUI or web page.
           :param modelXbrl: ModelXbrl whose views are to be reloaded"""
        pass
    
    def rssWatchUpdateOption(self, **args):
        """.. method:: rssWatchUpdateOption(**args)
           Notification to change rssWatch options, as passed in, usually from a modal dialog."""
        pass
        
    # default web authentication password
    def internet_user_password(self, host, realm):
        """.. method:: internet_user_password(self, host, realm)
           Request (for an interactive UI or web page) to obtain user ID and password (usually for a proxy 
           or when getting a web page that requires entry of a password).
           :param host: The host that is requesting the password
           :param realm: The domain on the host that is requesting the password
           :rtype string: xzzzzzz"""
        return ('myusername','mypassword')
    
    # if no text, then return what is on the clipboard, otherwise place text onto clipboard
    def clipboardData(self, text=None):
        """.. method:: clipboardData(self, text=None)
           Places text onto the clipboard (if text is not None), otherwise retrieves and returns text from the clipboard.
           Only supported for those platforms that have clipboard support in the current python implementation (macOS
           or ActiveState Windows Python).
           :param text: Text to place onto clipboard if not None, otherwise retrieval of text from clipboard."""
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
        formattedMessage = super(LogFormatter, self).format(record)
        del record.file
        return formattedMessage

class LogToPrintHandler(logging.Handler):
    """
    .. class:: LogToPrintHandler()
    
    A log handler that emits log entries to standard out as they are logged.
    
    CAUTION: Output is utf-8 encoded, which is fine for saving to files, but may not display correctly in terminal windows.
    """
    def emit(self, logRecord):
        if isPy3:
            print(self.format(logRecord))
        else:
            print(self.format(logRecord).encode("utf-8"))

class LogHandlerWithXml(logging.Handler):        
    def __init__(self):
        super(LogHandlerWithXml, self).__init__()
        
    def recordToXml(self, logRec):
        msg = self.format(logRec)
        if logRec.args:
            args = "".join([' {0}="{1}"'.format(n, str(v).replace('"','&quot;')) for n, v in logRec.args.items()])
        else:
            args = ""
        refs = "\n".join('<ref href="{0}"{1}/>'.format(
                        ref["href"], 
                        ' sourceLine="{0}"'.format(ref["sourceLine"]) if "sourceLine" in ref else '')
                       for ref in logRec.refs)
        return ('<entry code="{0}" level="{1}">'
                '<message{2}>{3}</message>{4}'
                '</entry>\n'.format(logRec.messageCode, 
                                    logRec.levelname.lower(), 
                                    args, 
                                    msg.replace("&","&amp;").replace("<","&lt;"), 
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
        """.. method:: getXml()
           Returns an XML document (as a string) representing the messages in the log buffer, and clears the buffer."""
        xml = ['<?xml version="1.0" encoding="utf-8"?>\n',
               '<log>']
        for logRec in self.logRecordBuffer:
            xml.append(self.recordToXml(logRec))
        xml.append('</log>')  
        self.logRecordBuffer = []
        return '\n'.join(xml)
    
    def getJson(self):
        """.. method:: getJson()
           Returns an JSON string representing the messages in the log buffer, and clears the buffer."""
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
        """.. method:: getLines()
           Returns a list of the message strings in the log buffer, and clears the buffer."""
        lines = [self.format(logRec) for logRec in self.logRecordBuffer]
        self.logRecordBuffer = []
        return lines
    
    def getText(self, separator='\n'):
        """.. method:: getText()
           :param separator: Line separator (default is platform's newline)
           Returns a text string of the messages in the log buffer, and clears the buffer."""
        return separator.join(self.getLines())
    
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)



