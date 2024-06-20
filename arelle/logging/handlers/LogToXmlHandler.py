"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import logging
import sys

from arelle import PluginManager
from arelle.logging.handlers.LogHandlerWithXml import LogHandlerWithXml


class LogToXmlHandler(LogHandlerWithXml):
    """
    .. class:: LogToXmlHandler(filename)

    A log handler that writes log entries to named XML file (utf-8 encoded) upon closing the application.
    """
    logRecordBuffer: list[logging.LogRecord]
    filename: str | None
    filemode: str
    htmlTitle: str = "Arelle Message Log" # may be customized in plugin startup

    def __init__(
            self,
            filename: str | None = None,
            mode: str = 'w',
            logXmlMaxAttributeLength: int | None = None
    ) -> None:
        super(LogToXmlHandler, self).__init__(logXmlMaxAttributeLength=logXmlMaxAttributeLength)
        self.filename = filename # may be none if buffer is retrieved by get methods below and not written anywhere
        self.logRecordBuffer = []
        self.filemode = mode

    def flush(self) -> None:
        # Note to developers: breakpoints in this method don't work, please debug with print statements
        securityIsActive = securityHasWritten = False
        for pluginMethod in PluginManager.pluginClassMethods("Security.Crypt.IsActive"):
            securityIsActive = pluginMethod(self) # must be active for the cntlr object to effect log writing
        if self.filename == "logToStdOut.xml":
            print('<?xml version="1.0" encoding="utf-8"?>')
            print('<log>')
            for logRec in self.logRecordBuffer:
                logRecXml = self.recordToXml(logRec)
                try:
                    print(logRecXml)
                except UnicodeEncodeError:
                    # extra parentheses in print to allow for 3-to-2 conversion
                    print((logRecXml
                           .encode(sys.stdout.encoding, 'backslashreplace')
                           .decode(sys.stdout.encoding, 'strict')))
            print('</log>')
        elif self.filename is not None:
            if self.filename.endswith(".xml"):
                # print ("filename=" + self.filename)
                if securityIsActive:
                    for pluginMethod in PluginManager.pluginClassMethods("Security.Crypt.Write"):
                        securityHasWritten = pluginMethod(self, self.filename,
                                                          '<?xml version="1.0" encoding="utf-8"?>\n<log>\n' +
                                                          ''.join(self.recordToXml(logRec) for logRec in self.logRecordBuffer) +
                                                          '</log>\n')
                if not securityHasWritten:
                    with open(self.filename, self.filemode, encoding='utf-8') as fh:
                        fh.write('<?xml version="1.0" encoding="utf-8"?>\n<log>\n')
                        for logRec in self.logRecordBuffer:
                            fh.write(self.recordToXml(logRec))
                        fh.write('</log>\n')
            elif self.filename.endswith(".json"):
                if securityIsActive:
                    for pluginMethod in PluginManager.pluginClassMethods("Security.Crypt.Write"):
                        securityHasWritten = pluginMethod(self, self.filename, self.getJson())
                if not securityHasWritten:
                    with open(self.filename, self.filemode, encoding='utf-8') as fh:
                        fh.write(self.getJson())
            elif self.filename.endswith(".html"):
                if securityIsActive:
                    for pluginMethod in PluginManager.pluginClassMethods("Security.Crypt.Write"):
                        securityHasWritten = pluginMethod(self, self.filename, self.getHtml())
                if not securityHasWritten:
                    with open(self.filename, self.filemode, encoding='utf-8') as fh:
                        fh.write(self.getHtml())
            elif self.filename in ("logToPrint", "logToStdErr"):
                _file = sys.stderr if self.filename == "logToStdErr" else None
                for logRec in self.logRecordBuffer:
                    logEntry = self.format(logRec)
                    try:
                        print(logEntry, file=_file)
                    except UnicodeEncodeError:
                        # extra parentheses in print to allow for 3-to-2 conversion
                        print((logEntry
                               .encode(sys.stdout.encoding, 'backslashreplace')
                               .decode(sys.stdout.encoding, 'strict')),
                              file=_file)
            else:
                if securityIsActive:
                    for pluginMethod in PluginManager.pluginClassMethods("Security.Crypt.Write"):
                        securityHasWritten = pluginMethod(self, self.filename,
                                                          ''.join(self.format(logRec) + "\n" for logRec in self.logRecordBuffer))
                if not securityHasWritten:
                    with open(self.filename, self.filemode, encoding='utf-8') as fh:
                        for logRec in self.logRecordBuffer:
                            fh.write(self.format(logRec) + "\n")
        self.clearLogBuffer()

    def clearLogBuffer(self) -> None:
        del self.logRecordBuffer[:]

    def getXml(self, clearLogBuffer: bool = True, includeDeclaration: bool = True) -> str:
        """
        Returns an XML document (as a string) representing the messages in the log buffer.
        Optionally clears the log buffer afterwards.
        Optionally includes XML declaration.
        :return: XML string of messages in the log buffer.
        """
        xml = []
        if includeDeclaration:
            xml.append('<?xml version="1.0" encoding="utf-8"?>\n')
        xml.append('<log>')
        for logRec in self.logRecordBuffer:
            xml.append(self.recordToXml(logRec))
        xml.append('</log>')
        if clearLogBuffer:
            self.clearLogBuffer()
        return '\n'.join(xml)

    def getJson(self, clearLogBuffer: bool = True) -> str:
        """Returns an JSON string representing the messages in the log buffer, and clears the buffer.

        :returns: str -- json representation of messages in the log buffer
        """
        entries = []
        for logRec in self.logRecordBuffer:
            entries.append(self.recordToJson(logRec))
        if clearLogBuffer:
            self.clearLogBuffer()
        return json.dumps( {"log": entries}, ensure_ascii=False, indent=1, default=str )

    def getHtml(self, clearLogBuffer: bool = True) -> str:
        """Returns an HTML string representing the messages in the log buffer, and clears the buffer.

        :returns: str -- HTML representation of messages in the log buffer
        """
        html = ["""<!doctype html>
        <html>
        <head>
            <title>{0}</title>
            <style>
                table {{
                    border: 1px solid black;
                    border-spacing: 3px;
                    table-layout: fixed;
                    width: 100%;
                }}
                th, td {{
                    padding: 5px;
                    word-wrap: break-word;
                }}
                th {{
                    background-color: #bcf1fd;
                }}
                td {{
                    background-color: #f4f7f7;
                }}
                td:last-child, th:last-child {{
                    width: 80%;
                }}
            </style>
        </head>
        <body>
        <table>
            <thead>
                <tr>
                    <th>Code</th>
                    <th>Level</th>
                    <th style="">Message</th>
                </tr>
            </thead>
            <tbody>""".format(
            self.htmlTitle)
        ]
        if self.logRecordBuffer:
            for logRec in self.logRecordBuffer:
                if all(p(logRec) for p in PluginManager.pluginClassMethods("Cntlr.Log.RecFilter.Html")):
                    html.append(self.recordToHtml(logRec))
            if clearLogBuffer:
                self.clearLogBuffer()
            html.append("</tbody>\n</table>\n</body>\n</html>\n")
        if len(html) < 3: # no entries were added to log. Display no log errors message
            html = ["""<!doctype html>
            <html>
            <head>
                <title>{0}</title>
                <style>
                    div {{
                        background-color: #f4f7f7;
                        position: relative;
                        top: 33.33%;
                        margin: -10px auto;
                        width: 25vw;
                        height: 25vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        text-align: center;
                    }}
                    body {{
                        background-color: #bcf1fd;
                        height: 100vh;
                    }}
                </style>
            </head>
            <body>
                <div>
                    <h1>No log errors to display</h1>
                </div>
            </body>
            </html>
            """.format(
                self.htmlTitle)
            ]
        return '\n'.join(html)

    def getLines(self, clearLogBuffer: bool = True) -> list[str]:
        """Returns a list of the message strings in the log buffer, and clears the buffer.

        :returns: [str] -- list of strings representing messages corresponding to log buffer entries
        """
        lines = [self.format(logRec) for logRec in self.logRecordBuffer]
        if clearLogBuffer:
            self.clearLogBuffer()
        return lines

    def getText(self, separator: str = '\n', clearLogBuffer: bool = True) -> str:
        """Returns a string of the lines in the log buffer, separated by newline or provided separator.

        :param separator: Line separator (default is platform os newline character)
        :type separator: str
        :returns: str -- joined lines of the log buffer.
        """
        return separator.join(self.getLines(clearLogBuffer=clearLogBuffer))

    def emit(self, logRecord: logging.LogRecord) -> None:
        self.logRecordBuffer.append(logRecord)
