"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, List
import regex as re
from collections.abc import Iterable

from arelle.ModelValue import qname, QName, DateTime, YearMonthDayTimeDuration
from arelle.PythonUtil import OrderedSet
from arelle.oim.Load import EMPTY_DICT
from .XbrlConst import xbrl
from .XbrlDimension import XbrlDomain
from .XbrlProperty import XbrlProperty
from .XbrlTypes import XbrlModuleType, QNameKeyType, DefaultTrue, DefaultFalse
from .ModelValueMore import QNameAt, SQName
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject
from arelle.FunctionFn import true, false

class XbrlDateResolution(XbrlModelObject):
    conceptName: Optional[QName] # (optional) Identifies the QName of a concept object that has a date fact value. The values of the concept object resolves to a set of dates. If no value exists in the report then the property is ignored, and no date constraint is enforced on the cube.
    context: Optional[QNameAt] # (optional) Identifies the QName of a concept object that has a value. The context of the fact values resolves to a set of dates. If no value exists in the report then the property is ignored. The context suffix must be either @end or @start. If an @ value is not provided then the suffix defaults to @end.
    value: Optional[DateTime] # (optional) A literal date value representing the end date.
    timeShift: Optional[YearMonthDayTimeDuration] # (optional) Defines a time duration shift from the date derived form either the value, context or name properties. The duration of the time shift is defined using the XML duration type to define a duration of time. A negative operator is used to deduct the timeShift from the resolved date.

periodConstraintPeriodPattern = re.compile(
    r"^(?P<stDt>(?P<stYr>\d{4}|YYYY)-(?P<stMo>0[1-9]|1[0-2]|MM)-(?P<stDa>0[1-9]|[12]\d|3[01]|DD|eom))(T(?P<stHr>[01]\d|2[0-4]|hh):(?P<stMn>[0-5]\d|60|mm)(:(?P<stSc>[0-5]\d|60|ss))?)?(/((?P<EnDt>(?P<enYr>\d{4}|YYYY)-(?P<enMo>0[1-9]|1[0-2]|MM)-(?P<enDa>0[1-9]|[12]\d|3[01]|DD|eom))(T(?P<enHr>[01]\d|2[0-4]|hh):(?P<enMn>[0-5]\d|60|mm)(:(?P<enSc>[0-5]\d|60|ss))?)?))?")

class XbrlPeriodConstraint(XbrlModelObject):
    periodType: str # (required) Used to indicate if the period is an instant or a duration.
    timeSpan: Optional[str] # (optional) Defines a duration of time using the XML duration type to define a duration of time. The duration of the time span maps to facts with the same duration.
    periodPattern: Optional[str] # (optional) Defines a date or duration pattern that is used to select dates or durations.
    endDate: Optional[XbrlDateResolution] # (optional) Defines an end date for a duration fact and the date of an instant fact. Values can be provided as a literal date value, a fact with a date value, or the date context value of a date. A suffix of @start or @end may be added to any of the date formats, specifying the instant at the start or end end of the duration, respectively.
    startDate: Optional[XbrlDateResolution] # (optional) Defines a start date for a duration fact and the date of an instant fact. Values can be provided as a literal date value, a fact with a date value, or the date context value of a date. A suffix of @start or @end may be added to any of the date formats, specifying the instant at the start or end end of the duration, respectively.
    onOrAfter: Optional[XbrlDateResolution] # (optional) Defines a date where all instant facts on or after the date are included in the cube. For a duration fact any periods after or on the end date of the duration are included in the cube.
    onOrBefore: Optional[XbrlDateResolution] # (optional) Defines a date where all instant facts before or on the date are included in the cube. For a duration fact any periods before or on the end date are included in the cube.

    def periodPatternMatch(self, perVal):
        if not self.periodPattern or not self._periodPatternDict:
            return None # no period pattern check
        m = periodConstraintPeriodPattern.match(perVal)
        if not m:
            return False # period not processable to match, fail constraint
        perValDict = m.groupdict()
        for prop in ("stYr","stMo","stDa", "stHr", "stMn", "stSc", "enYr","enMo","enDa", "enHr", "enMn", "enSc"):
            if not self._periodPatternDict[prop] in (None, "YYYY", "MM", "DD", "hh", "mm", "SS") and perValDict[prop] is not None:
                if self._periodPatternDict[prop] == "eom":
                    dt = datetime.strptime(perValDict[prop[:2]+"Dt"])
                    if dt.day != calendar.monthrange(dt.year, dt.month)[1]:
                        return False
                else:
                    if self._periodPatternDict[prop] != perValDict[prop]:
                        return False
        return True


