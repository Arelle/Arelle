"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Set

from arelle.ModelValue import QName

class QNameAt(QName):
    atSuffix: str = "@end" # The context suffix must be either @end or @start. If an @ value is not provided then the suffix defaults to @end.

class SQName(QName):
    pass # no properties added to QName, just the localName part doesn't have to be an xml identifier
