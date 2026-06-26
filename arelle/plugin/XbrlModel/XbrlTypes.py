"""
See COPYRIGHT.md for copyright information.
"""

from typing_extensions import TypeAlias, List
from arelle.ModelValue import QName
from ordered_set import OrderedSet

XbrlLabelAlias: TypeAlias = "XbrlLabel"
XbrlLayoutAlias: TypeAlias = "XbrlLayout"
XbrlDataTableAlias: TypeAlias = "XbrlDataTable"
XbrlPropertyAlias: TypeAlias = "XbrlProperty"
XbrlTaxonomyModelAlias: TypeAlias = "XbrlCompiledModel"
XbrlModuleAlias: TypeAlias = "XbrlModule"
XbrlUnitTypeAlias: TypeAlias = "XbrlUnitType"

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
class OptionalList(List): # list of objects like OrderedSet which is absent (None) when no objects
    pass
class OptionalDict(dict): # dict of objects which is absent (None) when no contents
    pass
class NonemptySet(OrderedSet): # set of objects like OrderedSet which is present and nonempty
    pass