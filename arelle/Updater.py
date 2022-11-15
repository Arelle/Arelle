"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter.messagebox
from dataclasses import dataclass
from typing import TYPE_CHECKING

import regex

from arelle import Version
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.CntlrWinMain import CntlrWinMain

_: TypeGetText

_MESSAGE_HEADER = "arelle\u2122 - Updater"
_SEMVER_PATTERN = regex.compile(
    r"(?P<semver>(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+))"
)


@dataclass(eq=True, frozen=True, order=True)
class ArelleVersion:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def checkForUpdates(cntlr: CntlrWinMain) -> None:
    thread = threading.Thread(daemon=True, target=lambda c=cntlr: _checkForUpdates(c))
    thread.start()


def _checkForUpdates(cntlr: CntlrWinMain) -> None:
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
    except RuntimeError as e:
        _showWarning(
            cntlr,
            _("Failed to check for updates. URL {0}, {1}").format(cntlr.updateURL, e),
        )
        return
    finally:
        cntlr.showStatus("")  # clear web loading status entry
    cntlr.uiThreadQueue.put((_checkUpdateUrl, [cntlr, attachmentFileName]))


def _checkUpdateUrl(cntlr: CntlrWinMain, attachmentFileName: str) -> None:
    filename = os.path.basename(attachmentFileName)
    try:
        currentVersion = _parseVersion(Version.version)
    except ValueError:
        _showWarning(cntlr, _("Unable to determine current version of Arelle."))
        return
    try:
        updateVersion = _parseVersion(filename)
    except ValueError:
        _showWarning(cntlr, _("Unable to determine version of Arelle update."))
        return
    if updateVersion > currentVersion:
        reply = tkinter.messagebox.askokcancel(
            _(_MESSAGE_HEADER),
            _(
                """
                Update {0} is available, current version is {1}.

                Download now?

                (Arelle will exit before installing.)
                """
            ).format(updateVersion, currentVersion),
            parent=cntlr.parent,
        )
        if reply:
            _backgroundDownload(cntlr, attachmentFileName)
    elif updateVersion < currentVersion:
        _showInfo(
            cntlr,
            _("Current Arelle version {0} is newer than update {1}.").format(
                currentVersion, updateVersion
            ),
        )
    else:
        _showInfo(
            cntlr,
            _("Arelle is already running the latest version {0}.").format(
                currentVersion
            ),
        )


def _parseVersion(versionStr: str) -> ArelleVersion:
    semverMatch = _SEMVER_PATTERN.search(versionStr)
    if semverMatch:
        return ArelleVersion(
            major=int(semverMatch.group("major")),
            minor=int(semverMatch.group("minor")),
            patch=int(semverMatch.group("patch")),
        )
    raise ValueError(f"Unable to parse version from {versionStr}")


def _backgroundDownload(cntlr: CntlrWinMain, attachmentFileName: str) -> None:
    thread = threading.Thread(
        daemon=True, target=lambda u=attachmentFileName: _download(cntlr, u)
    )
    thread.start()


def _download(cntlr: CntlrWinMain, url: str) -> None:
    filepathTmp = cntlr.webCache.getfilename(cntlr.updateURL, reload=True)
    if not filepathTmp:
        _showWarning(cntlr, _("Failed to download update."))
        return
    cntlr.showStatus(_("Download completed"), 5000)
    filepath = os.path.join(os.path.dirname(filepathTmp), os.path.basename(url))
    try:
        os.rename(filepathTmp, filepath)
    except OSError:
        _showWarning(cntlr, _("Failed to process update."))
        return
    cntlr.uiThreadQueue.put((_install, [cntlr, filepath]))


def _install(cntlr: CntlrWinMain, filepath: str) -> None:
    if sys.platform == "win32":
        os.startfile(filepath)
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", filepath])
        except (OSError, subprocess.SubprocessError):
            _showWarning(cntlr, _("Failed to start updated Arelle instance."))
            return
    else:
        raise RuntimeError("Tried to install update on unsupported platform.")
    cntlr.uiThreadQueue.put((cntlr.quit, []))


def _showInfo(cntlr: CntlrWinMain, msg: str) -> None:
    tkinter.messagebox.showinfo(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)


def _showWarning(cntlr: CntlrWinMain, msg: str) -> None:
    tkinter.messagebox.showwarning(_(_MESSAGE_HEADER), msg, parent=cntlr.parent)
