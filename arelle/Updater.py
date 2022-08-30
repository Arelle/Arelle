"""
Created on May 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
"""
from __future__ import annotations

import gettext
import os
import subprocess
import sys
import threading
import tkinter.messagebox
import typing

from arelle import Version

if typing.TYPE_CHECKING:
    from arelle.CntlrWinMain import CntlrWinMain

_ = gettext.gettext

_MESSAGE_HEADER = "arelle\u2122 - Updater"


def checkForUpdates(cntlr: CntlrWinMain) -> None:
    thread = threading.Thread(target=lambda c=cntlr: backgroundCheckForUpdates(c))
    thread.daemon = True
    thread.start()


def backgroundCheckForUpdates(cntlr: CntlrWinMain) -> None:
    if cntlr.updateURL is None:
        _showInfo(
            cntlr,
            _(
                """
                Operating system not supported by update checker.
                Please go to arelle.org to check for updates.
                """
            ),
        )
        return
    if cntlr.webCache.workOffline:
        _showInfo(cntlr, _("Disable offline mode to check for updates."))
        return
    cntlr.showStatus(_("Checking for updates to Arelle"))
    try:
        attachmentFileName = cntlr.webCache.getAttachmentFilename(cntlr.updateURL)
        if attachmentFileName:
            cntlr.showStatus("")  # clear web loading status entry
            cntlr.uiThreadQueue.put((checkUpdateUrl, [cntlr, attachmentFileName]))
    except:
        pass
    cntlr.showStatus("")  # clear web loading status entry


def checkUpdateUrl(cntlr: CntlrWinMain, attachmentFileName: str) -> None:
    # get latest header file
    try:
        filename = os.path.basename(attachmentFileName)
        if filename and "-20" in filename:
            i = filename.index("-20") + 1
            filenameDate = filename[i : i + 10]
            versionDate = Version.version[0:10]
            if filenameDate > versionDate:
                # newer
                reply = tkinter.messagebox.askokcancel(
                    _(_MESSAGE_HEADER),
                    _(
                        "Update {0} is available, running version is {1}.  \n\nDownload now?    \n\n(Arelle will exit before installing.)"
                    ).format(filenameDate, versionDate),
                    parent=cntlr.parent,
                )
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


def backgroundDownload(cntlr: CntlrWinMain, url: str) -> None:
    filepathTmp = cntlr.webCache.getfilename(cntlr.updateURL, reload=True)
    if not filepathTmp:
        _showWarning(cntlr, _("Failed to download update."))
        return
    cntlr.modelManager.showStatus(_("Download completed"), 5000)
    filepath = os.path.join(os.path.dirname(filepathTmp), os.path.basename(url))
    os.rename(filepathTmp, filepath)
    cntlr.uiThreadQueue.put((install, [cntlr, filepath]))


def install(cntlr: CntlrWinMain, filepath: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(filepath)
    else:
        if sys.platform in ("darwin", "macos"):
            command = "open"
        else:  # linux/unix
            command = "xdg-open"
        try:
            subprocess.Popen([command, filepath])
        except:
            pass
    cntlr.uiThreadQueue.put((cntlr.quit, []))


def _showInfo(cntlr: CntlrWinMain, msg: str) -> None:
    tkinter.messagebox.showinfo(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)


def _showWarning(cntlr: CntlrWinMain, msg: str) -> None:
    tkinter.messagebox.showwarning(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)
