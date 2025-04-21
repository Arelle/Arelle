"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union
from collections import OrderedDict

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .ModelValueMore import SQName
from .XbrlDts import XbrlDts
from .XbrlImportedTaxonomy import XbrlImportedTaxonomy
from .XbrlProperty import XbrlProperty
from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType
from .XbrlCube import XbrlCube, XbrlCubeType
from .XbrlDimension import XbrlDimension, XbrlDomain, XbrlMember
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlLabel import XbrlLabel
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTypes import QNameKeyType, XbrlTaxonomyType
from .XbrlTaxonomyObject import XbrlTaxonomyObject

class XbrlTaxonomy(XbrlTaxonomyObject):
    dts: XbrlDts
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the taxonomy object.
    familyName: Optional[str] # (optional) The family name of the taxonomy such as "US-GAAP" that indicates the taxonomy broad taxonomy family. The family name stays consistent between regular taxonomy releases of the same taxonomy domain.
    version: Optional[str] # (optional) Used to identify the version of the taxonomy such as the year of release.
    entryPoint: AnyURI # (required) The uri entry point location of the taxonomy object that is used to locate the taxonomy.
    importedTaxonomies: OrderedSet[XbrlImportedTaxonomy] # ordered set of importedTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
    abstracts: OrderedSet[XbrlAbstract] # ordered set of abstract objects.
    concepts: OrderedSet[XbrlConcept] # ordered set of concept objects.
    cubes: OrderedSet[XbrlCube] # ordered set of cube objects.
    cubeTypes: OrderedSet[XbrlCubeType] # ordered set of cubeType objects.
    dataTypes: OrderedSet[XbrlDataType] # ordered set of dataType objects.
    dimensions: OrderedSet[XbrlDimension] # ordered set of dimension objects.
    domains: OrderedSet[XbrlDomain] # (optional) ordered set of domain objects.
    entities: OrderedDict[SQName, XbrlEntity] # (optional) ordered set of entity objects.
    groups: OrderedSet[XbrlGroup] #  ordered set of group objects.
    groupContents: OrderedSet[XbrlGroupContent] # ordered set of groupContent objects that link a group QName to a list of network or cube objects.
    labels: OrderedSet[XbrlLabel] # ordered set of label objects.
    members: OrderedSet[XbrlMember] #  ordered set of member objects.
    networks: OrderedSet[XbrlNetwork] # ordered set of network objects.
    propertyTypes: OrderedSet[XbrlPropertyType] # ordered set of propertyType objects.
    references: OrderedSet[XbrlReference] # ordered set of reference objects.
    referenceTypes: OrderedSet[XbrlReferenceType] # ordered set of referenceType objects.
    relationshipTypes: OrderedSet[XbrlRelationshipType] # ordered set of relationshipType objects.
    #tableTemplates: OrderedSet[XbrlTableType] # ordered set of tableTemplate objects.
    transforms: OrderedSet[XbrlTransform] # (optional) an ordered set of transform objects.
    units: OrderedSet[XbrlUnit] # ordered set of unit objects.
    properties: OrderedSet[XbrlProperty] # ordered set of property objects used to specify additional properties associated with the taxonomy. Only immutable properties as defined in the propertyType object can be added to a taxonom
