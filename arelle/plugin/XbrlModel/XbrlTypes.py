"""
See COPYRIGHT.md for copyright information.
"""

from typing_extensions import TypeAlias, List
from arelle.ModelValue import QName

XbrlLabelType: TypeAlias = "XbrlLabel"
XbrlLayoutType: TypeAlias = "XbrlLayout"
XbrlDataTableType: TypeAlias = "XbrlDataTable"
XbrlPropertyType: TypeAlias = "XbrlProperty"
XbrlTaxonomyModelType: TypeAlias = "XbrlCompiledModel"
XbrlModuleType: TypeAlias = "XbrlModule"
XbrlReportType: TypeAlias = "XbrlReport"
XbrlUnitTypeType: TypeAlias = "XbrlUnitType"

class QNameKeyType(QName): # a QName which is also the primary key for parent collection object
    pass
class SQNameKeyType(QName): # an SQName which is also the primary key for parent collection object
    pass
class strKeyType(str): # a str which is also the primary key for parent collection object
    pass
class DefaultTrue: # a bool which if absent defaults to true
    pass
class DefaultFalse: # a bool which if absent defaults to false
    pass
class DefaultZero: # a number which if absent defaults to zero
    pass
class DefaultOne: # a number which if absent defaults to one
    pass
class OptionalList(List): # list of objects like OrderedSet which is present and empty when no objects
    pass
class OptionalNonemptySet(set): # set of objects like OrderedSet which is present and absent when no objects
    pass