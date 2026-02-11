"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union, List, Any

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlLayoutType, XbrlDataTableType, XbrlModuleType, QNameKeyType, DefaultFalse, DefaultOne, OptionalList
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
    typedLabel: Optional[XbrlAxisTypedLabel] # (optional) Configuration for typed dimension labels
    
class XbrlGridHeader(XbrlModelObject):
    label: str # (required) The label to display for this grid row or column. This can be a static string or can reference a label defined in the taxonomy.
    span: Union[int, DefaultOne] # (optional) The number of columns (for x-axis) or rows (for y-axis) that this header should span. Defaults to 1 if not specified.
    rollUpLocation: Optional[str] # (optional) Specifies where the header label should be placed when spanning multiple columns or rows. Valid values are "start", "end" or "none". The default is "start". If a value of none is defined the header label does not have a represented value on the grid.
    labelLevel: Optional[int] # (optional) The position of this header in the grid. This is used to determine the order of headers when multiple headers are defined. If not specified, the order is determined by the order of the gridHeader objects in the array. Starts at 1 next to the grid coordinate cells if any.
    axisNumber: Optional[str] # (optional) Identifier for the axis position in the grid (e.g., 1 ,2 ,3). This is used to associate the header with a specific axis position when multiple headers are defined. The value of axisNumber should correspond to the axis positions defined in the gridAxis object.

class XbrlAxisLabelGroup(XbrlModelObject):
    valueArray: OptionalList[str] # (optional) Array of string values to use as axis labels.
    range: Optional[XbrlAxisLabelGroupRange] # (optional) Range specification for generating axis labels .

class XbrlAxisItem(XbrlModelObject):
    axisId: str # (required) Identifier for this axis item (e.g., "C0030", "R0100"). This identifier is used to reference the axis position in the grid.
    itemLabel: Optional[str] # (optional) Optional label for the axis item. If not provided, the label is derived from the member's label in the taxonomy.
    dimensions: dict[QName, QName] # (optional) Map of dimension names to member names for this grid cell.

class XbrlAxisGroup(XbrlModelObject):
    dimensionName: QName # (required) The dimension name for this axis dimension.
    axisNetwork: Optional[QName] # (required) The network or domain QName that defines the structure of axis members in this group. This can reference either a network object or a domain object that organizes the dimension members.
    axisIds: OrderedSet[str] # (required) Array of axis identifiers (e.g., "R0100", "R0110") that belong to this group. These identifiers correspond to specific positions or items on the axis.
    axisStart: Optional[int] # (optional) Integer that indicates the start location of the group on the axis. This is used for positioning the group on the axis. If not provided the group starts at the first position on the grid or a default value of 1.

class XbrlGridAxis(XbrlModelObject):
    axisItems: OrderedSet[XbrlAxisItem] # (optional) Array of axisItem objects that define individual dimension member pairs for grid positioning.
    axisGroups: OrderedSet[XbrlAxisGroup] # (optional) Array of axisGroup objects that organize dimension member pairs into logical groupings.

class XbrlAxis(XbrlModelObject):
    dataTable: XbrlDataTableType
    axisHeaders: OrderedSet[XbrlAxisHeader] # (optional) Defines a set of strings that are used as the axis labels. Cannot be used with the presentationNetwork property.
    gridHeaders: OrderedSet[XbrlGridHeader] # (optional) An array of gridHeader objects that defines the label for each column or row on a grid.
    axisLabelsGroup: Optional[XbrlAxisLabelGroup] # (optional) An optional grouping of axis labels with valueArray and/or range specifications.
    gridAxis: Optional[XbrlGridAxis] # (optional) Grid axis configuration for aligning dimension pairs with rows and columns in grid layouts. 

class XbrlGridCoordinate(XbrlModelObject):
    xAxis: str # (required) The x-axis (column) coordinate in the grid.
    yAxis: str # (required) The y-axis (row) coordinate in the grid.
    zAxis: Optional[str] # (optional) The z-axis coordinate in the grid.

class XbrlTablePoint(XbrlModelObject):
    dataTable: XbrlDataTableType
    gridCoordinates: XbrlGridCoordinate # (required) Grid coordinates identifying the cell location in the table.
    dimensions: dict[QName, QName] # (required) Map of dimension names to member names for this grid cell.

class XbrlDataTable(XbrlReferencableModelObject):
    layout: XbrlLayoutType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the data table object.
    tableType: str # (required) Specifies the layout type for the table. Valid values are "gridLayout" (uses explicit grid positioning with tablePoints) or "cubeLayout" (uses traditional cube-based rendering with axes). This property determines how the table structure is interpreted and rendered.
    cubeName: Optional[QName] # (optional) The name is a QName that identifies the cube associated with the data table.
    xAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the X axis of the table.
    yAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Y axis of the table.
    zAxis: Optional[XbrlAxis] # (optional) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Z axis of the table.
    tablePoints: Optional[XbrlTablePoint] # (optional) Array of tablePoint objects that map dimension member pairs to specific grid cells. 

class XbrlLayout(XbrlModelObject):
    txmyMdl: XbrlModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the layout object.
    tableConstruction: Optional[str] # (optional) Specifies how multiple tables in the dataTables array should be joined together. 
    dataTables: OrderedSet[XbrlDataTable] # (optional) ordered set of dataTable objects.
