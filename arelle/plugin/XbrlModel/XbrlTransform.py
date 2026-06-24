"""
See COPYRIGHT.md for copyright information.
"""

from arelle.ModelValue import QName, YearMonthDayTimeDuration
from .XbrlTypes import XbrlModuleAlias, QNameKeyType
from .ModelValueMore import QNameAt, SQName
from .XbrlObject import XbrlReferencableModelObject

class XbrlTransform(XbrlReferencableModelObject):
    """ Transform Object
        Reference: oim-taxonomy#transform-object
    """
    module: XbrlModuleAlias
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the transform object.
    inputDataType: QName # (required) Indicates the datatype of the input to be transformed.
    outputDataType: QName # (required) Indicates the datatype of the input to be transformed.
