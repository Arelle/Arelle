"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
import sys
from typing import TextIO


class LogToPrintHandler(logging.Handler):
    """
    .. class:: LogToPrintHandler()

    A log handler that emits log entries to standard out as they are logged.

    CAUTION: Output is utf-8 encoded, which is fine for saving to files, but may not display correctly in terminal windows.

    :param logOutput: 'logToStdErr' to cause log print to stderr instead of stdout
    :type logOutput: str
    """
    logFile: str | TextIO | None

    def __init__(self, logOutput: str) -> None:
        super(LogToPrintHandler, self).__init__()
        if logOutput == "logToStdErr":
            self.logFile = sys.stderr
        else:
            self.logFile = None

    def emit(self, logRecord: logging.LogRecord) -> None:
        file = sys.stderr if self.logFile else None
        logEntry = self.format(logRecord)
        try:
            print(logEntry, file=file)
        except UnicodeEncodeError:
            # extra parentheses in print to allow for 3-to-2 conversion
            print((logEntry
                   .encode(sys.stdout.encoding, 'backslashreplace')
                   .decode(sys.stdout.encoding, 'strict')),
                  file=file)
