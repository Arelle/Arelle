'''
Created on May 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import tkinter.messagebox, webbrowser, os, threading

def checkForUpdates(cntlr):
    if not cntlr.webCache.workOffline:
        # check for updates in background
        import threading
        thread = threading.Thread(target=lambda c=cntlr: backgroundCheckForUpdates(c))
        thread.daemon = True
        thread.start()

def backgroundCheckForUpdates(cntlr):
    actualUrl = None
    cntlr.showStatus(_("Checking for updates to Arelle")) 
    try:
        actualUrl = cntlr.webCache.geturl(cntlr.updateURL)
        if actualUrl:
            cntlr.showStatus("") # clear web loading status entry 
            cntlr.uiThreadQueue.put((checkUpdateUrl, [cntlr, actualUrl]))
    except:
        cntlr.showStatus("") # clear web loading status entry 

def checkUpdateUrl(cntlr, actualUrl):    
    # get latest header file
    try:
        from arelle import WebCache, Version
        filename = os.path.basename(actualUrl)
        if filename and "-20" in filename:
            i = filename.index("-20") + 1
            filenameDate = filename[i:i+10]
            versionDate = Version.version[0:10]
            if filenameDate > versionDate:
                # newer
                reply = tkinter.messagebox.askyesnocancel(
                            _("arelle\u2122 - Updater"),
                            _("Update {0} is available, running version is {1}.  \n\nDownload now?    \n\n(Arelle will exit before installing.)").format(
                                  filenameDate, versionDate), 
                            parent=cntlr.parent)
                if reply is None:
                    return False
                if reply:
                    thread = threading.Thread(target=lambda u=actualUrl: backgroundDownload(cntlr, u))
                    thread.daemon = True
                    thread.start()
            else:
                if filenameDate < versionDate:
                    msg = _("Arelle running version, {0}, is newer than the downloadable version, {1}.").format(
                              versionDate, filenameDate)
                else:
                    msg = _("Arelle running version, {0}, is the same as the downloadable version.").format(
                              versionDate)
                tkinter.messagebox.showwarning(_("arelle\u2122 - Updater"), msg, parent=cntlr.parent) 
                                
    except:
        pass
    
    return

def backgroundDownload(cntlr, url):
    filepathtmp = cntlr.webCache.getfilename(cntlr.updateURL, reload=True)
    cntlr.modelManager.showStatus(_("Download ompleted"), 5000)
    filepath = os.path.join(os.path.dirname(filepathtmp), os.path.basename(url))
    os.rename(filepathtmp, filepath)
    cntlr.uiThreadQueue.put((install, [cntlr,filepath]))
    
def install(cntlr,filepath):
    import sys
    if sys.platform.startswith("win"):
        os.startfile(filepath)
    else:
        if sys.platform in ("darwin", "macos"):
            command = 'open'
        else: # linux/unix
            command = 'xdg-open'
        try:
            import subprocess
            subprocess.Popen([command,filepath])
        except:
            pass
    cntlr.uiThreadQueue.put((cntlr.quit, []))
