"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union
from collections import OrderedDict

from arelle.ModelValue import qname, QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .ModelValueMore import SQName
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlExportProfile, XbrlFinalTaxonomy
from .XbrlProperty import XbrlProperty
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlCube import XbrlCube, XbrlCubeType, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution, XbrlAllowedCubeDimension, XbrlRequiredCubeRelationship
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainRoot, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent, XbrlGroupTree
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType, XbrlRelationshipConstraint
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlReport import XbrlFactspace, XbrlFootnote, XbrlTableTemplate
from .XbrlModel import XbrlCompiledModel
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTypes import QNameKeyType
from .XbrlObject import XbrlModelObject
from .XbrlLayout import XbrlLayout, XbrlDataTable, XbrlAxis, XbrlAxisDimension

class XbrlModule(XbrlModelObject):
    compiledModel: XbrlCompiledModel
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the taxonomy object.
    frameworkName: Optional[str] # (optional) The framework name of the taxonomy such as "US-GAAP" that indicates the taxonomy broad taxonomy family. The framework name stays consistent between regular taxonomy releases of the same taxonomy domain.
    version: Optional[str] # (optional) Used to identify the version of the taxonomy such as the year of release.
    modelForm: Optional[str] # (optional) Indicates if the model is a compiled or is modularized. If no value is provided the model defaults to module. Possible values are compiled, module
    importedTaxonomies: OrderedSet[XbrlImportTaxonomy] # ordered set of importTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
    finalTaxonomy: Optional[XbrlFinalTaxonomy] # (optional) A final taxonomy object that indicates those components of the taxonomy that are final and cannot be amended or added by an importing taxonomy.
    exportProfiles: OrderedSet[XbrlExportProfile] # (optional) ordered set of exportProfile objects.
    abstracts: OrderedSet[XbrlAbstract] # ordered set of abstract objects.
    concepts: OrderedSet[XbrlConcept] # ordered set of concept objects.
    cubes: OrderedSet[XbrlCube] # ordered set of cube objects.
    cubeTypes: OrderedSet[XbrlCubeType] # ordered set of cubeType objects.
    dataTypes: OrderedSet[XbrlDataType] # ordered set of dataType objects.
    dimensions: OrderedSet[XbrlDimension] # ordered set of dimension objects.
    domains: OrderedSet[XbrlDomain] # (optional) ordered set of domain objects.
    domainRoots: OrderedSet[XbrlDomainRoot] # (optional) ordered set of domain root objects.
    entities: OrderedSet[XbrlEntity] # (optional) ordered set of entity objects.
    factspaces: OrderedSet[XbrlFactspace] #  (optional) ordered set of factspace objects.
    footnotes: OrderedSet[XbrlFootnote] #  (optional) ordered set of footnote objects.
    tableTemplates: OrderedSet[XbrlTableTemplate] # (optional) ordered set of tableTemplate objects.
    groups: OrderedSet[XbrlGroup] #  (optional) ordered set of group objects.
    groupContents: OrderedSet[XbrlGroupContent] # ordered set of groupContent objects that link a group QName to a list of network or cube objects.
    groupTree: Optional[XbrlGroupTree] # (optional) A groupTree object that defines the hierarchical organization of groups within the taxonomy. Unlike groupContents which links groups to networks and cubes, groupTree organizes the groups themselves into a tree structure. The taxonomy serves as the root by being referenced as the source in top-level relationships. Only one groupTree object is allowed per taxonomy.
    labels: OrderedSet[XbrlLabel] # (optional) ordered set of label objects.
    members: OrderedSet[XbrlMember] #  (optional) ordered set of member objects.
    networks: OrderedSet[XbrlNetwork] # (optional) ordered set of network objects.
    propertyTypes: OrderedSet[XbrlPropertyType] # (optional) ordered set of propertyType objects.
    references: OrderedSet[XbrlReference] # (optional) ordered set of reference objects.
    labelTypes: OrderedSet[XbrlLabelType] # (optional)  ordered set of labelType objects.
    referenceTypes: OrderedSet[XbrlReferenceType] # (optional) ordered set of referenceType objects.
    relationshipTypes: OrderedSet[XbrlRelationshipType] # (optional) ordered set of relationshipType objects.
    transforms: OrderedSet[XbrlTransform] # (optional) an ordered set of transform objects.
    units: OrderedSet[XbrlUnit] # ordered set of unit objects.
    properties: OrderedSet[XbrlProperty] # ordered set of property objects used to specify additional properties associated with the taxonomy. Only immutable properties as defined in the propertyType object can be added to a taxonom

