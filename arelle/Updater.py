"""
Created on May 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
"""
import os
import threading
import tkinter.messagebox

_MESSAGE_HEADER = "arelle\u2122 - Updater"


def checkForUpdates(cntlr):
    if not cntlr.webCache.workOffline:
        # check for updates in background
        import threading

        thread = threading.Thread(target=lambda c=cntlr: backgroundCheckForUpdates(c))
        thread.daemon = True
        thread.start()


def backgroundCheckForUpdates(cntlr):
    cntlr.showStatus(_("Checking for updates to Arelle"))
    try:
        attachmentFileName = cntlr.webCache.getAttachmentFilename(cntlr.updateURL)
        if attachmentFileName:
            cntlr.showStatus("")  # clear web loading status entry
            cntlr.uiThreadQueue.put((checkUpdateUrl, [cntlr, attachmentFileName]))
    except:
        pass
    cntlr.showStatus("")  # clear web loading status entry


def checkUpdateUrl(cntlr, attachmentFileName):
    # get latest header file
    try:
        from arelle import WebCache, Version

        filename = os.path.basename(attachmentFileName)
        if filename and "-20" in filename:
            i = filename.index("-20") + 1
            filenameDate = filename[i : i + 10]
            versionDate = Version.version[0:10]
            if filenameDate > versionDate:
                # newer
                reply = tkinter.messagebox.askyesnocancel(
                    _(_MESSAGE_HEADER),
                    _(
                        "Update {0} is available, running version is {1}.  \n\nDownload now?    \n\n(Arelle will exit before installing.)"
                    ).format(filenameDate, versionDate),
                    parent=cntlr.parent,
                )
                if reply is None:
                    return
                if reply:
                    thread = threading.Thread(
                        target=lambda u=attachmentFileName: backgroundDownload(cntlr, u)
                    )
                    thread.daemon = True
                    thread.start()
            else:
                if filenameDate < versionDate:
                    msg = _(
                        "Arelle running version, {0}, is newer than the downloadable version, {1}."
                    ).format(versionDate, filenameDate)
                else:
                    msg = _(
                        "Arelle running version, {0}, is the same as the downloadable version."
                    ).format(versionDate)
                _showInfo(cntlr, msg)
    except:
        pass


def backgroundDownload(cntlr, url):
    filepathTmp = cntlr.webCache.getfilename(cntlr.updateURL, reload=True)
    if not filepathTmp:
        _showWarning(cntlr, _("Failed to download update."))
        return
    cntlr.modelManager.showStatus(_("Download completed"), 5000)
    filepath = os.path.join(os.path.dirname(filepathTmp), os.path.basename(url))
    os.rename(filepathTmp, filepath)
    cntlr.uiThreadQueue.put((install, [cntlr, filepath]))


def install(cntlr, filepath):
    import sys

    if sys.platform.startswith("win"):
        os.startfile(filepath)
    else:
        if sys.platform in ("darwin", "macos"):
            command = "open"
        else:  # linux/unix
            command = "xdg-open"
        try:
            import subprocess

            subprocess.Popen([command, filepath])
        except:
            pass
    cntlr.uiThreadQueue.put((cntlr.quit, []))


def _showInfo(cntlr, msg):
    tkinter.messagebox.showinfo(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)


def _showWarning(cntlr, msg):
    tkinter.messagebox.showwarning(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)
