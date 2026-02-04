"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, List, Any

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlLayoutType, XbrlModuleType, QNameKeyType, DefaultFalse
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject

class XbrlAxisLabel(XbrlModelObject):
    labelType: Optional[QName] # (required when rollup not specified) A QName representing the label type of the label. This can be a taxonomy defined label type or a standard XBRL label type defined in specification.
    language: Optional[str] # (required when rollup not specified) Defines the language of the label using a valid BCP 47 [BCP47] language code.
    value: Optional[str] # (required when rollup and valueSource are not specified) The text of the label.
    valueSource: Optional[QName] # (required when rollup and value are not specified) Specifies a dimension or domain which provides a network for axis members and the corresponding object label type to use as a label.
    rollup: Union[bool, DefaultFalse] # (optional) When true specifies that the preceding axis labels array value is spanned, or continued, into the corresponding position in this axis labels item (e.g. no separator). Absent if false.
    span: Optional[int] # (optional) The number of items in the axis to be spanned by the label if greater than 1.

class XbrlAxis(XbrlModelObject):
    layout: XbrlLayoutType
    axisLabels: OrderedSet[XbrlAxisLabel] # (optional) Defines a set of strings that are used as the axis labels. Cannot be used with the presentationNetwork property.
    axisDimensions: List[dict[QName, Any]] # (required) An array of factDimension objects, each containing dimensions for a each item in the axis. An item may be a fully specified factDimension object or one containing a member type and network for the case of cube networks or concept networks.

class XbrlDataTable(XbrlReferencableModelObject):
    layout: XbrlLayoutType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the data table object.
    cubeName: QName # (required) The name is a QName that identifies the cube associated with the data table.
    xAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the X axis of the table.
    yAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Y axis of the table.
    zAxis: Optional[XbrlAxis] # (optional) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Z axis of the table.

class XbrlLayout(XbrlModelObject):
    txmyMdl: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the layout object.
    xbrlModelName: XbrlModuleType # (required) The name is a QName that identifies the taxonomy associated with the layout objects.
    dataTables: OrderedSet[XbrlDataTable] # (optional) ordered set of dataTable objects.
