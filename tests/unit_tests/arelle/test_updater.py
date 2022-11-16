from __future__ import annotations

import json
import os.path
import queue
from collections.abc import Mapping
from types import MappingProxyType
from unittest.mock import Mock, call, patch
from urllib.error import URLError

import pytest

from arelle import Updater
from arelle.Updater import ArelleRelease, ArelleVersion

MACOS_DOWNLOAD_URL = (
    "https://github.com/Arelle/Arelle/releases/download/2.1.3/arelle-macos-2.1.3.dmg"
)
WINDOWS_DOWNLOAD_URL = (
    "https://github.com/Arelle/Arelle/releases/download/2.1.3/arelle-win-2.1.3.exe"
)
OTHER_DOWNLOAD_URL = "https://github.com/Arelle/Arelle/releases/download/2.1.3/arelle-release-2.1.3.tar.gz"

OLD_ARELLE_VERSION = ArelleVersion(major=2, minor=0, patch=0)
NEW_ARELLE_VERSION = ArelleVersion(major=2, minor=1, patch=3)
OLD_SEMVER_VERSION = str(OLD_ARELLE_VERSION)
NEW_SEMVER_VERSION = str(NEW_ARELLE_VERSION)


def _mockGitHubRelease(
    tagName: str = NEW_SEMVER_VERSION,
    assetUrls: tuple[str] = (
        MACOS_DOWNLOAD_URL,
        WINDOWS_DOWNLOAD_URL,
        OTHER_DOWNLOAD_URL,
    ),
):
    return {
        "tag_name": tagName,
        "assets": [{"browser_download_url": url} for url in assetUrls],
    }


def _mockCntlrWinMain(
    updateTagName: str = NEW_SEMVER_VERSION,
    githubRelease: Mapping[str, str | list[Mapping[str, str]]]
    | URLError = MappingProxyType(_mockGitHubRelease()),
    workOffline: bool = False,
    tmpDownloadFilename: str | RuntimeError | None = os.path.normcase("/tmp/tmpfile"),
):
    if isinstance(githubRelease, Mapping):

        def downloadWriter(*args, **kwargs):
            jsonResponse = json.dumps(dict(githubRelease)).encode("utf-8")
            kwargs["filestream"].write(jsonResponse)
            kwargs["filestream"].seek(0)

        release = downloadWriter
    else:
        release = githubRelease
    webCache = Mock(
        retrieve=Mock(side_effect=release),
        getfilename=Mock(side_effect=[tmpDownloadFilename]),
        workOffline=workOffline,
    )
    return Mock(
        uiThreadQueue=queue.Queue(),
        webCache=webCache,
    )


class TestArelleVersion:
    @pytest.mark.parametrize(
        "olderVersion, newerVersion",
        [
            (
                ArelleVersion(major=0, minor=0, patch=0),
                ArelleVersion(major=0, minor=0, patch=1),
            ),
            (
                ArelleVersion(major=0, minor=0, patch=9),
                ArelleVersion(major=0, minor=1, patch=0),
            ),
            (
                ArelleVersion(major=0, minor=9, patch=9),
                ArelleVersion(major=1, minor=0, patch=0),
            ),
            (
                ArelleVersion(major=1, minor=1, patch=3),
                ArelleVersion(major=1, minor=1, patch=10),
            ),
            (
                ArelleVersion(major=1, minor=2, patch=9),
                ArelleVersion(major=1, minor=10, patch=1),
            ),
            (
                ArelleVersion(major=2, minor=9, patch=9),
                ArelleVersion(major=10, minor=1, patch=1),
            ),
        ],
    )
    def test_arelleVersionCompare(self, olderVersion, newerVersion):
        assert olderVersion < newerVersion


