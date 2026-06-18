"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union
from collections import OrderedDict

from arelle.ModelValue import qname, QName, AnyURI
from ordered_set import OrderedSet
from .ModelValueMore import SQName
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlFinalTaxonomy
from .XbrlProperty import XbrlProperty
from .XbrlHeading import XbrlHeading
from .XbrlConcept import XbrlCollectionType, XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import xbrl
from .XbrlCube import XbrlCube, XbrlCubeType, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution
from .XbrlDimension import XbrlDimension, XbrlDomainNetwork, XbrlDomainClass, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent, XbrlGroupTree
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType, XbrlRelationshipConstraint
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlFact import XbrlFact, XbrlFactLocatorType, XbrlFactValueAnchor, XbrlFactValueSource, XbrlFootnote, XbrlJSONTemplateMap, XbrlTableTemplate, XbrlFactSource, XbrlFactMap, XbrlXMLTemplateMap
from .XbrlModel import XbrlCompiledModel
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTypes import XbrlModuleType, QNameKeyType, NonemptySet
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject
from .XbrlLayout import XbrlLayout, XbrlDataTable, XbrlAxis, XbrlAxisHeader

class XbrlModelType(XbrlReferencableModelObject):
    """ Model Type Object
        Reference: oim-taxonomy#modeltype-object
    """
    module: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the model type object.
    allowedObjects: Optional[NonemptySet[QName]] # (optional) Defines a set of QNames representing the object types that may use the modelType. If no value is provided then the modelType can be used with any object type.
    allowedProperties: Optional[NonemptySet[QName]] # (optional) Defines a set of property QNames that can be used with the model type. If no value is provided then any property can be used with the model type.
    requiredProperties: Optional[NonemptySet[QName]] # (optional) Defines a set of property QNames that must be properties of the xbrl:xbrlModelObject. The set MUST NOT be empty.

class XbrlNamespacePrefix(XbrlReferencableModelObject):
    """ Namespace Prefix Object
        Reference: oim-taxonomy#namespaceprefix-object
    """
    module: XbrlModuleType
    namespace: AnyURI # (required) The namespace URI for which preferred prefixes are being declared.
    preferredPrefixes: OrderedSet[str] # (required) An ordered set of preferred prefix strings for the namespace. Each value MUST be a valid xs:NCName. The first item is the most preferred prefix. Values MUST be unique within the set.

class XbrlImpliedObject(XbrlReferencableModelObject):
    """ Implied Object
        Reference: oim-taxonomy#impliedobject-object
    """
    module: XbrlModuleType
    name: QNameKeyType # (required) The name of the implied object definition. This is a QName that identifies the implied object namespace. The local name of the QName is not used for resolution; only the namespace URI is relevant.
    namespace: AnyURI # (required) This is the namespace URI that defines the implied object namespace. Any QName with this namespace is considered to resolve to an implied object of the type defined by this implied object definition.
    domainClass: QName # (required) The domain class that the implied object belongs to. This is a QName that identifies the domain class within the XBRL model.
    objectType: QName # (required) The object type that the implied object represents. This is a QName that identifies the object type within the XBRL model.
    dataType: Optional[QName] # (optional) QName referencing a dataType or collectionType that constrains the local-name portion of implied QNames.