referencableObjectTypes = {
        qname("{https://xbrl.org/2025}xbrl:taxonomyObject"): XbrlModule,
        qname("{https://xbrl.org/2025}xbrl:exportProfileObject"): XbrlExportProfile,
        qname("{https://xbrl.org/2025}xbrl:conceptObject"): XbrlConcept,
        qname("{https://xbrl.org/2025}xbrl:abstractObject"): XbrlAbstract,
        qname("{https://xbrl.org/2025}xbrl:cubeObject"): XbrlCube,
        qname("{https://xbrl.org/2025}xbrl:dimensionObject"): XbrlDimension,
        qname("{https://xbrl.org/2025}xbrl:domainObject"): XbrlDomain,
        qname("{https://xbrl.org/2025}xbrl:domainRootObject"): XbrlDomainRoot,
        qname("{https://xbrl.org/2025}xbrl:entityObject"): XbrlEntity,
        qname("{https://xbrl.org/2025}xbrl:factspaceObject"): XbrlFactspace,
        qname("{https://xbrl.org/2025}xbrl:finalTaxonomyObject"): XbrlFinalTaxonomy,
        qname("{https://xbrl.org/2025}xbrl:footnoteObject"): XbrlFootnote,
        qname("{https://xbrl.org/2025}xbrl:groupObject"): XbrlGroup,
        qname("{https://xbrl.org/2025}xbrl:groupTreeObject"): XbrlGroupTree,
        qname("{https://xbrl.org/2025}xbrl:networkObject"): XbrlNetwork,
        qname("{https://xbrl.org/2025}xbrl:relationshipTypeObject"): XbrlRelationshipType,
        qname("{https://xbrl.org/2025}xbrl:memberObject"): XbrlMember,
        qname("{https://xbrl.org/2025}xbrl:referenceObject"): XbrlReference,
        qname("{https://xbrl.org/2025}xbrl:unitObject"): XbrlUnit,
        qname("{https://xbrl.org/2025}xbrl:dataTypeObject"): XbrlDataType,
        qname("{https://xbrl.org/2025}xbrl:propertyTypeObject"): XbrlPropertyType,
        qname("{https://xbrl.org/2025}xbrl:labelTypeObject"): XbrlLabelType,
        qname("{https://xbrl.org/2025}xbrl:referenceTypeObject"): XbrlReferenceType,
        qname("{https://xbrl.org/2025}xbrl:cubeTypeObject"): XbrlCubeType,
        qname("{https://xbrl.org/2025}xbrl:unitTypeObject"): XbrlUnitType,
        qname("{https://xbrl.org/2025}xbrl:transformObject"): XbrlTransform,
        qname("{https://xbrl.org/2025}xbrl:layoutObject"): XbrlLayout,
        qname("{https://xbrl.org/2025}xbrl:tableTemplateObject"): XbrlTableTemplate,
        qname("{https://xbrl.org/2025}xbrl:dataTableObject"): XbrlDataTable,
    }
nonReferencableObjectTypes = {
        qname("{https://xbrl.org/2025}xbrl:importTaxonomyObject"): XbrlImportTaxonomy,
        qname("{https://xbrl.org/2025}xbrl:cubeDimensionObject"): XbrlCubeDimension,
        qname("{https://xbrl.org/2025}xbrl:groupContentObject"): XbrlGroupContent,
        qname("{https://xbrl.org/2025}xbrl:periodConstraintObject"): XbrlPeriodConstraint,
        qname("{https://xbrl.org/2025}xbrl:dateResolutionObject"): XbrlDateResolution,
        qname("{https://xbrl.org/2025}xbrl:relationshipObject"): XbrlRelationship,
        qname("{https://xbrl.org/2025}xbrl:relationshipConstraintObject"): XbrlRelationshipConstraint,
        qname("{https://xbrl.org/2025}xbrl:labelObject"): XbrlLabel,
        qname("{https://xbrl.org/2025}xbrl:propertyObject"): XbrlProperty,
        qname("{https://xbrl.org/2025}xbrl:allowedCubeDimensionObject"): XbrlAllowedCubeDimension,
        qname("{https://xbrl.org/2025}xbrl:requiredCubeRelationshipObject"): XbrlRequiredCubeRelationship,
        qname("{https://xbrl.org/2025}xbrl:axisObject"): XbrlAxis,
        qname("{https://xbrl.org/2025}xbrl:axisDimensionObject"): XbrlAxisDimension,
    }
xbrlObjectTypes = referencableObjectTypes | nonReferencableObjectTypes
xbrlObjectQNames = dict((v,k) for k,v in xbrlObjectTypes.items())
