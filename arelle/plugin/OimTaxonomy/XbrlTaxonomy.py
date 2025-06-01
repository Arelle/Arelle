"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union
from collections import OrderedDict

from arelle.ModelValue import qname, QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .ModelValueMore import SQName
from .XbrlDts import XbrlDts
from .XbrlImportedTaxonomy import XbrlImportedTaxonomy
from .XbrlProperty import XbrlProperty
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlCube import XbrlCube, XbrlCubeType, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlDomainRoot, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTypes import QNameKeyType, XbrlTaxonomyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject
from .XbrlTableTemplate import XbrlTableTemplate, XbrlDataTable

class XbrlTaxonomy(XbrlTaxonomyObject):
    dts: XbrlDts
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the taxonomy object.
    frameworkName: Optional[str] # (optional) The framework name of the taxonomy such as "US-GAAP" that indicates the taxonomy broad taxonomy family. The framework name stays consistent between regular taxonomy releases of the same taxonomy domain.
    version: Optional[str] # (optional) Used to identify the version of the taxonomy such as the year of release.
    resolved: bool # (required) Used to indicate if the taxonomy is in a resolved form. Allowable values are true or false. True indicates that the taxonomy is a complete model including all objects post dts processing that has resolved all importedTaxonomy objects, extendTargetName attributes and domain filters. False indicates that the taxonomy is pre dts processing and is not in resolved form.
    importedTaxonomies: OrderedSet[XbrlImportedTaxonomy] # ordered set of importedTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
    abstracts: OrderedSet[XbrlAbstract] # ordered set of abstract objects.
    concepts: OrderedSet[XbrlConcept] # ordered set of concept objects.
    cubes: OrderedSet[XbrlCube] # ordered set of cube objects.
    cubeTypes: OrderedSet[XbrlCubeType] # ordered set of cubeType objects.
    dataTypes: OrderedSet[XbrlDataType] # ordered set of dataType objects.
    dimensions: OrderedSet[XbrlDimension] # ordered set of dimension objects.
    domains: OrderedSet[XbrlDomain] # (optional) ordered set of domain objects.
    domainRoots: OrderedSet[XbrlDomainRoot] # (optional) ordered set of domain root objects.
    entities: OrderedSet[XbrlEntity] # (optional) ordered set of entity objects.
    groups: OrderedSet[XbrlGroup] #  ordered set of group objects.
    groupContents: OrderedSet[XbrlGroupContent] # ordered set of groupContent objects that link a group QName to a list of network or cube objects.
    labels: OrderedSet[XbrlLabel] # ordered set of label objects.
    members: OrderedSet[XbrlMember] #  ordered set of member objects.
    networks: OrderedSet[XbrlNetwork] # ordered set of network objects.
    propertyTypes: OrderedSet[XbrlPropertyType] # ordered set of propertyType objects.
    references: OrderedSet[XbrlReference] # ordered set of reference objects.
    labelTypes: OrderedSet[XbrlLabelType] # rdered set of labelType objects.
    referenceTypes: OrderedSet[XbrlReferenceType] # ordered set of referenceType objects.
    relationshipTypes: OrderedSet[XbrlRelationshipType] # ordered set of relationshipType objects.
    tableTemplates: OrderedSet[XbrlTableTemplate] # ordered set of tableTemplate objects.
    dataTables: OrderedSet[XbrlDataTable] # (optional) ordered set of dataTable objects.
    transforms: OrderedSet[XbrlTransform] # (optional) an ordered set of transform objects.
    units: OrderedSet[XbrlUnit] # ordered set of unit objects.
    properties: OrderedSet[XbrlProperty] # ordered set of property objects used to specify additional properties associated with the taxonomy. Only immutable properties as defined in the propertyType object can be added to a taxonom

xbrlObjectTypes = {
        qname("{https://xbrl.org/2025}xbrl:taxonomyObject"): XbrlTaxonomy,
        qname("{https://xbrl.org/2025}xbrl:importTaxonomyObject"): XbrlImportedTaxonomy,
        qname("{https://xbrl.org/2025}xbrl:conceptObject"): XbrlConcept,
        qname("{https://xbrl.org/2025}xbrl:abstractObject"): XbrlAbstract,
        qname("{https://xbrl.org/2025}xbrl:cubeObject"): XbrlCube,
        qname("{https://xbrl.org/2025}xbrl:cubeDimensionObject"): XbrlCubeDimension,
        qname("{https://xbrl.org/2025}xbrl:periodConstraintObject"): XbrlPeriodConstraint,
        qname("{https://xbrl.org/2025}xbrl:dateResolutionObject"): XbrlDateResolution,
        qname("{https://xbrl.org/2025}xbrl:dimensionObject"): XbrlDimension,
        qname("{https://xbrl.org/2025}xbrl:domainObject"): XbrlDomain,
        qname("{https://xbrl.org/2025}xbrl:entityObject"): XbrlEntity,
        qname("{https://xbrl.org/2025}xbrl:groupObject"): XbrlGroup,
        qname("{https://xbrl.org/2025}xbrl:groupContentObject"): XbrlGroupContent,
        qname("{https://xbrl.org/2025}xbrl:networkObject"): XbrlNetwork,
        qname("{https://xbrl.org/2025}xbrl:relationshipObject"): XbrlRelationship,
        qname("{https://xbrl.org/2025}xbrl:relationshipTypeObject"): XbrlRelationshipType,
        qname("{https://xbrl.org/2025}xbrl:labelObject"): XbrlLabel,
        qname("{https://xbrl.org/2025}xbrl:memberObject"): XbrlMember,
        qname("{https://xbrl.org/2025}xbrl:propertyObject"): XbrlProperty,
        qname("{https://xbrl.org/2025}xbrl:referenceObject"): XbrlReference,
        qname("{https://xbrl.org/2025}xbrl:dataTypeObject"): XbrlDataType,
        qname("{https://xbrl.org/2025}xbrl:propertyTypeObject"): XbrlPropertyType,
        qname("{https://xbrl.org/2025}xbrl:labelTypeObject"): XbrlLabelType,
        qname("{https://xbrl.org/2025}xbrl:referenceTypeObject"): XbrlReferenceType,
        qname("{https://xbrl.org/2025}xbrl:cubeTypeObject"): XbrlCubeType,
        qname("{https://xbrl.org/2025}xbrl:tableTemplateObject"): XbrlTableTemplate,
        qname("{https://xbrl.org/2025}xbrl:transformObject"): XbrlTransform,
        qname("{https://xbrl.org/2025}xbrl:unitObject"): XbrlUnit,
        qname("{https://xbrl.org/2025}xbrl:unitTypeObject"): XbrlUnitType,
    }
xbrlObjectQNames = dict((v,k) for k,v in xbrlObjectTypes.items())
