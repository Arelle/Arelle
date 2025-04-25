"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING
from decimal import Decimal

from arelle.ModelValue import QName
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject

class XbrlTableTemplate(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the transform object.
    rowIdColumn: str # (optional) An identifier specifying the name of the row ID column.
    columns: dict # (required) A columns object. (See xbrl-csv specification)
    dimensions: dict # (required) A dimensions object that defines table dimensions. (See xbrl-csv specification)
    decimals: Decimal # (optional) A decimals value
