"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

DEFAULT_JSON_MAX_ATTRIBUTE_LENGTH = 4096000
DEFAULT_XML_MAX_ATTRIBUTE_LENGTH = 128

class LogHandlerWithXml(logging.Handler):
    logTextMaxLength: int

    def __init__(self, logXmlMaxAttributeLength: int | None = None ) -> None:
        super(LogHandlerWithXml, self).__init__()
        self.logJsonMaxAttributeLength = logXmlMaxAttributeLength or DEFAULT_JSON_MAX_ATTRIBUTE_LENGTH
        self.logXmlMaxAttributeLength = logXmlMaxAttributeLength or DEFAULT_XML_MAX_ATTRIBUTE_LENGTH

    def recordToXml(self, logRec: logging.LogRecord) -> str:
        def entityEncode(arg: Any, truncateAt: int = self.logTextMaxLength) -> str:  # be sure it's a string, vs int, etc, and encode &, <, ".
            s = str(arg)
            s = s if len(s) <= truncateAt else s[:truncateAt] + '...'
            return s.replace("&","&amp;").replace("<","&lt;").replace('"','&quot;')

        def ncNameEncode(arg: str) -> str:
            s = []
            for c in arg:
                if c.isalnum() or c in ('.','-','_'):
                    s.append(c)
                else: # covers : and any other non-allowed character
                    s.append('_') # change : into _ for xml correctness
            return "".join(s)

        def propElts(properties: list[tuple[Any, Any, Any]], indent: str, truncateAt: int = 128) -> str:
            nestedIndent = indent + ' '
            return indent.join('<property name="{0}" value="{1}"{2}>'.format(
                entityEncode(p[0]),
                entityEncode(p[1], truncateAt=truncateAt),
                '/' if len(p) == 2
                else '>' + nestedIndent + propElts(p[2],nestedIndent) + indent + '</property')
                               for p in properties
                               if 2 <= len(p) <= 3)

        msg = self.format(logRec)
        if logRec.args and isinstance(logRec.args, Mapping):
            args = "".join([' {0}="{1}"'.format(
                ncNameEncode(n), entityEncode(v, truncateAt=(self.logJsonMaxAttributeLength if n == "json" else self.logXmlMaxAttributeLength))
            )
                            for n, v in logRec.args.items()])
        else:
            args = ""
        refs = "\n ".join('\n <ref href="{0}"{1}{2}{3}>'.format(
            entityEncode(ref["href"]),
            ' sourceLine="{0}"'.format(ref["sourceLine"]) if "sourceLine" in ref else '',
            ''.join(' {}="{}"'.format(ncNameEncode(k),entityEncode(v))
                    for k,v in ref["customAttributes"].items())
            if 'customAttributes' in ref else '',
            (">\n  " + propElts(ref["properties"],"\n  ", truncateAt=self.logTextMaxLength) + "\n </ref" )
            if ("properties" in ref) else '/')
                          for ref in getattr(logRec, "refs", []))
        return ('<entry code="{0}" level="{1}">'
                '\n <message{2}>{3}</message>{4}'
                '</entry>\n'.format(getattr(logRec, "messageCode", ""),
                                    logRec.levelname.lower(),
                                    args,
                                    entityEncode(msg),
                                    refs))
    def recordToJson(self, logRec: logging.LogRecord) -> dict[str, Any]:
        message = { "text": self.format(logRec) }
        if logRec.args and isinstance(logRec.args, Mapping):
            for n, v in logRec.args.items():
                message[n] = str(v)
        return {"code": getattr(logRec, "messageCode", ""),
                "level": logRec.levelname.lower(),
                "refs": getattr(logRec, "refs", []),
                "message": message}

    def recordToHtml(self, logRec: logging.LogRecord) -> str:
        record = ["<tr>"]
        record.append(f"<td>{getattr(logRec, 'messageCode', '')}</td>")
        record.append(f"<td>{logRec.levelname.lower()}</td>")
        record.append(f"<td>{self.format(logRec)}</td>")
        record.append("</tr>")
        return "\n".join(record)