class XbrlCubeDimension(XbrlModelObject):
    dimensionName: QName # (required) The QName of the dimension object that is used to identify the dimension. For the core dimensions of concept, period, entity and unit, the core dimension QNames of xbrl:concept, xbrl:period, xbrl:entity, xbrl:unit and xbrl:language are used. The dimension object indicates if the dimension is typed or explicit.
    domainName: Optional[QName] # (required if explicit dimension) The QName of the domain object that is used to identify the domain associated with the dimension. Only one domain can be associated with a dimension. The domain name cannot be provided for a typed dimension or the period core dimension.
    domainDataType: Optional[QName] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    typedSort: Optional[str] # (optional if typed dimension) A string value that indicates the sort order of the typed dimension. The values can be either asc or desc. This indicates the viewing order of the values using a typed dimension. The typedSort property cannot be used with an explicit dimension. The typedSort can be used with the period dimension. The sort order is applied to each period constraint defined in periodConstraints. If there are two period constraints the first for instant and the second for duration and a typedSort of asc then all instant dates appear first ascending, then all duration dates appear second in ascending order.
    allowDomainFacts: Union[bool, DefaultFalse] # (optional) A boolean value that indicates if facts not identified with the dimension are included in the cube. For typed and explicit dimensions the value defaults to false. A value of true for a typed or explicit dimension will include facts that don't use the dimension in the cube. For the period core dimension, forever facts or facts with no period dimension are included when this value is set to true. For units, this is a unit with no units such as a string or date. For the entity core dimension, it is fact values with no entity. This property cannot be used on the concept core dimension.
    periodConstraints: set[XbrlPeriodConstraint] # (optional only for period core dimension) Defines an ordered set of periodConstraint objects to restrict fact values in a cube to fact values with a specified period.

    def allowedMembers(self, txmyMdl):
        try:
            return self._allowedMembers
        except AttributeError:
            self._allowedMembers = mem = OrderedSet()
            domObj = txmyMdl.namedObjects.get(self.domainName)
            if isinstance(domObj, XbrlDomain):
                if self.allowDomainFacts:
                    mem.add(domObj.root)
                for relObj in domObj.relationships:
                    mem.add(relObj.target)
            return self._allowedMembers

class XbrlCube(XbrlReferencableModelObject):
    module: XbrlModuleType
    name: QNameKeyType # (required) The name property is a QName that uniquely identifies the cube object.
    cubeType: Optional[QName] # (optional) The cubeType property identifies the type of data cube being represented. This must match a defined cubeType object or specification defined cube types of xbrl:eventCube, xbrl:positionCube, xbrl:referenceCube, xbrl:reportCube, xbrl:journalCube, xbrl:eventDetailsCube, xbrl:timeSeriesCube and xbrl:defaultCube. If no QName is provided the default is xbrl:reportCube.
    cubeDimensions: OrderedSet[XbrlCubeDimension] # (required) An ordered set of cubeDimension objects that identify the dimensions and associated domains used on the cube.
    cubeNetworks: OrderedSet[QName] # (optional) An ordered set of network object QNames that reference network objects that are directly related to the cube.
    excludeCubes: OrderedSet[QName] # (optional) An ordered set of cube object QNames that remove the facts of the constraint cube from the facts of the defined cube.
    cubeComplete: Optional[bool] # (optional) A boolean flag that indicates if all cells in the cube are required to have a value. If true then all cube cells must include a fact value. If a value is not provided for the cubeComplete property then the default is false.
    properties: OrderedSet[XbrlProperty] # (optional) An ordered set of property objects Used to specify additional properties associated with the cube using the property object. Only immutable properties as defined in the propertyType object can be added to a cube.

