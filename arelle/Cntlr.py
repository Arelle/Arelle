'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import tempfile, os, pickle, sys, logging, gettext, json
from arelle import ModelManager
from arelle.Locale import getLanguageCodes

class Cntlr:

    __version__ = "0.0.4"
    
    def __init__(self, logFileName=None, logFileMode=None, logFileEncoding=None, logFormat=None):
        self.hasWin32gui = False
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
        elif self.moduleDir.endswith("library.zip\\arelle"): # cx_Freexe
            resources = os.path.dirname(os.path.dirname(self.moduleDir))
            self.configDir = os.path.join(resources, "config")
            self.imagesDir = os.path.join(resources, "images")
            self.localeDir = os.path.join(resources, "locale")
        else:
            self.configDir = os.path.join(self.moduleDir, "config")
            self.imagesDir = os.path.join(self.moduleDir, "images")
            self.localeDir = os.path.join(self.moduleDir, "locale")
        # assert that app dir must exist
        if not os.path.exists(self.userAppDir):
            os.makedirs(self.userAppDir)
        # load config if it exists
        self.configPickleFile = self.userAppDir + os.sep + "config.pickle"
        self.config = None
        if os.path.exists(self.configPickleFile):
            try:
                with open(self.configPickleFile, 'rb') as f:
                    self.config = pickle.load(f)
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
            self.logHandler.setFormatter(logging.Formatter(logFormat if logFormat else "%(asctime)s [%(messageCode)s] %(message)s - %(file)s %(sourceLine)s \n"))
            self.logger.addHandler(self.logHandler)
        else:
            self.logger = None
            
    def addToLog(self, message, messageCode="", file="", sourceLine=""):
        # if there is a default logger, use it with dummy file name and arguments
        if self.logger is not None:
            self.logger.info(message, extra={"messageCode":messageCode,"file":file,"sourceLine":sourceLine})
        else:
            print(message) # allows printing on standard out
            
    def showStatus(self, message, clearAfter=None):
        # dummy status line for batch operation
        pass
    
    def close(self, saveConfig=False):
        if saveConfig:
            self.saveConfig()
        if self.logger is not None:
            self.logHandler.close()
        
    def saveConfig(self):
        with open(self.configPickleFile, 'wb') as f:
            pickle.dump(self.config, f, pickle.HIGHEST_PROTOCOL)
            
    # default non-threaded viewModelObject                 
    def viewModelObject(self, modelXbrl, objectId):
        modelXbrl.viewModelObject(objectId)
            
    def reloadViews(self, modelXbrl):
        pass
    
    def rssWatchUpdateOption(self, **args):
        pass
        
    # default web authentication password
    def internet_user_password(self, host, realm):
        return ('myusername','mypassword')
    
    # if no text, then return what is on the clipboard, otherwise place text onto clipboard
    def clipboardData(self, text=None):
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

class LogToPrintHandler(logging.Handler):
    def emit(self, logRecord):
        print(self.format(logRecord))

class LogToXmlHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.logRecordBuffer = []
    def flush(self):
        with open(self.filename, "w", encoding='utf-8') as fh:
            fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
            fh.write('<log>\n')
            for logRec in self.logRecordBuffer:
                msg = self.format(logRec)
                if logRec.args:
                    args = "".join([' {0}="{1}"'.format(n, v.replace('"','&quot;')) for n, v in logRec.args.items()])
                else:
                    args = ""
                fh.write('<entry code="{0}" level="{1}" file="{2}" sourceLine="{3}"><message{4}>{5}</message></entry>\n'.format(
                        logRec.messageCode, logRec.levelname.lower(), logRec.file, logRec.sourceLine, args, msg.replace("&","&amp;").replace("<","&lt;")))
            fh.write('</log>\n')  
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)

class LogToBufferHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logRecordBuffer = []
        
    def flush(self):
        pass # do nothing
    
    def getXml(self):
        xml = ['<?xml version="1.0" encoding="utf-8"?>\n',
               '<log>']
        for logRec in self.logRecordBuffer:
            msg = self.format(logRec)
            if logRec.args:
                args = "".join([' {0}="{1}"'.format(n, v.replace('"','&quot;')) 
                                for n, v in logRec.args.items()
                                if v])  # skip empty arguments, they won't show in the message strings 
            else:
                args = ""
            xml.append('<entry code="{0}" level="{1}" file="{2}" sourceLine="{3}"><message{4}>{5}</message></entry>'.format(
                    logRec.messageCode, logRec.levelname.lower(), logRec.file, logRec.sourceLine, args, msg.replace("&","&amp;").replace("<","&lt;")))
        xml.append('</log>')  
        self.logRecordBuffer = []
        return '\n'.join(xml)
    
    def getJson(self):
        entries = []
        for logRec in self.logRecordBuffer:
            message = { "text": self.format(logRec) }
            if logRec.args:
                for n, v in logRec.args.items():
                    message[n] = v
            entry = {"code": logRec.messageCode,
                     "level": logRec.levelname.lower(),
                     "file": logRec.file,
                     "sourceLine": logRec.sourceLine,
                     "message": message}
            entries.append(entry)
        self.logRecordBuffer = []
        return json.dumps( {"log": entries} )
    
    def getLines(self):
        lines = [self.format(logRec) for logRec in self.logRecordBuffer]
        self.logRecordBuffer = []
        return lines
    
    def getText(self, separator='\n'):
        return separator.join(self.getLines())
    
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)



