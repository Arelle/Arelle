"""
See COPYRIGHT.md for copyright information.
"""

from typing_extensions import TypeAlias
from arelle.ModelValue import QName

XbrlDtsType: TypeAlias = "XbrlDts"
XbrlLabelType: TypeAlias = "XbrlLabel"
XbrlPropertyType: TypeAlias = "XbrlProperty"
XbrlTaxonomyType: TypeAlias = "XbrlTaxonomy"
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
