"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, cast, Any
from collections import OrderedDict # OrderedDict is not same as dict, has additional key order features

from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl, create as modelXbrlCreate
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject

def castToDts(modelXbrl):
    if isinstance(modelXbrl, ModelXbrl):
        modelXbrl.__class__ = XbrlDts
        modelXbrl.taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType] = OrderedDict()
        modelXbrl.dtsObjectIndex = 0
        modelXbrl.taxonomyObjects: list[XbrlTaxonomyObject] = []
        modelXbrl.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata
    return modelXbrl


class XbrlDts(ModelXbrl): # complete wrapper for ModelXbrl
    taxonomies: OrderedDict[QNameKeyType, XbrlTaxonomyType]
    taxonomyObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] # not visible metadata

    def __init__(self,  *args: Any, **kwargs: Any) -> None:
        super(XbrlDts, self).__init__(*args, **kwargs)
        self.taxonomyObjects: list[XbrlTaxonomyObject] = []
        self.namedObjects: OrderedDict[QNameKeyType, XbrlReferencableTaxonomyObject] = OrderedDict() # not visible metadata

    @property
    def xbrlTaxonomy(self):
        return cast(XbrlTaxonomy, self.modelDocument)

    # UI thread viewTaxonomyObject
    def viewTaxonomyObject(self, objectId: str | int) -> None:
        """Finds taxonomy object, if any, and synchronizes any views displaying it to bring the model object into scrollable view region and highlight it
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        """
        txmyObj: XbrlTaxonomyObject | str | int = ""
        try:
            if isinstance(objectId, XbrlTaxonomyObject):
                txmyObj = objectId
            elif isinstance(objectId, str) and objectId.startswith("_"):
                txmyObj = cast('XbrlTaxonomyObject', self.taxonomyObjects[int(objectId.rpartition("_")[2])])
            if txmyObj is not None:
                for view in self.views:
                    view.viewModelObject(txmyObj)
        except (IndexError, ValueError, AttributeError)as err:
            self.modelManager.addToLog(_("Exception viewing properties {0} {1} at {2}").format(
                            modelObject,
                            err, traceback.format_tb(sys.exc_info()[2])))

def create(*args: Any, **kwargs: Any) -> XbrlDts:
    return cast(XbrlDts, modelXbrlCreate(*args, **kwargs))
