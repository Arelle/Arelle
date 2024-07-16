"""
See COPYRIGHT.md for copyright information.

The Arelle Python Beta API (located in `arelle.api` module) is an in-progress API module.
A roadmap for this API is in development.

Users of this API should expect changes in future releases.
"""
from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Type, BinaryIO

from arelle import PluginManager, PackageManager
from arelle.CntlrCmdLine import CntlrCmdLine, createCntlrAndPreloadPlugins
from arelle.ModelXbrl import ModelXbrl
from arelle.RuntimeOptions import RuntimeOptions


class Session:
    def __init__(self) -> None:
        self._cntlr: CntlrCmdLine | None = None

    def __enter__(self) -> Any:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._cntlr is not None:
            self._cntlr.close()

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
        sourceZipStream: BinaryIO | None = None,
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
                    logTextMaxLength=options.logTextMaxLength,  # e.g., used by EdgarRenderer to require buffered logging
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
