"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Set, Any

from arelle.ModelValue import QName

class QNameAt(QName):
    def __init__(self, prefix: str | None, namespaceURI: str | None, localName: str, atSuffix:str = "end") -> None:
        super(QNameAt, self).__init__(prefix, namespaceURI, localName)
        self.atSuffix: str = atSuffix # The context suffix must be either @end or @start. If an @ value is not provided then the suffix defaults to @end.

class SQName(QName):
    pass # no properties added to QName, just the localName part doesn't have to be an xml identifier
