"""
See COPYRIGHT.md for copyright information.
"""

from typing import Optional

from arelle.ModelValue import qname, QName, AnyURI
from ordered_set import OrderedSet
from .XbrlConst import xbrl
from .ModelValueMore import SQName
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleAlias, QNameKeyType, NonemptySet
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject

class XbrlLabel(XbrlTaxonomyTagObject):
    """ Label Object
        Reference: oim-taxonomy#label-object
    """
    module: XbrlModuleAlias
    forObject: QName # (required) Defines a QName that the label is associated with.
    labelType: QName # (required) A QName representing the label type of the label. This can be a taxonomy defined label type or a standard XBRL label type defined in specification.
    language: str # (required) Defines the language of the label using a valid BCP 47 [BCP47] language code.
    value: str # (required) The text of the label.

    @property
    def _type(self):
        return self.labelType

class XbrlLabelType(XbrlReferencableModelObject):
    """ Label Type Object
        Reference: oim-taxonomy#labeltype-object
    """
    module: XbrlModuleAlias
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the label type object.
    uri: Optional[AnyURI] # (optional) A uri used to identify the label type of label objects for backward compatability with XBRL 2.1 taxonomies.
    formatType: str # (required) Specifies the content format of label values. MUST be one of: text, html, markdown, xbrl:xhtml, structured. (Replaced the former dataType property.)
    contentConstraints: Optional[dict] # (optional) An object constraining label values: maxLength, minLength (xs:integer) and/or pattern (xs:string regex). Modeled as a plain object (no OIM object-type QName), so kept as a dict.
    allowedObjects: Optional[NonemptySet[QName]] # (optional) Defines an ordered set of object types that can use the labelType.  None means absent from input, empty set means [] on input which raises an error.

preferredLabel = qname(xbrl, "xbrl:preferredLabel")
