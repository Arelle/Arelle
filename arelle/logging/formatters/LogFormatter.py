"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any


class LogFormatter(logging.Formatter):
    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super(LogFormatter, self).__init__(fmt, datefmt)

    def fileLines(self, record: logging.LogRecord) -> str:
        # provide a file parameter made up from refs entries
        return logRefsFileLines(getattr(record, "refs", []))

    def format(self, record: logging.LogRecord) -> str:
        record.file = self.fileLines(record)
        try:
            formattedMessage = super(LogFormatter, self).format(record)
        except (KeyError, TypeError, ValueError) as ex:
            formattedMessage = "Message: "
            if getattr(record, "messageCode", ""):
                formattedMessage += "[{0}] ".format(getattr(record, "messageCode", ""))
            if getattr(record, "msg", ""):
                formattedMessage += record.msg + " "
            if isinstance(record.args, dict) and 'error' in record.args: # args may be list or empty
                formattedMessage += record.args['error']
            formattedMessage += " \nMessage log error: " + str(ex)
        if hasattr(record, "file"):
            delattr(record, "file")
        return formattedMessage


def logRefsFileLines(refs: list[dict[str, Any]]) -> str:
    fileLines = defaultdict(set)
    for ref in refs:
        href = ref.get("href")
        if href:
            hrefWithoutFakeIxdsPrefix = href.rpartition("_IXDS#?#")[2]
            fileLines[hrefWithoutFakeIxdsPrefix.partition("#")[0]].add(ref.get("sourceLine") or 0)
    return ", ".join(file + " " + ', '.join(str(line)
                                            for line in sorted(lines, key=lambda l: l)
                                            if line)
                     for file, lines in sorted(fileLines.items()))
