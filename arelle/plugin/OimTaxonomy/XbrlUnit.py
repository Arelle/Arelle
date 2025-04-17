"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlTaxonomyType
from .ModelValueMore import SQName
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlUnit(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: SQName # (required) The unitQName that identifies the unit so it can be referenced by other objects.
    dataType: QName # (required) Indicates the dataType of the unit. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    baseStandard: str # (required) Indicates the source of the unit. Valid values are Cutomary, SI, NonSI, ISO4217, and XBRL.
    dataTypeNumerator: Optional[QName] # (optional) Indicates the dataType of the unit numerator when the unit is comprised of a division of two datatypes. This is an optional property and must be used with dataTypeDenominator
    dataTypeDenominator: Optional[QName] # (optional) Indicates the dataType of the unit denominator when the unit is comprised of a division of two datatypes. This is an optional property and must be used with dataTypeNumerator