class XbrlModule(XbrlModelObject):
    """ XBRL Module Object
        Reference: oim-taxonomy#taxonomy-object
    """
    compiledModel: XbrlCompiledModel
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the taxonomy object.
    frameworkName: Optional[str] # (optional) The framework name of the taxonomy such as "US-GAAP" that indicates the taxonomy broad taxonomy family. The framework name stays consistent between regular taxonomy releases of the same taxonomy domain.
    version: Optional[str] # (optional) Used to identify the version of the taxonomy such as the year of release.
    modelForm: Optional[str] # (optional) Indicates if the model is a compiled or is modularized. If no value is provided the model defaults to module. Possible values are compiled, module
    modelType: Optional[QName]
    duplicateFactsInModel: Optional[str] # (optional) A string value that indicates if the model validates duplicate facts. It can be one of the following: no duplicates, complete duplicates,consistent duplicates, or inconsistent duplicates. If no string value is provided the default value is inconsistent duplicates. The value of duplicateFactsInModel sets the default value of duplicateFactsInCube. The value of duplicateFactsInCube has precedence over duplicateFactsInModel
    concepts: Optional[NonemptySet[XbrlConcept]] # ordered set of concept objects.
    collectionTypes: Optional[NonemptySet[XbrlCollectionType]] # ordered set of collectionType objects.
    cubes: Optional[NonemptySet[XbrlCube]] # ordered set of cube objects.
    cubeTypes: Optional[NonemptySet[XbrlCubeType]] # ordered set of cubeType objects.
    dataTypes: Optional[NonemptySet[XbrlDataType]] # ordered set of dataType objects.
    dimensions: Optional[NonemptySet[XbrlDimension]] # ordered set of dimension objects.
    domainNetworks: Optional[NonemptySet[XbrlDomainNetwork]] # (optional) ordered set of domain network objects.
    domainClasses: Optional[NonemptySet[XbrlDomainClass]] # (optional) ordered set of domain root objects.
    entities: Optional[NonemptySet[XbrlEntity]] # (optional) ordered set of entity objects.
    facts: Optional[NonemptySet[XbrlFact]] #  (optional) ordered set of fact objects.
    factMaps: Optional[NonemptySet[XbrlFactMap]] # (optional) ordered set of factMap objects.
    factSources: Optional[NonemptySet[XbrlFactSource]] # (optional) ordered set of factSource objects.
    factLocatorTypes: Optional[NonemptySet[XbrlFactLocatorType]] # (optional) ordered set of factLocatorType objects.
    footnotes: Optional[NonemptySet[XbrlFootnote]] #  (optional) ordered set of footnote objects.
    tableTemplates: Optional[NonemptySet[XbrlTableTemplate]] # (optional) ordered set of tableTemplate objects.
    groups: Optional[NonemptySet[XbrlGroup]] #  (optional) ordered set of group objects.
    groupContents: Optional[NonemptySet[XbrlGroupContent]] # ordered set of groupContent objects that link a group QName to a list of network or cube objects.
    groupTree: Optional[XbrlGroupTree] # (optional) A groupTree object that defines the hierarchical organization of groups within the taxonomy. Unlike groupContents which links groups to networks and cubes, groupTree organizes the groups themselves into a tree structure. The taxonomy serves as the root by being referenced as the source in top-level relationships. Only one groupTree object is allowed per taxonomy.
    headings: Optional[NonemptySet[XbrlHeading]] # ordered set of heading objects.
    jsonTemplateMaps: Optional[NonemptySet[XbrlJSONTemplateMap]] # (optional) ordered set of JSON template map objects that define mappings from taxonomy objects to JSON templates for rendering in user interfaces or forms.
    labels: Optional[NonemptySet[XbrlLabel]] # (optional) ordered set of label objects.
    layouts: Optional[NonemptySet[XbrlLayout]] # (optional) A layout object that defines the layout of a data structure that conforms with a XBRL model. The layout object is used to define how facts in a model or are rendered in a form or user interface.
    members: Optional[NonemptySet[XbrlMember]] #  (optional) ordered set of member objects.
    modelTypes: Optional[NonemptySet[XbrlModelType]] # (optional) ordered set of modelType objects.
    networks: Optional[NonemptySet[XbrlNetwork]] # (optional) ordered set of network objects.
    propertyTypes: Optional[NonemptySet[XbrlPropertyType]] # (optional) ordered set of propertyType objects.
    references: Optional[NonemptySet[XbrlReference]] # (optional) ordered set of reference objects.
    labelTypes: Optional[NonemptySet[XbrlLabelType]] # (optional)  ordered set of labelType objects.
    referenceTypes: Optional[NonemptySet[XbrlReferenceType]] # (optional) ordered set of referenceType objects.
    relationshipTypes: Optional[NonemptySet[XbrlRelationshipType]] # (optional) ordered set of relationshipType objects.
    transforms: Optional[NonemptySet[XbrlTransform]] # (optional) an ordered set of transform objects.
    units: Optional[NonemptySet[XbrlUnit]] # ordered set of unit objects.
    xmlTemplateMaps: Optional[NonemptySet[XbrlXMLTemplateMap]] # (optional) ordered set of XML template map objects that define mappings from taxonomy objects to XML templates for rendering in user interfaces or forms.
    importedTaxonomies: Optional[NonemptySet[XbrlImportTaxonomy]] # ordered set of importTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
    finalTaxonomy: Optional[XbrlFinalTaxonomy] # (optional) A final taxonomy object that indicates those components of the taxonomy that are final and cannot be amended or added by an importing taxonomy.
    namespacePrefixes: Optional[NonemptySet[XbrlNamespacePrefix]] # (optional) ordered set of namespace prefix objects that define preferred prefixes for namespaces used within the taxonomy.
    impliedObjects: Optional[NonemptySet[XbrlImpliedObject]] # (optional) A set of implied Objects that defines objects that are implied by the model but not explicitly defined.
    JSONTemplateMaps: Optional[NonemptySet[XbrlJSONTemplateMap]]
    XMLTemplateMaps: Optional[NonemptySet[XbrlXMLTemplateMap]]
    properties: Optional[NonemptySet[XbrlProperty]] # ordered set of property objects used to specify additional properties associated with the taxonomy. Only immutable properties as defined in the propertyType object can be added to a taxonom

