"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING

from arelle.ModelValue import QName, YearMonthDayTimeDuration
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .ModelValueMore import QNameAt, SQName
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject

class XbrlTransform(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the transform object.
    inputDataType: QName # (required) Indicates the datatype of the input to be transformed.
    outputDataType: QName # (required) Indicates the datatype of the input to be transformed.
