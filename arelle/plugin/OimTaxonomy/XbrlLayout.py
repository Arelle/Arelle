"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Union
from decimal import Decimal

from arelle.ModelValue import QName
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlLayoutType, XbrlTaxonomyModuleType, QNameKeyType, DefaultFalse
from .XbrlObject import XbrlTaxonomyObject, XbrlReferencableTaxonomyObject

class XbrlTableTemplate(XbrlReferencableTaxonomyObject):
    layout: XbrlLayoutType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the transform object.
    rowIdColumn: Optional[str] # (optional) An identifier specifying the name of the row ID column.
    columns: dict # (required) A columns object. (See xbrl-csv specification)
    dimensions: dict # (required) A dimensions object that defines table dimensions. (See xbrl-csv specification)
    decimals: Optional[Decimal] # (optional) A decimals value

class XbrlAxisDimension(XbrlTaxonomyObject):
    dimensionName: QName # (required) The QName of a dimension defined by the cubeName property.
    showTotal: Union[bool, DefaultFalse] # (optional) Indicates if the total of the dimension is shown in the axis. This is the value associated with the dimension absent. If no value is provided the default is false. The concept dimension defaults to false and cannot be set to true.
    showAncestorColumns: Union[bool, DefaultFalse] # (optional) Define members on an explicit dimension that are not leaf values that are included on the axis. If not provided only leaf members on the axis will show.
    totalLocation: Optional[str] # (optional) Indicates if the total is at the start or at the end when shown on the axis. The default value is end. The totalLocation attribute can only have a value of start or end.
    periodAlign: OrderedSet[str] # (optional) the period align attribute can only be used with the period dimension. This attribute is used to align time values of facts in a dimension rather than being created as seperate columns or rows. The values @start and @end are used to indicate if instant values are aligned with duration values. These values are used to support roll-forwards in a datatgrid and will align duration values and instant values with the same start and end dates.

class XbrlAxis(XbrlTaxonomyObject):
    layout: XbrlLayoutType
    dimensionNames: OrderedSet[XbrlAxisDimension] # (required) The axis dimension objects that define the dimensions associated with the axis.
    axisLabels: OrderedSet[str] # (optional) Defines a set of strings that are used as the axis labels. Cannot be used with the presentationNetwork property.
    language: Optional[str] # (optional) Defines the language of the axisLabels using a valid BCP 47 [BCP47] language code.
    presentationNetwork: Optional[QName] # (optional) Defines a QName of a network with a relationshipType of xbrl:parent-child that is used to control the order of items on the axis and the labels that are used

class XbrlDataTable(XbrlReferencableTaxonomyObject):
    layout: XbrlLayoutType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the data table object.
    cubeName: QName # (required) The name is a QName that identifies the cube associated with the data table.
    xAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the X axis of the table.
    yAxis: XbrlAxis # (required) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Y axis of the table.
    zAxis: XbrlAxis # (optional) An axis object that identifies an ordered set of axis and the behaviour of the dimension when mapped to the Z axis of the table.

class XbrlLayout(XbrlTaxonomyObject):
    txmyMdl: XbrlTaxonomyModuleType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the layout object.
    taxonomyName: XbrlTaxonomyModuleType # (required) The name is a QName that identifies the taxonomy associated with the layout objects.
    tableTemplates: OrderedSet[XbrlTableTemplate] # (optional) ordered set of tableTemplate objects.
    dataTables: OrderedSet[XbrlDataTable] # (optional) ordered set of dataTable objects.
    