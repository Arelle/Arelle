"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING

from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlDts import XbrlDts

class XbrlTaxonomy:
    def __init__(self,
                 xbrlDts: XbrlDts,
                 name: QName, 
                 entryPoint: AnyURI,
                 familyName: str | None = None, 
                 version: str | None = None):
        self.xbrlDts: xbrlDts
        self.name: QName = name # (required) The name is a QName that uniquely identifies the taxonomy object.
        self.familyName: str | None = familyName # (optional) The family name of the taxonomy such as "US-GAAP" that indicates the taxonomy broad taxonomy family. The family name stays consistent between regular taxonomy releases of the same taxonomy domain.
        self.version: str | None = version # (optional) Used to identify the version of the taxonomy such as the year of release.
        self.entryPoint: AnyURI = entryPoint # (required) The uri entry point location of the taxonomy object that is used to locate the taxonomy.
        self.importedTaxonomies: OrderedSet[XbrlTaxonomy] = OrderedSet() # ordered set of importedTaxonomy objects that can comprise QName of the taxonomy to be imported, an object type or a taxonomy object referenced by its QName.
        self.abstracts: OrderedSet[XbrlAbstract] = OrderedSet() # ordered set of abstract objects.
        self.concepts: OrderedSet[XbrlConcept] = OrderedSet() # ordered set of concept objects.
        self.cubes: OrderedSet[XbrlCube] = OrderedSet() # ordered set of cube objects.
        self.cubeTypes: OrderedSet[XbrlCubeType] = OrderedSet() # ordered set of cubeType objects.
        self.dataTypes: OrderedSet[XbrlDataType] = OrderedSet() # ordered set of dataType objects.
        self.dimensions: OrderedSet[XbrlDimwnaion] = OrderedSet() # ordered set of dimension objects.
        self.domains: OrderedSet[XbrlDomain] = OrderedSet() # (optional) ordered set of domain objects.
        self.entities: OrderedSet[XbrlEntity] = OrderedSet() # (optional) ordered set of entity objects.
        self.groups:OrderedSet[XbrlGroups] = OrderedSet() #  ordered set of group objects.
        self.groupContents: OrderedSet[XbrlGroupContent] = OrderedSet() # ordered set of groupContent objects that link a group QName to a list of network or cube objects.
        self.labels: OrderedSet[XbrlLabel] = OrderedSet() # ordered set of label objects.
        self.members: OrderedSet[XbrlMember] = OrderedSet() #  ordered set of member objects.
        self.networks: OrderedSet[XbrlNetwork] = OrderedSet() # ordered set of network objects.
        self.propertyTypes: OrderedSet[XbrlProperty] = OrderedSet() # ordered set of propertyType objects.
        self.references: OrderedSet[XbrlReference] = OrderedSet() # ordered set of reference objects.
        self.referenceTypes: OrderedSet[XbrlReferenceType] = OrderedSet() # ordered set of referenceType objects.
        self.relationshipTypes: OrderedSet[XbrlRelationshipType] = OrderedSet() # ordered set of relationshipType objects.
        self.tableTemplates: OrderedSet[XbrlTableType] = OrderedSet() # ordered set of tableTemplate objects.
        self.units: OrderedSet[XbrlUnit] = OrderedSet() # ordered set of unit objects.
        self.properties: OrderedSet[XbrlProperty] = OrderedSet() # ordered set of property objects used to specify additional properties associated with the taxonomy. Only immutable properties as defined in the propertyType object can be added to a taxonomy.
        self.transforms: OrderedSet[XbrlTransform] = OrderedSet() #