"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Any, Union, ClassVar
from collections import defaultdict, OrderedDict
from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlTaxonomyModelType,XbrlTaxonomyModuleType, XbrlReportType, QNameKeyType, DefaultFalse
from .XbrlObject import XbrlObject, XbrlReportObject
from .XbrlProperty import XbrlProperty
from .XbrlUnit import  parseUnitString


class XbrlFact(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlTaxonomyModuleType]  # facts in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    value: Optional[str] # (required) The value of the {value} property of the fact. The value MUST be represented as (xbrlje:invalidFactValue):
    decimals: Optional[int] # An integer providing the value of the {decimals} property, or absent if the value is infinitely precise or not applicable (for nil or non-numeric facts).
    factDimensions: dict[QName, Any] # (required) A dimensions object with properties corresponding to the members of the {dimensions} property.
    links: dict[str, dict[str, list[str]]] # A links object, corresponding to the link groups associated with the fact. This member MAY be absent if there are no link groups associated with the fact.
    _propertyMap: ClassVar[dict[type,dict[str, str]]] = {}

class XbrlTable(XbrlReportObject):
    report: XbrlReportType # tables in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (optional) A table template identifier. If this property is omitted, then it defaults to the table identifier. The value MUST be the identifier of a table template present in the effective metadata of the file in which the table object appears (xbrlce:unknownTableTemplate).
    url: AnyURI # (required) A URL (xs:anyURI) to the CSV file for this table. Relative URLs are resolved relative to the primary metadata file
    template: QName # (optional) A table template identifier. If this property is omitted, then it defaults to the table identifier. The value MUST be the identifier of a table template present in the effective metadata of the file in which the table object appears (xbrlce:unknownTableTemplate).
    optional: Union[bool, DefaultFalse] # optional) A boolean value indicating that the CSV file specified by the url property is not required to exist. Defaults to false. If false, the file specified MUST exist (xbrlce:missingRequiredCSVFile).
    parameters: dict[str, str] # (optional) ordered set of property objects used to specify additional properties associated with the concept using the property object. Only immutable properties as defined in the propertyType object can be added to a concept.


class XbrlReport(XbrlReportObject):
    txmyMdl: XbrlTaxonomyModelType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    linkTypes: OrderedDict[str, AnyURI]
    linkGroups: OrderedDict[str, AnyURI]
    facts: OrderedDict[QNameKeyType, XbrlFact]
    tables: OrderedDict[QNameKeyType, XbrlTable] # CSV tables in the report

    @property
    def factsByName(self):
        try:
            return self._factsByName
        except AttributeError:
            self._factsByName = fbn = defaultdict(OrderedSet)
            for fact in self.facts:
                fbn[fact.name].add(fact)
            return self._factsByName

XbrlFact._propertyMap[XbrlReport] = {
    # mapping for OIM report facts parented by XbrlReport object
    "name": "id", # name may be id in source input
    "factDimensions": "dimensions" # factDimensions may be dimensions in source input
}