""" Referencable Object Types
    These are the object types that can be referenced by other objects in the taxonomy or report."""
referencableObjectTypes = {
        qname(xbrl, "xbrl:xbrlModelObject"): XbrlModule,
        qname(xbrl, "xbrl:conceptObject"): XbrlConcept,
        qname(xbrl, "xbrl:collectionTypeObject"): XbrlCollectionType,
        qname(xbrl, "xbrl:headingObject"): XbrlHeading,
        qname(xbrl, "xbrl:cubeObject"): XbrlCube,
        qname(xbrl, "xbrl:dimensionObject"): XbrlDimension,
        qname(xbrl, "xbrl:domainNetworkObject"): XbrlDomainNetwork,
        qname(xbrl, "xbrl:domainClassObject"): XbrlDomainClass,
        qname(xbrl, "xbrl:entityObject"): XbrlEntity,
        qname(xbrl, "xbrl:factObject"): XbrlFact,
        qname(xbrl, "xbrl:factMapObject"): XbrlFactMap,
        qname(xbrl, "xbrl:factLocatorTypeObject"): XbrlFactLocatorType,
        qname(xbrl, "xbrl:factSourceObject"): XbrlFactSource,
        qname(xbrl, "xbrl:finalTaxonomyObject"): XbrlFinalTaxonomy,
        qname(xbrl, "xbrl:footnoteObject"): XbrlFootnote,
        qname(xbrl, "xbrl:groupObject"): XbrlGroup,
        qname(xbrl, "xbrl:groupTreeObject"): XbrlGroupTree,
        qname(xbrl, "xbrl:jsonTemplateMapObject"): XbrlJSONTemplateMap,
        qname(xbrl, "xbrl:networkObject"): XbrlNetwork,
        qname(xbrl, "xbrl:relationshipTypeObject"): XbrlRelationshipType,
        qname(xbrl, "xbrl:memberObject"): XbrlMember,
        qname(xbrl, "xbrl:referenceObject"): XbrlReference,
        qname(xbrl, "xbrl:unitObject"): XbrlUnit,
        qname(xbrl, "xbrl:dataTypeObject"): XbrlDataType,
        qname(xbrl, "xbrl:propertyTypeObject"): XbrlPropertyType,
        qname(xbrl, "xbrl:labelTypeObject"): XbrlLabelType,
        qname(xbrl, "xbrl:referenceTypeObject"): XbrlReferenceType,
        qname(xbrl, "xbrl:cubeTypeObject"): XbrlCubeType,
        qname(xbrl, "xbrl:unitTypeObject"): XbrlUnitType,
        # qname(xbrl, "xbrl:taxonomyObject"): XbrlModule,  # xbrl:taxonomyObject is xbrl:modelObject
        qname(xbrl, "xbrl:modelTypeObject"): XbrlModelType,
        qname(xbrl, "xbrl:layoutObject"): XbrlLayout,
        qname(xbrl, "xbrl:tableTemplateObject"): XbrlTableTemplate,
        qname(xbrl, "xbrl:dataTableObject"): XbrlDataTable,
        qname(xbrl, "xbrl:xmlTemplateMapObject"): XbrlXMLTemplateMap,
    }
nonReferencableObjectTypes = {
        qname(xbrl, "xbrl:importTaxonomyObject"): XbrlImportTaxonomy,
        qname(xbrl, "xbrl:cubeDimensionObject"): XbrlCubeDimension,
        qname(xbrl, "xbrl:factValueSourceObject"): XbrlFactValueSource,
        qname(xbrl, "xbrl:factValueAnchorObject"): XbrlFactValueAnchor,
        qname(xbrl, "xbrl:groupContentObject"): XbrlGroupContent,
        qname(xbrl, "xbrl:impliedObject"): XbrlImpliedObject,
        qname(xbrl, "xbrl:periodConstraintObject"): XbrlPeriodConstraint,
        qname(xbrl, "xbrl:dateResolutionObject"): XbrlDateResolution,
        qname(xbrl, "xbrl:relationshipObject"): XbrlRelationship,
        qname(xbrl, "xbrl:relationshipConstraintObject"): XbrlRelationshipConstraint,
        qname(xbrl, "xbrl:labelObject"): XbrlLabel,
        qname(xbrl, "xbrl:propertyObject"): XbrlProperty,
        qname(xbrl, "xbrl:axisObject"): XbrlAxis,
        qname(xbrl, "xbrl:axisHeaderObject"): XbrlAxisHeader,
    }
xbrlObjectTypes = referencableObjectTypes | nonReferencableObjectTypes
xbrlObjectQNames = dict((v,k) for k,v in xbrlObjectTypes.items())