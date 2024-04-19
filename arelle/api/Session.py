"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from types import TracebackType
from typing import Any, Type

from arelle.CntlrCmdLine import createCntlrAndPreloadPlugins
from arelle.ModelXbrl import ModelXbrl
from arelle.RuntimeOptions import RuntimeOptions


class Session:
    def __init__(
        self,
        ui_lang: str | None = None,
        disable_persistent_config: bool = False
     ):
        self._cntlr = createCntlrAndPreloadPlugins(
            uiLang=ui_lang,
            disablePersistentConfig=disable_persistent_config,
            arellePluginModules={},
        )

    def __enter__(self) -> Any:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType | None
    ) -> None:
        self._cntlr.close()

    def get_logs(self, clear_logs: bool = False) -> str:
        """
        Retrieve logs as a string in the configured format.
        Optionally clear the log buffer after retrieving.
        :param clear_logs: If enabled, clears the log buffer after retrieving logs.
        :return:
        """
        handler = self._cntlr.logHandler
        if hasattr(handler, 'getXml'):
            return str(handler.getXml(clearLogBuffer=clear_logs, includeDeclaration=False))
        if hasattr(handler, 'getText'):
            return str(handler.getText(clearLogBuffer=clear_logs))
        return ""

    def get_models(self) -> list[ModelXbrl]:
        """
        Retrieve a list of loaded models.
        """
        return self._cntlr.modelManager.loadedModelXbrls

    def run(self, options: RuntimeOptions) -> bool:
        """
        Perform a run using the given options.
        :param options: Options to use for the run.
        :return: True if the run was successful, False otherwise.
        """
        if options.webserver:
            if not self._cntlr.logger:
                self._cntlr.startLogging(
                    logFileName='logToBuffer',
                    logTextMaxLength=options.logTextMaxLength,
                    logRefObjectProperties=options.logRefObjectProperties
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
                    logToBuffer=options.logFile == 'logToBuffer',
                    logTextMaxLength=options.logTextMaxLength,  # e.g., used by EdgarRenderer to require buffered logging
                    logRefObjectProperties=options.logRefObjectProperties
                )
                self._cntlr.postLoggingInit()  # Cntlr options after logging is started
            return self._cntlr.run(options)
