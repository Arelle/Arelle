"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Union

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlDts import XbrlDts
from .XbrlAbstract import XbrlAbstract
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, DefaultTrue, DefaultFalse
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlImportedTaxonomy(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    importedTaxonomies: OrderedSet # ordered set of importedTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
    abstracts: OrderedSet[XbrlAbstract] # ordered set of abstract objects.
    taxonomyName: QNameKeyType # (required) The QName of the taxonomy to import. The location of the taxonomy QName is resolved by referencing the namespace map which includes the url of the namespace. When importing XBRL 2.1 taxonomies a QName comprising the namespace of the taxonomy to import and a local name of taxonomy is defined. i.e. ifrs:Taxonomy.
    includeObjects: set[QName] # (optional) A set of object QNames that should be imported from the taxonomyName location property. Only the objects defined in the include and any dependent objects are added to the dts. This property can only be used for taxonomy files using the OIM specification. The dependents of each object are defined in this specification.
    includeObjectTypes: set[QName] # (optional) A set of object type QNames that should be imported from the taxonomyName location property. Examples include xbrl:conceptObject and xbrl:memberObject. All objects of the specified object types from the taxonomyName and any dependent objects will be imported. This property can only be used for taxonomy files using the OIM specification. The includeObjectTypes cannot include the label object.
    excludeLabels: Union[bool, DefaultTrue] # (optional) If set to true any labels attached to the objects comprising the dts deriving from the taxonomyName property will be excluded from the dts. The default value is false.
    followImport: Union[bool, DefaultFalse] # (optional) If set to false the dts resolution will not import taxonomies defined in descendant ImportedTaxonomyObjects. These imports will be excluded from the dts. The default value is true. This means if a taxonomy QName is provided all imprtedTaxonomy objects will be brought into the dts.
