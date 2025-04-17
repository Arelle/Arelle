"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, cast, Any
from collections import OrderedDict # OrderedDict is not same as dict, has additional key order features

from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject

def castToDts(modelXbrl):
    if isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlDts
        modelXbrl.taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
    return modelXbrl


class XbrlDts(ModelXbrl): # complete wrapper for ModelXbrl
    taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType]

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlDts, self).__init__(*args, **kwargs)
        self.dtsObjectIndex = 0

    @property
    def xbrlTaxonomy(self):
        return cast(XbrlTaxonomy, self.modelDocument)

def create(*args: Any, **kwargs: Any) -> XbrlDts:
    return cast(XbrlDts, modelXbrlCreate(*args, **kwargs))
