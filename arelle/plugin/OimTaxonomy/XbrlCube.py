"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union

from arelle.ModelValue import qname, QName, DateTime, YearMonthDayTimeDuration
from arelle.PythonUtil import OrderedSet
from .XbrlConst import xbrl
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, DefaultTrue, DefaultFalse
from .ModelValueMore import QNameAt, SQName
from .XbrlTaxonomyObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject

class XbrlDateResolution(XbrlTaxonomyObject):
    conceptName: Optional[QName] # (optional) Identifies the QName of a concept object that has a date fact value. The values of the concept object resolves to a set of dates. If no value exists in the report then the property is ignored, and no date constraint is enforced on the cube.
    context: Optional[QNameAt] # (optional) Identifies the QName of a concept object that has a value. The context of the fact values resolves to a set of dates. If no value exists in the report then the property is ignored. The context suffix must be either @end or @start. If an @ value is not provided then the suffix defaults to @end.
    value: Optional[DateTime] # (optional) A literal date value representing the end date.
    timeShift: Optional[YearMonthDayTimeDuration] # (optional) Defines a time duration shift from the date derived form either the value, context or name properties. The duration of the time shift is defined using the XML duration type to define a duration of time. A negative operator is used to deduct the timeShift from the resolved date.

class XbrlPeriodConstraint(XbrlTaxonomyObject):
    periodType: str # (required) Used to indicate if the period is an instant or a duration.
    timeSpan: Optional[str] # (optional) Defines a duration of time using the XML duration type to define a duration of time. The duration of the time span maps to facts with the same duration.
    periodFormat: Optional[str] # (optional) Defines a a duration of time with an end date. The period value defined in the taxonomy must resolve to a valid period format as defined in xbrl-csv specification.
    monthDay: Optional[XbrlDateResolution] # (optional) Represents a Gregorian date that recurs such as 04-16. The date resolution object when used with this property returns the date without the year. The conceptName property of the dateResolution object can also use a datatype of monthDay.
    endDate: Optional[XbrlDateResolution] # (optional) Defines an end date for a duration fact and the date of an instant fact. Values can be provided as a literal date value, a fact with a date value, or the date context value of a date. A suffix of @start or @end may be added to any of the date formats, specifying the instant at the start or end end of the duration, respectively.
    startDate: Optional[XbrlDateResolution] # (optional) Defines a start date for a duration fact and the date of an instant fact. Values can be provided as a literal date value, a fact with a date value, or the date context value of a date. A suffix of @start or @end may be added to any of the date formats, specifying the instant at the start or end end of the duration, respectively.
    onOrAfter: Optional[XbrlDateResolution] # (optional) Defines a date where all instant facts on or after the date are included in the cube. For a duration fact any periods after or on the end date of the duration are included in the cube.
    onOrBefore: Optional[XbrlDateResolution] # (optional) Defines a date where all instant facts before or on the date are included in the cube. For a duration fact any periods before or on the end date are included in the cube.

class XbrlCubeDimension(XbrlTaxonomyObject):
    dimensionName: QName # (required) The QName of the dimension object that is used to identify the dimension. For the core dimensions of concept, period, entity and unit, the core dimension QNames of xbrl:concept, xbrl:period, xbrl:entity, xbrl:unit and xbrl:language are used. The dimension object indicates if the dimension is typed or explicit.
    domainName: Optional[QName] # (required if explicit dimension) The QName of the domain object that is used to identify the domain associated with the dimension. Only one domain can be associated with a dimension. The domain name cannot be provided for a typed dimension or the period core dimension.
    domainSort: Optional[str] # (optional if typed dimension) A string value that indicates the sort order of the typed dimension. The values can be either asc or desc. The values are case insensitive. This indicates if the cube is viewed the order of the values shown on the typed dimension. This cannot be used on an explicit dimension.
    allowDomainFacts: Union[bool, DefaultFalse] # (optional    ) A boolean value that indicates if facts not identified with the dimension are included in the cube. For typed and explicit dimensions the value defaults to false. A value of true for a typed or explicit dimension will include facts that don't use the dimension in the cube. For the period core dimension, forever facts or facts with no period dimension are included when this value is set to true. For units, this is a unit with no units such as a string or date. For the entity core dimension, it is fact values with no entity. This property cannot be used on the concept core dimension.
    periodConstraints: set[XbrlPeriodConstraint] # (optional only for period core dimension) Defines an ordered set of periodConstraint objects to restrict fact values in a cube to fact values with a specified period.

