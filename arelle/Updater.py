"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import tkinter.messagebox
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from urllib.error import URLError

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
_UPDATE_URL = "https://api.github.com/repos/Arelle/Arelle/releases/latest"


@dataclass(eq=True, frozen=True, order=True)
class ArelleVersion:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(eq=True, frozen=True, order=True)
class ArelleRelease:
    version: ArelleVersion
    downloadUrl: str | None


def checkForUpdates(cntlr: CntlrWinMain) -> None:
    thread = threading.Thread(daemon=True, target=lambda c=cntlr: _checkForUpdates(c))
    thread.start()


def _checkForUpdates(cntlr: CntlrWinMain) -> None:
    if cntlr.webCache.workOffline:
        _showInfo(cntlr, _("Disable offline mode to check for updates."))
        return
    cntlr.showStatus(_("Checking for updates to Arelle"))
    try:
        arelleRelease = _getLatestArelleRelease(cntlr)
    except RuntimeError as e:
        _showWarning(
            cntlr,
            _("Failed to check for updates. Try again later. URL {0}, {1}").format(
                _UPDATE_URL, e
            ),
        )
        return
    finally:
        cntlr.showStatus("")  # clear web loading status entry
    cntlr.uiThreadQueue.put((_checkUpdateUrl, [cntlr, arelleRelease]))


def _getLatestArelleRelease(cntlr: CntlrWinMain) -> ArelleRelease:
    try:
        with io.BytesIO() as filestream:
            cntlr.webCache.retrieve(_UPDATE_URL, filestream=filestream)  # type: ignore[no-untyped-call]
            updateResponseJson: dict[str, Any] = json.load(filestream)
    except (URLError, json.JSONDecodeError) as e:
        raise RuntimeError("Failed to get latest Arelle release.") from e
    tagName = updateResponseJson.get("tag_name", "")
    try:
        updateVersion = _parseVersion(tagName)
    except ValueError as e:
        raise RuntimeError(f"Failed to parse version from latest Arelle release {tagName}.") from e
    downloadUrl = _getArelleReleaseDownloadUrl(updateResponseJson.get("assets", []))
    return ArelleRelease(version=updateVersion, downloadUrl=downloadUrl)


def _getArelleReleaseDownloadUrl(assets: list[dict[str, Any]]) -> str | None:
    if sys.platform == "darwin":
        return _getArelleReleaseDownloadUrlByFileExtension(assets, ".dmg")
    elif sys.platform == "win32":
        return _getArelleReleaseDownloadUrlByFileExtension(assets, ".exe")
    else:
        return None


def _getArelleReleaseDownloadUrlByFileExtension(
    assets: list[dict[str, Any]], fileExtension: str
) -> str | None:
    for asset in assets:
        downloadUrl = asset.get("browser_download_url")
        if isinstance(downloadUrl, str) and downloadUrl.endswith(fileExtension):
            return downloadUrl
    return None


def _checkUpdateUrl(cntlr: CntlrWinMain, arelleRelease: ArelleRelease) -> None:
    try:
        currentVersion = _parseVersion(Version.version)
    except ValueError:
        _showWarning(cntlr, _("Unable to determine current version of Arelle."))
        return
    if arelleRelease.version > currentVersion:
        if arelleRelease.downloadUrl:
            reply = tkinter.messagebox.askokcancel(
                _(_MESSAGE_HEADER),
                _(
                    """
                    Update {0} is available, current version is {1}.

                    Download now?

                    (Arelle will exit before installing.)
                    """
                ).format(arelleRelease.version, currentVersion),
                parent=cntlr.parent,
            )
            if reply:
                _backgroundDownload(cntlr, arelleRelease)
        else:
            _showInfo(
                cntlr,
                _(
                    """
                    Update {0} is available, current version is {1}.

                    New version of Arelle can be downloaded at https://arelle.org/arelle/pub/.
                    """
                ).format(arelleRelease.version, currentVersion),
            )
    elif arelleRelease.version < currentVersion:
        _showInfo(
            cntlr,
            _("Current Arelle version {0} is newer than update {1}.").format(
                currentVersion, arelleRelease.version
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


def _backgroundDownload(cntlr: CntlrWinMain, arelleRelease: ArelleRelease) -> None:
    thread = threading.Thread(
        daemon=True, target=lambda: _download(cntlr, arelleRelease)
    )
    thread.start()


def _download(cntlr: CntlrWinMain, arelleRelease: ArelleRelease) -> None:
    if not arelleRelease.downloadUrl:
        raise RuntimeError(f"Arelle can't self-update on platform '{sys.platform}'.")
    filepathTmp = cntlr.webCache.getfilename(arelleRelease.downloadUrl, reload=True)
    if not filepathTmp:
        _showWarning(cntlr, _("Failed to download update."))
        return
    cntlr.showStatus(_("Download completed"), 5000)
    try:
        filepath = os.path.join(
            os.path.dirname(filepathTmp), os.path.basename(arelleRelease.downloadUrl)
        )
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
