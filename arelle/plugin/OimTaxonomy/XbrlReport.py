"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Any, Union
from collections import OrderedDict
from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlTaxonomyModelType, XbrlReportType, QNameKeyType
from .XbrlObject import XbrlObject, XbrlReportObject


class XbrlFact(XbrlReportObject):
    report: XbrlReportType
    id: str # synthesized id (from fact key in JSON), marked Optional because it's a key, not value, in json source.
    value: Optional[str] # (required) The value of the {value} property of the fact. The value MUST be represented as (xbrlje:invalidFactValue):
    decimals: Optional[int] # An integer providing the value of the {decimals} property, or absent if the value is infinitely precise or not applicable (for nil or non-numeric facts).
    dimensions: dict[Union[QName, str], Any] # (required) A dimensions object with properties corresponding to the members of the {dimensions} property.
    links: dict[str, dict[str, list[str]]] # A links object, cormesponding to the link groups associated with the fact. This member MAY be absent if there are no link groups associated with the fact.

class XbrlReport(XbrlReportObject):
    txmyMdl: XbrlTaxonomyModelType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    linkTypes: OrderedDict[str, AnyURI] = OrderedDict()
    linkGroups: OrderedDict[str, AnyURI] = OrderedDict()
    facts: OrderedDict[str, XbrlFact] = OrderedDict()
