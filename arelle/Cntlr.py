'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import tempfile, os, pickle, sys
from arelle import (ModelManager, WebCache)

class Cntlr:

    __version__ = "0.0.4"
    
    def __init__(self):
        if sys.platform == "darwin":
            self.userAppDir = os.path.expanduser("~") + "/Library/Application Support/Arelle"
            self.contextMenuClick = "<Button-2>"
            self.hasClipboard = True
            self.updateURL = "http://arelle.org/downloads/8"
        elif sys.platform.startswith("win"):
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
            self.contextMenuClick = "<Button-3>"
            if "64 bit" in sys.version:
                self.updateURL = "http://arelle.org/downloads/9"
            else: # 32 bit
                self.updateURL = "http://arelle.org/downloads/10"
        else: # Unix/Linux
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
        elif self.moduleDir.endswith("library.zip\\arelle"): # cx_Freexe
            resources = os.path.dirname(os.path.dirname(self.moduleDir))
            self.configDir = os.path.join(resources, "config")
            self.imagesDir = os.path.join(resources, "images")
        else:
            self.configDir = os.path.join(self.moduleDir, "config")
            self.imagesDir = os.path.join(self.moduleDir, "images")
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
        from arelle.WebCache import WebCache
        self.webCache = WebCache(self, self.config.get("proxySettings"))
        self.modelManager = ModelManager.initialize(self)
            
    def close(self):
        self.saveConfig()
        
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



