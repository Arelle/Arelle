"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from logging import LogRecord
from typing import Any, Mapping, cast

from arelle.logging.handlers.LogToXmlHandler import LogToXmlHandler

REFS = "refs"
MSG = "msg"
MESSAGE_CODE = "messageCode"
LEVELNAME = "levelname"
ARGS = "args"


class StructuredMessageLogHandler(LogToXmlHandler):
    """
    Custom logging handler to handle logging traffic.
    """

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict[str, Any]] = []

    def flush(self) -> None:
        """
        Nothing to Flush, so this overload causes flush to be a no-op.
        """
        pass

    def emit(self, logRecord: LogRecord) -> None:
        """
        Converts a log record to a map format and adds it to the list of messages

        :param logRecord: The log record to use for the message
        :type logRecord: :class:`~logging.LogRecord`
        :return: None
        :rtype: None
        """
        self.logRecordBuffer.append(logRecord)
        if not logRecord.args or len(logRecord.args) == 0:
            logRecord.args = {}

        args = cast(Mapping[str, Any], logRecord.args)
        data = {
            LEVELNAME: logRecord.levelname,
            MESSAGE_CODE: getattr(logRecord, MESSAGE_CODE, ""),
            MSG: StructuredMessageLogHandler.get_message(logRecord),
            REFS: getattr(logRecord, REFS, []),
            ARGS: args.get('args', {})
        }

        self.messages.append(data)

    @staticmethod
    def get_message(log_record: LogRecord) -> str | tuple[object, ...] | Mapping[str, object] | None:
        """
        Gets the message that we want to report from the log record.

        :param log_record: The log record to use for the message
        :type log_record: :class:`~logging.LogRecord`
        :return: The message that we want to use
        """
        # Handle the cases where we have data in the log message directly,
        # such as iXBRL and Edgar Renderer.
        try:
            return log_record.msg % log_record.args
        except TypeError:
            return log_record.msg
        except ValueError:
            return log_record.msg