class XbrlDimensionPropertiesConstraint(XbrlModelObject):
    allowed: OrderedSet[QName] # (optional) An ordered set of property type QNames that can be used on the dimension.
    required: OrderedSet[QName] # (optional) An ordered set of property type QNames that must be used on the dimension.

class XbrlDimensionConstraint(XbrlModelObject):
    dimensionName: Optional[QName] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    type: Optional[str] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    dataType: Optional[QName] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    required: Optional[bool] # (optional) The dimension QName that identifies the taxonomy defined dimension.
    dimensionProperties: Optional[XbrlDimensionPropertiesConstraint] # (optional) Defines constraints on dimension properties defining those properties that are allowed.

class XbrlDimensionsAllowed(XbrlModelObject):
    allowed: OrderedSet[XbrlDimensionConstraint] # (optional) An ordered set of dimension constraint objects. (xbrl:dimensionConstraintObject) The dimension constraint defines the constraints on dimensions that can be included in cubes of this type.
    closed: Optional[bool] # (optional) If true, only dimensions listed in allowed can be used. If false, other taxonomy-defined dimensions are permitted. Defaults to false.

class XbrlVertexConstraint(XbrlModelObject):
    qname: Optional[QName] # (optional) Specific source or target QName
    objectType: Optional[QName] # (optional) Source or target object type QName (e.g., xbrl:conceptObject)
    dataType: Optional[QName] # (optional) Source or target data type QName

    def __eq__(self, other):
        if not isinstance(other, XbrlVertexConstraint):
            return NotImplemented
        return self.qname == other.qname and self.objectType == other.objectType and self.dataType == other.dataType

class XbrlCubeRelationshipConstraint(XbrlModelObject):
    type: Optional[QName] # (optional) The relationship type QName
    source: Optional[XbrlVertexConstraint] # (optional) Constraints on the relationship source. Use the xbrl:vertexConstraintObject to define the constraints on the source of the relationship.
    target: Optional[XbrlVertexConstraint] # (optional) Constraints on the relationship target. Use the xbrl:vertexConstraintObject to define the constraints on the target of the relationship.

    def __eq__(self, other):
        if not isinstance(other, XbrlCubeRelationshipConstraint):
            return NotImplemented
        return self.type == other.type and self.source == other.source and self.target == self.target


class XbrlCubeRelationshipAllowed(XbrlModelObject):
    required: List[XbrlCubeRelationshipConstraint] # (optional)An ordered set of cube relationships constraint objects (xbrl:cubeRelationshipConstraintObject) that must be present.
    allowed: List[XbrlCubeRelationshipConstraint] # (optional) An ordered set of cube relationships constraint objects (xbrl:cubeRelationshipConstraintObject) that are permitted, using the same format as required.

class XbrlCubePropertiesConstraint(XbrlModelObject):
    required: OrderedSet[QName] # (optional) An ordered set of property type QNames that must be associated with cubes of this type.
    allowed: OrderedSet[QName] # (optional) An ordered set of property type QNames that are permitted on cubes of this type. If not specified, any property type defined in the taxonomy can be used.