class XbrlCube(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name property is a QName that uniquely identifies the cube object.
    cubeType: Optional[QName] # (optional) The cubeType property identifies the type of data cube being represented. This must match a defined cubeType object or specification defined cube types of xbrl:eventCube, xbrl:positionCube, xbrl:referenceCube, xbrl:reportCube, xbrl:journalCube, xbrl:eventDetailsCube, xbrl:timeSeriesCube and xbrl:defaultCube. If no QName is provided the default is xbrl:reportCube.
    cubeDimensions: OrderedSet[XbrlCubeDimension] # (required) An ordered set of cubeDimension objects that identify the dimensions and associated domains used on the cube.
    cubeNetworks: OrderedSet[QName] # (optional) An ordered set of network object QNames that reference network objects that are directly related to the cube.
    excludeCubes: OrderedSet[QName] # (optional) An ordered set of cube object QNames that remove the facts of the constraint cube from the facts of the defined cube.
    cubeComplete: Optional[bool] # (optional) A boolean flag that indicates if all cells in the cube are required to have a value. If true then all cube cells must include a fact value. If a value is not provided for the cubeComplete property then the default is false.
    properties: OrderedSet[XbrlProperty] # (optional) An ordered set of property objects Used to specify additional properties associated with the cube using the property object. Only immutable properties as defined in the propertyType object can be added to a cube.

class XbrlAllowedCubeDimension(XbrlTaxonomyObject):
    dimensionName: Optional[QName] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    dimensionType: Optional[str] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    dimensionDataType: Optional[QName] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    required: Union[bool, DefaultFalse] # (optional) The dimension QName that identifies the taxonomy defined dimension.

class XbrlRequiredCubeRelationship(XbrlTaxonomyObject):
    relationshipTypeName: QName # (required) The relationship type QName of a relationship. This requires that at lease one of these relationship types exist on the cube.
    source: Optional[QName] # (optional) The QName of the source object type in the relationship.
    target: Optional[QName] # (optional) The QName of the target object type in the relationship.

class XbrlCubeType(XbrlReferencableTaxonomyObject):
    taxonomy: XbrlTaxonomyType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the cube type object.
    baseCubeType: Union[bool, DefaultTrue] # (optional) Base cube type that the cube object is based on. Uses the QName of a cubeType object. The property only allows restriction rather than expansion of the baseCubeTape.
    periodDimension: Union[bool, DefaultTrue] # (optional) boolean to indicate if the period core dimension is included in the cube. Defaults to true.
    entityDimension: Union[bool, DefaultTrue] # (optional) boolean to indicate if the entity core dimension is included in the cube. Defaults to true.
    unitDimension: Union[bool, DefaultTrue] # (optional) boolean to indicate if the unit core dimension is included in the cube. Defaults to true.
    taxonomyDefinedDimension: Union[bool, DefaultTrue] # (optional) boolean to indicate if taxonomy defined dimensions are included in the cube. Defaults to true.
    allowedCubeDimensions: OrderedSet[XbrlAllowedCubeDimension] # (optional) An ordered set of allowedCubeDimension objects that are permitted to be used on the cube. If the property is not defined then any dimensions can be associated with the cube.
    requiredCubeRelationships: OrderedSet[XbrlRequiredCubeRelationship] # (optional) An ordered set of requiredCubeRelationship objects that at a minimum must be associated with the cube.

baseCubeTypes = {
    qname(xbrl, "xbrl:eventCube"),
    qname(xbrl, "xbrl:positionCube"),
    qname(xbrl, "xbrl:referenceCube"),
    qname(xbrl, "xbrl:reportCube"),
    qname(xbrl, "xbrl:journalCube"),
    qname(xbrl, "xbrl:eventDetailsCube"),
    qname(xbrl, "xbrl:timeSeriesCube"),
    qname(xbrl, "xbrl:defaultCube")
    }

periodCoreDim = qname(xbrl, "xbrl:period")
conceptCoreDim = qname(xbrl, "xbrl:concept")
entityCoreDim = qname(xbrl, "xbrl:entity")
unitCoreDim = qname(xbrl, "xbrl:unit")
languageCoreDim = qname(xbrl, "xbrl:language")

coreDimensions = {periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim}

conceptDomainRoot = qname(xbrl, "xbrl:conceptDomain")
entityDomainRoot = qname(xbrl, "xbrl:entityDomain")
unitDomainRoot = qname(xbrl, "xbrl:unitDomain")
