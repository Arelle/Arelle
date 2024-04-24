"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.logging.handlers.LogToXmlHandler import LogToXmlHandler


class LogToBufferHandler(LogToXmlHandler):
    """
    .. class:: LogToBufferHandler()

    A log handler that writes log entries to a memory buffer for later retrieval (to a string) in XML, JSON, or text lines,
    usually for return to a web service or web page call.
    """
    def __init__(self) -> None:
        super(LogToBufferHandler, self).__init__()

    def flush(self) -> None:
        pass # do nothing -- overrides LogToXmlHandler's flush