class TestUpdater:
    @patch("sys.platform", "darwin")
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_macos(self, showWarning, showInfo):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._checkUpdateUrl,
            [cntlr, arelleRelease],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "win32")
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_windows(self, showWarning, showInfo):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=WINDOWS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._checkUpdateUrl,
            [cntlr, arelleRelease],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "linux")
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_linux(self, showWarning, showInfo):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=None,
        )
        cntlr = _mockCntlrWinMain()

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._checkUpdateUrl,
            [cntlr, arelleRelease],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_work_offline(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain(
            workOffline=True,
        )

        Updater._checkForUpdates(cntlr)

        assert showInfo.called
        assert not showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_api_error(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain(
            githubRelease=URLError("API Error"),
        )

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_api_parse_error(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain(githubRelease=_mockGitHubRelease(tagName="badTag"))

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_user_install(
            self,
            backgroundDownload,
            version,
            askokcancel,
            showWarning,
            showInfo,
    ):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        version.version = OLD_SEMVER_VERSION
        askokcancel.return_value = True

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert not showInfo.called
        assert not showWarning.called
        assert askokcancel.called
        assert backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_no_url(
        self,
        backgroundDownload,
        version,
        askokcancel,
        showWarning,
        showInfo,
    ):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl="",
        )
        cntlr = _mockCntlrWinMain()
        version.version = OLD_SEMVER_VERSION
        askokcancel.return_value = True

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert showInfo.called
        assert not showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_user_no_install(
        self,
        backgroundDownload,
        version,
        askokcancel,
        showWarning,
        showInfo,
    ):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        version.version = OLD_SEMVER_VERSION
        askokcancel.return_value = False

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert not showInfo.called
        assert not showWarning.called
        assert askokcancel.called
        assert not backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_older(
        self,
        backgroundDownload,
        version,
        askokcancel,
        showWarning,
        showInfo,
    ):
        arelleRelease = ArelleRelease(
            version=OLD_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        version.version = NEW_SEMVER_VERSION

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert showInfo.called
        assert not showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @pytest.mark.parametrize(
        "currentVersion, updateVersion",
        [
            (OLD_SEMVER_VERSION, OLD_ARELLE_VERSION),
            (NEW_SEMVER_VERSION, NEW_ARELLE_VERSION),
        ],
    )
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_same(
        self,
        backgroundDownload,
        version,
        askokcancel,
        showWarning,
        showInfo,
        currentVersion,
        updateVersion,
    ):
        arelleRelease = ArelleRelease(
            version=updateVersion,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        version.version = currentVersion

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert showInfo.called
        assert not showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_fail_parse_current(
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        version.version = "invalid version string"

        Updater._checkUpdateUrl(cntlr, arelleRelease)

        assert not showInfo.called
        assert showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download(self, showWarning, rename):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain(
            tmpDownloadFilename=os.path.normcase("/tmp/path/tmpfile"),
        )

        Updater._download(cntlr, arelleRelease)

        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._install,
            [cntlr, os.path.normcase("/tmp/path/arelle-macos-2.1.3.dmg")],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download_no_release_url(self, showWarning, rename):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl="",
        )
        cntlr = _mockCntlrWinMain()

        with pytest.raises(RuntimeError):
            Updater._download(cntlr, arelleRelease)

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download_failed(self, showWarning, rename):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain(
            tmpDownloadFilename=None,
        )

        Updater._download(cntlr, arelleRelease)

        assert showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download_process_failed(self, showWarning, rename):
        arelleRelease = ArelleRelease(
            version=NEW_ARELLE_VERSION,
            downloadUrl=MACOS_DOWNLOAD_URL,
        )
        cntlr = _mockCntlrWinMain()
        rename.side_effect = OSError()

        Updater._download(cntlr, arelleRelease)

        assert showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "win32")
    @patch("subprocess.Popen")
    @patch("os.startfile", create=True)
    @patch("tkinter.messagebox.showwarning")
    def test_install_windows(self, showWarning, startfile, Popen):
        cntlr = _mockCntlrWinMain()
        filepath = "filepath"

        Updater._install(cntlr, filepath)

        assert not showWarning.called
        assert startfile.called
        assert startfile.call_args == call(filepath)
        assert not Popen.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (cntlr.quit, [])
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "darwin")
    @patch("subprocess.Popen")
    @patch("os.startfile", create=True)
    @patch("tkinter.messagebox.showwarning")
    def test_install_mac(self, showWarning, startfile, Popen):
        cntlr = _mockCntlrWinMain()
        filepath = "filepath"

        Updater._install(cntlr, filepath)

        assert not showWarning.called
        assert not startfile.called
        assert Popen.called
        assert Popen.call_args == call(["open", filepath])
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (cntlr.quit, [])
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "darwin")
    @patch("subprocess.Popen")
    @patch("os.startfile", create=True)
    @patch("tkinter.messagebox.showwarning")
    def test_install_mac_exception(self, showWarning, startfile, Popen):
        cntlr = _mockCntlrWinMain()
        filepath = "filepath"
        Popen.side_effect = OSError()

        Updater._install(cntlr, filepath)

        assert showWarning.called
        assert not startfile.called
        assert Popen.called
        assert Popen.call_args == call(["open", filepath])
        assert cntlr.uiThreadQueue.empty()

    @patch("sys.platform", "linux")
    @patch("subprocess.Popen")
    @patch("os.startfile", create=True)
    @patch("tkinter.messagebox.showwarning")
    def test_install_unsupported_platform(self, showWarning, startfile, Popen):
        cntlr = _mockCntlrWinMain()
        filepath = "filepath"

        with pytest.raises(RuntimeError) as e:
            Updater._install(cntlr, filepath)

        assert not showWarning.called
        assert not startfile.called
        assert not Popen.called
        assert cntlr.uiThreadQueue.empty()
