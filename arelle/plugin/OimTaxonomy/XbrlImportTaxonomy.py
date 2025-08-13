"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Union, Any

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlAbstract import XbrlAbstract
from .XbrlTypes import XbrlTaxonomyModuleType, QNameKeyType, DefaultTrue, DefaultFalse
from .XbrlObject import XbrlObject, XbrlTaxonomyObject

class XbrlFilterCondition(XbrlObject):
    property: QName # (required) The name of the property to be used for filtering the objects. This is either a names object property or a QName property that identifies the property, such as periodType, xbrl:balance, etc.
    operator: str # (required) The operator to be used for filtering the objects. The operator can be one of the following values: =, !=, in, not in, contains, not contains, >, <, >=, <=. The operator is used to compare the property value with the specified value.
    value: Any # (required) The value to be used for filtering the objects. The value can be a string, number, or boolean, depending on the property type. The value is compared with the property value using the specified operator.

class XbrlStructuredSelectStatement(XbrlObject):
    objectType: QName # (required) The type of the object to be selected. This is a QName that identifies the object type, such as xbrl:conceptObject, xbrl:dimensionObject, etc.
    where: list[XbrlFilterCondition] # (optional) An array of filter conditions that define the selection criteria. Each condition is an object that specifies the property, operator, and value to be used for filtering the objects.

class XbrlExportProfile(XbrlTaxonomyObject):
    name: QName # (required) The name of the export profile.
    taxonomyType: str # (required) The type of the taxonomy that the export profile is associated with. This is typically a string that identifies the taxonomy framework, such as "US-GAAP" or "IFRS".
    selections: set[XbrlStructuredSelectStatement] # (optional) Specifies a set of string select statements PW needs to reference a definition or structured select objects that define the objects to be included in the export profile. Each select statement is a string or structured select objects that specify the objects to be selected from the taxonomy model. The select statements can include object names, types, and properties. e.g., xbrl:conceptObject where periodType = "instant".
    exportObjects: set[QName] # (optional) Specifies a set of object QNames that define the objects to be included in the export profile. The exportObjects property allows for the selection of specific objects from the taxonomy model to be included in the export profile.
    exportObjectTypes: set[QName] # (optional) Specifies a set of object type QNames that define the types of objects to be included in the export profile. The exportObjectTypes property allows for the selection of specific object types from the taxonomy model to be included in the export profile.
    excludeLabels: Union[bool, DefaultFalse] # (optional) If set to true, any labels attached to the objects comprising the taxonomy model deriving from the taxonomyName property will be excluded from the taxonomy model. The default value is false.

class XbrlImportTaxonomy(XbrlTaxonomyObject):
    taxonomy: XbrlTaxonomyModuleType
    taxonomyName: QNameKeyType # (required) The QName of the taxonomy to import. When importing XBRL 2.1 taxonomies, the QName comprising the namespace of the taxonomy to import and a local name of taxonomy is defined (e.g., ifrs:Taxonomy).
    profiles: set[XbrlExportProfile] # (optional only if selections, importObjects or importObjectTypes are not used) A set of exportProfile objects defined in the taxonomy being imported. Only objects defined in this set will be included in the taxonomy model. If this property is not present, all objects in the taxonomy identified by the taxonomyName property location will be included in the taxonomy model.
    selections: set[XbrlStructuredSelectStatement]  # (optional) Specifies a set of string select statements or structured select objects that define the objects to be included in the import. Each select statement is a string that specifies the objects to be selected from the taxonomy model. The select statements can include object names, types, and properties. e.g., xbrl:conceptObject where periodType = "instant".
    importObjects: set[QName] # (optional) A set of object QNames that should be imported from the taxonomyName location property. Only the objects defined in the include and any dependent objects are added to the dts. This property can only be used for taxonomy files using the OIM specification. The dependents of each object are defined in this specification.
    importObjectTypes: set[QName] # (optional) A set of object type QNames that should be imported from the taxonomyName location property. Examples include xbrl:conceptObject and xbrl:memberObject. All objects of the specified object types from the taxonomyName and any dependent objects will be imported. This property can only be used for taxonomy files using the OIM specification. The includeObjectTypes cannot include the label object.
    excludeLabels: Union[bool, DefaultFalse] # (optional) If set to true, any labels attached to the objects comprising the taxonomy model deriving from the taxonomyName property will be excluded from the taxonomy model. The default value is false.
