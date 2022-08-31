from __future__ import annotations

import queue
from unittest.mock import Mock, call, patch

import pytest

from arelle import Updater

OLD_FILENAME = "arelle-macOS-2021-01-01.dmg"
NEW_FILENAME = "arelle-macOS-2022-01-01.dmg"

OLD_VERSION = "2021-01-01 12:00 UTC"
NEW_VERSION = "2022-01-01 12:00 UTC"

DOWNLOAD_URL = "https://arelle.org/download/X"


def _mockCntlrWinMain(
    updateUrl: str | None = DOWNLOAD_URL,
    workOffline: bool = False,
    updateFilename: str | RuntimeError | None = OLD_FILENAME,
):
    webCache = Mock(
        getAttachmentFilename=Mock(side_effect=[updateFilename]),
        getfilename=Mock(side_effect=[updateFilename]),
        workOffline=workOffline,
    )
    return Mock(
        uiThreadQueue=queue.Queue(),
        updateURL=updateUrl,
        webCache=webCache,
    )


class TestUpdater:
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain()

        Updater._checkForUpdates(cntlr)

        assert not showInfo.called
        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._checkUpdateUrl,
            [cntlr, OLD_FILENAME],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    def test_check_for_updates_no_update_url(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain(
            updateUrl=None,
        )

        Updater._checkForUpdates(cntlr)

        assert showInfo.called
        assert not showWarning.called
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
    def test_check_for_updates_attachment_exception(self, showWarning, showInfo):
        cntlr = _mockCntlrWinMain(
            updateFilename=RuntimeError(),
        )

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
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        cntlr = _mockCntlrWinMain()
        newFilename = NEW_FILENAME
        version.version = OLD_VERSION
        askokcancel.return_value = True

        Updater._checkUpdateUrl(cntlr, newFilename)

        assert not showInfo.called
        assert not showWarning.called
        assert askokcancel.called
        assert backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_user_no_install(
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        cntlr = _mockCntlrWinMain()
        newFilename = NEW_FILENAME
        version.version = OLD_VERSION
        askokcancel.return_value = False

        Updater._checkUpdateUrl(cntlr, newFilename)

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
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        cntlr = _mockCntlrWinMain()
        newFilename = OLD_FILENAME
        version.version = NEW_VERSION

        Updater._checkUpdateUrl(cntlr, newFilename)

        assert showInfo.called
        assert not showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_update_same(
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        cntlr = _mockCntlrWinMain()
        newFilename = NEW_FILENAME
        version.version = NEW_VERSION

        Updater._checkUpdateUrl(cntlr, newFilename)

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
        cntlr = _mockCntlrWinMain()
        newFilename = NEW_FILENAME
        version.version = "invalid version string"

        Updater._checkUpdateUrl(cntlr, newFilename)

        assert not showInfo.called
        assert showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showwarning")
    @patch("tkinter.messagebox.askokcancel")
    @patch("arelle.Updater.Version")
    @patch("arelle.Updater._backgroundDownload")
    def test_check_update_url_fail_parse_update(
        self, backgroundDownload, version, askokcancel, showWarning, showInfo
    ):
        cntlr = _mockCntlrWinMain()
        newFilename = "filename-without-version-string"
        version.version = OLD_VERSION

        Updater._checkUpdateUrl(cntlr, newFilename)

        assert not showInfo.called
        assert showWarning.called
        assert not askokcancel.called
        assert not backgroundDownload.called

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download(self, showWarning, rename):
        cntlr = _mockCntlrWinMain(
            updateFilename=NEW_FILENAME,
        )

        Updater._download(cntlr, DOWNLOAD_URL)

        assert not showWarning.called
        assert not cntlr.uiThreadQueue.empty()
        assert cntlr.uiThreadQueue.get_nowait() == (
            Updater._install,
            [cntlr, "X"],
        )
        assert cntlr.uiThreadQueue.empty()

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download_failed(self, showWarning, rename):
        cntlr = _mockCntlrWinMain(
            updateFilename=None,
        )

        Updater._download(cntlr, DOWNLOAD_URL)

        assert showWarning.called
        assert cntlr.uiThreadQueue.empty()

    @patch("os.rename")
    @patch("tkinter.messagebox.showwarning")
    def test_download_process_failed(self, showWarning, rename):
        cntlr = _mockCntlrWinMain(
            updateFilename=NEW_FILENAME,
        )
        rename.side_effect = OSError()

        Updater._download(cntlr, DOWNLOAD_URL)

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
