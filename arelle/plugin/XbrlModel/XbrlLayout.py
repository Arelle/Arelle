"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, List, Any

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlLayoutType, XbrlDataTableType, XbrlModuleType, QNameKeyType, DefaultFalse, OptionalList
from .XbrlObject import XbrlModelObject, XbrlReferencableModelObject

class XbrlAxisLabelGroupRange(XbrlModelObject):
    dataType: QName # (required) The data type of the range values
    interval: str # (required) The interval between range values
    startValue: str # (required) The starting value of the range
    stopValue: Optional[str] # (optional) The ending value of the range
    order: str # (required) The order of the range values ("ascending" or "descending")

class XbrlAxisTypedLabel(XbrlModelObject):
    use: Optional[str] # (optional) Indicates the method for generating typed labels.
    transform: Optional[QName] # (optional) The transform to apply to typed values if the value of the use property is "formattedValue".
    range: Optional[XbrlAxisLabelGroupRange] # Range specification for typed label values with the same structure as axisLabelsGroup range

class XbrlAxisHeader(XbrlModelObject):
    dimensionName: QName # (required) The name of the dimension for this axis header.
    labelType: Optional[QName] # (optional) The label type to use for displaying axis members.
    language: Optional[str] # (optional) Defines the language of the labels using a valid BCP 47 [BCP47] language code.
    axisMembers: OptionalList[QName] # (optional) Array of member QNames to display on this axis.
    axisNetwork: Optional[QName] # (optional) The network QName that defines the hierarchy of axis members.
    dimensionOptional: Union[bool, DefaultFalse] # (optional) Indicates whether the dimension is optional.
    totalLocation: Optional[str] # (optional) Specifies where totals should be displayed relative to the dimension members. Valid values are "start", "end", or "none".
    groupDuplicateLabels: Union[bool, DefaultFalse] # (optional) Indicates whether duplicate labels should be grouped together.
    labelTransform: Optional[QName]
    typedLabel: Optional[XbrlAxisTypedLabel] # (optional) Configuration for typed dimension labels

class XbrlAxisLabelGroup(XbrlModelObject):
    valueArray: OptionalList[str] # (optional) Array of string values to use as axis labels.
    range: Optional[XbrlAxisLabelGroupRange] # (optional) Range specification for generating axis labels .

class XbrlAxis(XbrlModelObject):
    dataTable: XbrlDataTableType
    axisHeaders: OrderedSet[XbrlAxisHeader] # (optional) Defines a set of strings that are used as the axis labels. Cannot be used with the presentationNetwork property.
    axisLabelsGroup: Optional[XbrlAxisLabelGroup] # (optional) An optional grouping of axis labels with valueArray and/or range specifications.

class XbrlDataTable(XbrlReferencableModelObject):
    layout: XbrlLayoutType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the data table object.
    cubeName: Optional[QName] # (optional) The name is a QName that identifies the cube associated with the data table.
    xAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the X axis of the table.
    yAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Y axis of the table.
    zAxis: Optional[XbrlAxis] # (optional) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Z axis of the table.

class XbrlLayout(XbrlModelObject):
    txmyMdl: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the layout object.
    xbrlModelName: XbrlModuleType # (required) The name is a QName that identifies the taxonomy associated with the layout objects.
    dataTables: OrderedSet[XbrlDataTable] # (optional) ordered set of dataTable objects.