class XbrlCubeType(XbrlReferencableModelObject):
    module: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the cube type object.
    # Optional properties may be inherited so they don't default until checking inheritance chain
    baseCubeType: Optional[QName] # (optional) Base cube type that the cube object is based on. Uses the QName of a cubeType object. The property only allows restriction rather than expansion of the baseCubeTape.
    coreDimensions: OrderedSet[QName] # (optional) An ordered set of core dimension QNames that are permitted to be included in the cube.
    cubeDimensionConstraints: Optional[XbrlDimensionsAllowed] # (optional) An object that defines constraints on taxonomy-defined dimensions that can be included in the cube.
    cubeRelationships: Optional[XbrlCubeRelationshipAllowed] # (optional) An object that defines constraints on relationships that can be associated with the cube.
    cubeProperties: Optional[XbrlCubePropertiesConstraint] # (optional) An object that defines constraints on properties that can be associated with the cube.

    def effectivePropVal(self, compMdl, *propNames): # property effective value considering inheritance and default value if not on basemost cube type
        obj = self
        accumVal = None # accumulate OrderedSet contents inherited
        for propName in propNames: # e.g. (cuubeDimensions, closed)
            val = getattr(obj, propName, None)
            if isinstance(val, XbrlModelObject):
                obj = val
            elif isinstance(val, Iterable):
                if val: # e.g. nonempty OrderedSet
                    #accumVal = val # add these to inherited set contents
                    #break
                    return val # TBD: ensure there is no need to accumulate among the base items
            elif val is not None: # not an iterable and has a non-None value such as boolean False or int 0
                return val
        # check if there's a base type with a value
        baseCubeType = compMdl.namedObjects.get(self.baseCubeType)
        if isinstance(baseCubeType, XbrlCubeType):
            baseEffectiveVal = baseCubeType.effectivePropVal(compMdl, propName)
            if accumVal is not None and isinstance(baseEffectiveVal, Iterable):
                return accumVal | baseEffectiveVal
            return baseEffectiveVal
        if accumVal:
            return accumVal
        # no base type so return this object's default value
        if propNames[-1] in ("baseCubeType", "closed"): # scalars
            return None
        return set() # set object

    def basemostCubeType(self, compMdl):
        baseCubeType = compMdl.namedObjects.get(self.baseCubeType)
        if isinstance(baseCubeType, XbrlCubeType):
            return baseCubeType.basemostCubeType
        return self.name

eventCubeType = qname(xbrl, "xbrl:eventCube")
positionCubeType = qname(xbrl, "xbrl:positionCube")
referenceCubeType = qname(xbrl, "xbrl:referenceCube")
reportCubeType = qname(xbrl, "xbrl:reportCube")
journalCubeType = qname(xbrl, "xbrl:journalCube")
eventDetailsCubeType = qname(xbrl, "xbrl:eventDetailsCube")
timeSeriesCubeType = qname(xbrl, "xbrl:timeSeriesCube")
defaultCubeType = qname(xbrl, "xbrl:defaultCube")
baseCubeTypes = {eventCubeType, positionCubeType, referenceCubeType, reportCubeType, journalCubeType,
                 eventDetailsCubeType, timeSeriesCubeType, defaultCubeType}
timeSeriesPropType = qname(xbrl, "xbrl:timeSeriesType")
intervalOfMeasurementPropType = qname(xbrl, "xbrl:intervalOfMeasurement")
intervalConventionPropType = qname(xbrl, "xbrl:intervalConvention")
excludedIntervalsPropType = qname(xbrl, "xbrl:excludedIntervals")

periodCoreDim = qname(xbrl, "xbrl:period")
conceptCoreDim = qname(xbrl, "xbrl:concept")
entityCoreDim = qname(xbrl, "xbrl:entity")
unitCoreDim = qname(xbrl, "xbrl:unit")
languageCoreDim = qname(xbrl, "xbrl:language")

coreDimensions = {periodCoreDim, conceptCoreDim, entityCoreDim, unitCoreDim, languageCoreDim}
coreDimensionsByLocalname = dict((d.localName, d) for d in coreDimensions)

conceptDomainClass = qname(xbrl, "xbrl:conceptDomain")
entityDomainClass = qname(xbrl, "xbrl:entityDomain")
unitDomainClass = qname(xbrl, "xbrl:unitDomain")
languageDomainClass = qname(xbrl, "xbrl:languageDomain")

