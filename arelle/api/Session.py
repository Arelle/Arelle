"""
See COPYRIGHT.md for copyright information.

The `arelle.api` module is the supported method for integrating Arelle into other Python applications.
"""
from __future__ import annotations

import logging
import threading
from types import TracebackType
from typing import Any, BinaryIO, TypeVar

from arelle import PackageManager, PluginManager
from arelle.CntlrCmdLine import CntlrCmdLine, createCntlrAndPreloadPlugins
from arelle.FileSource import FileNamedBytesIO
from arelle.ModelXbrl import ModelXbrl
from arelle.RuntimeOptions import RuntimeOptions

_session_lock = threading.Lock()

# typing.Self can be used once Python 3.10 support is dropped.
Self = TypeVar("Self", bound="Session")


class Session:
    """
    CRITICAL THREAD SAFETY WARNING:

    Arelle uses shared global state (PackageManager, PluginManager) which is NOT thread-safe.
    Only ONE Session can run at a time across the entire process.

    Safe usage:
    - Use one Session at a time per process
    - Use a process pool instead of thread pool for parallelism

    Unsafe usage:
    - Running multiple Sessions concurrently in any threads
    - Threading.Thread with Session.run()
    """

    def __init__(self) -> None:
        self._cntlr: CntlrCmdLine | None = None
        self._thread_id = threading.get_ident()

    def _check_thread(self) -> None:
        """Ensure session is only used from the thread that created it."""
        if threading.get_ident() != self._thread_id:
            raise RuntimeError(
                "Session objects cannot be shared between threads. Create a new Session instance in each thread."
            )

    def __enter__(self: Self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        with _session_lock:
            self._check_thread()
            if self._cntlr is not None:
                self._cntlr.close()
            PluginManager.close()

    def get_log_messages(self) -> list[dict[str, Any]]:
        """
        :return: Raw log records (messages) from the session.
        """
        if not self._cntlr or not self._cntlr.logHandler:
            return []
        return getattr(self._cntlr.logHandler, 'messages', [])

    def get_logs(self, log_format: str, clear_logs: bool = False) -> str:
        """
        Retrieve logs as a string in the configured format.
        Raises a `ValueError` if the log format is not supported by the current log handler.
        Optionally clear the log buffer after retrieving.
        :param log_format: The format to retrieve logs in. Supported formats are 'json', 'text', and 'xml'.
        :param clear_logs: If enabled, clears the log buffer after retrieving logs.
        :return:
        """
        if self._cntlr:
            handler = self._cntlr.logHandler
            if log_format == 'json' and hasattr(handler, 'getJson'):
                return str(handler.getJson(clearLogBuffer=clear_logs))
            if log_format == 'text' and hasattr(handler, 'getText'):
                return str(handler.getText(clearLogBuffer=clear_logs))
            if log_format == 'xml' and hasattr(handler, 'getXml'):
                return str(handler.getXml(clearLogBuffer=clear_logs, includeDeclaration=False))
            raise ValueError('Unsupported log format for {}: {}'.format(type(handler).__name__, log_format))
        return ""

    def get_models(self) -> list[ModelXbrl]:
        """
        Retrieve a list of loaded models.
        """
        if self._cntlr is None:
            return []
        return self._cntlr.modelManager.loadedModelXbrls

    def run(
        self,
        options: RuntimeOptions,
        sourceZipStream: BinaryIO | FileNamedBytesIO | None = None,
        responseZipStream: BinaryIO | None = None,
        logHandler: logging.Handler | None = None,
        logFilters: list[logging.Filter] | None = None,
    ) -> bool:
        """
        Perform a run using the given options.
        :param options: Options to use for the run.
        :param sourceZipStream: Optional stream to read source data from.
        :param responseZipStream: Options stream to write response data to.
        :param logHandler: Optional log handler to use for logging.
        :return: True if the run was successful, False otherwise.
        """
        with _session_lock:
            self._check_thread()
            PackageManager.reset()
            PluginManager.reset()
            if self._cntlr is None:
                # Certain options must be passed into the controller constructor to have the intended effect
                self._cntlr = createCntlrAndPreloadPlugins(
                    uiLang=options.uiLang,
                    disablePersistentConfig=options.disablePersistentConfig,
                    arellePluginModules={},
                )
            else:
                # Certain options passed into the controller constructor need to be updated
                if self._cntlr.uiLang != options.uiLang:
                    self._cntlr.setUiLanguage(options.uiLang)
                self._cntlr.disablePersistentConfig = options.disablePersistentConfig or False
            logRefObjectProperties = True
            if options.logRefObjectProperties is not None:
                logRefObjectProperties = options.logRefObjectProperties
            if options.webserver:
                assert sourceZipStream is None, "Source streaming is not supported with webserver"
                assert responseZipStream is None, "Response streaming is not supported with webserver"
                if not self._cntlr.logger:
                    self._cntlr.startLogging(
                        logFileName='logToBuffer',
                        logFilters=logFilters,
                        logHandler=logHandler,
                        logTextMaxLength=options.logTextMaxLength,
                        logRefObjectProperties=logRefObjectProperties,
                        logPropagate=options.logPropagate,
                    )
                    self._cntlr.postLoggingInit()
                from arelle import CntlrWebMain
                CntlrWebMain.startWebserver(self._cntlr, options)
                return True
            else:
                if not self._cntlr.logger:
                    self._cntlr.startLogging(
                        logFileName=(options.logFile or "logToPrint"),
                        logFileMode=options.logFileMode,
                        logFormat=(options.logFormat or "[%(messageCode)s] %(message)s - %(file)s"),
                        logLevel=(options.logLevel or "DEBUG"),
                        logFilters=logFilters,
                        logHandler=logHandler,
                        logToBuffer=options.logFile == 'logToBuffer',
                        logTextMaxLength=options.logTextMaxLength,  # e.g., used by EDGAR/render to require buffered logging
                        logRefObjectProperties=logRefObjectProperties,
                        logXmlMaxAttributeLength=options.logXmlMaxAttributeLength,
                        logPropagate=options.logPropagate,
                    )
                    self._cntlr.postLoggingInit()  # Cntlr options after logging is started
                return self._cntlr.run(
                    options,
                    sourceZipStream=sourceZipStream,
                    responseZipStream=responseZipStream,
                )
