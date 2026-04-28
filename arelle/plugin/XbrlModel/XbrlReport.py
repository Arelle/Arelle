"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional, Any, Union, ClassVar, Dict
from collections import defaultdict, OrderedDict
from decimal import Decimal
from arelle.ModelValue import QName, AnyURI
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlTaxonomyModelType,XbrlModuleType, XbrlReportType, QNameKeyType, DefaultFalse, OptionalList
from .XbrlObject import XbrlObject, XbrlReportObject
from .XbrlProperty import XbrlProperty
from .XbrlUnit import  parseUnitString

class XbrlFactValueSource(XbrlObject):
    """ Fact Value Source Object
        Reference: oim-taxonomy#factvaluesource-object"""
    source: Optional[QName] # (optional) entifies the source of the document file using a QName that represents a file such as a pdf file or html file. If no source is provided the document file encapsulating the taxonomy (report) object is implied. If the model is external to the source file then the sourceMapping property of the documentInfo object is used to associate the model with a document file. A value only needs to be provided if there is more than one source file used to represent fact values.
    medium: Optional[str] # (optional) The document medium, which may be implied when the taxonomy (report) object is encapsulated in a document file: html, pdf, tabular.
    id: Optional[str] # (optional for HTML only) The HTML element containing mapped (inner) text content. May be an id such as #elt1, to identify inner text of that element, if present (else ineffective and contributes nothing to the value).
    formField: Optional[str] # (optional for PDF only) The field name of a PDF form field. Identifies that field contents (if any) or default (if any) contribute to the value.
    page: Optional[int] # (required for PDF non-form text only) The page number.
    mcid: Optional[str] # (optional for PDF non-form structure text identified by mcid)
    elementId: Optional[str] # (optional for PDF non-form text identified by structure element Id)
    tabularPath: Optional[str] # (optional for tabular sources to identify a tabular path (e.g. RevenueByRegion!row[@Year=2024 and @Region='NA']/Revenue). See Appendix I for the tabularPath grammar.
    transformation: Optional[QName] # (optional for html/pdf) identifes a transformation for the document file text, such as conversion from dates in some locale format. Not relevant for workbook cells with number or date formats specified.
    scale: Optional[int] # (optional) identifies a power of 10 to multiply source text number (such as when in billions in the source document_
    sign: Optional[str] # (optional) identifies a sign when not part of transformation of value. Not relevant for workbook cells with number or date formats specified.
    escape: Union[bool, DefaultFalse] # (optional) If the escape attribute is true then value is the escaped representation for media with markup, e.g. html or pdf, otherwise the concatenation in document order of all descendant text content. If no value is provided the attribute defaults to false.

class XbrlFactValueAnchor(XbrlObject):
    """ Fact Value Anchor Object
        Reference: oim-taxonomy#factvalueanchor-object
    """
    source: Optional[QName] # (optional) entifies the source of the document file using a QName that represents a file such as a pdf file or html file. If no source is provided the document file encapsulating the taxonomy (report) object is implied. If the model is external to the source file then the sourceMapping property of the documentInfo object is used to associate the model with a document file. A value only needs to be provided if there is more than one source file used to represent fact values.
    medium: Optional[str] # (optional) The document medium, which may be implied when the taxonomy (report) object is encapsulated in a document file: html, pdf, tabular.
    id: Optional[str] # (optional for HTML only) The HTML element containing mapped (inner) text content. May be an id such as #elt1, to identify inner text of that element, if present (else ineffective and contributes nothing to the value).
    formField: Optional[str] # (optional for PDF only) The field name of a PDF form field. Identifies that field contents (if any) or default (if any) contribute to the value.
    page: Optional[int] # (required for PDF non-form text only) The page number.
    mcid: Optional[str] # (optional for PDF non-form structure text identified by mcid)
    elementId: Optional[str] # (optional for PDF non-form text identified by structure element Id)
    tabularPath: Optional[str] # (optional for tabular sources to identify a tabular path (e.g. RevenueByRegion!row[@Year=2024 and @Region='NA']/Revenue). See Appendix I for the tabularPath grammar.

class XbrlFactValue(XbrlObject):
    """ Fact Value Object
        Reference: oim-taxonomy#factvalue-object
    """
    name: QNameKeyType
    value: Optional[Any] # (required if valueSources not provided) The value of the fact. This can be a numeric value, a string, or any other type of value that is valid for the fact.
    decimals: Optional[int] # An integer providing the value of the {decimals} property, or absent if the value is infinitely precise or not applicable (for nil or non-numeric facts).
    language: Optional[str] # (optional) The language of the fact value, specified using the BCP 47 standard language code (e.g., "en" for English, "fr" for French).
    valueSources: OrderedSet[XbrlFactValueSource] # (required if value not provided) An ordered set of factValueSource objects that identify where the values are obtained from content of an embedding or accompanying document file (html, pdf or tabular).
    valueAnchors: OrderedSet[XbrlFactValueAnchor] # (optional if valueSources not provided) An ordered set of factAnchor objects that identify corresponding content of an embedding document file (html, pdf or tabular) for cases where the value is provided in the value property instead of obtained from the content of document file. For example, non-transformable values, such as a QName value, may correspond to prose text in the document file. Used by tools to highlight and detect mouse-over correspondence between fact values and document text.

class XbrlFact(XbrlReportObject):
    """ Fact Object
        Reference: oim-taxonomy#fact-object
    """
    parent: Union[XbrlReportType,XbrlModuleType]  # facts in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (equired if no extendTargetName) The name is a QName that uniquely identifies the factspace object.
    factValues: OrderedSet[XbrlFactValue]
    factDimensions: Dict[QName, Any] # (required) A dimensions object with properties corresponding to the members of the {dimensions} property.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to specify additional properties associated with the fact using the property object.
    extendTargetName: Optional[QName] # (required if no name property) Names the fact object that is appended to. The fact values and dimensions of the fact with this property are appended to the end of the fact object with the name property. This property cannot be used in conjunction with the name property.
    _propertyMap: ClassVar[dict[type,dict[str, str]]] = {}

class XbrlFootnote(XbrlReportObject):
    """ Footnote Object
        Reference: oim-taxonomy#footnote-object
    """
    parent: Union[XbrlReportType,XbrlModuleType]  # facts in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    relatedNames: OrderedSet[QName] # (required) QNames of the fact objects associated with this footnote.
    content: Optional[str] # (required) The content of the footnote.
    language: Optional[str] # ((optional) The language of the footnote text, specified using the BCP 47 standard language code (e.g., "en" for English, "fr" for French).

class XbrlNamespaceMap(XbrlObject):
    """ Namespace Map Object
        Reference: oim-taxonomy#namespacemap-object
    """
    fromNamespace: AnyURI # (required) The fromNamespace property is the original namespace that is being redirected.
    toNamespace: AnyURI # (required) The toNamespace property is the new namespace that the fromNamespace is being redirected to.

class XbrlFactSourceDimensionSummaryRange(XbrlObject):
    """ Fact Source Dimension Summary Range Object
        Reference: oim-taxonomy#factsourcedimensionsummaryrange-object
    """
    min: Any # (required) The minimum value for the dimension in the data source identified by the factSource object. For explicit dimensions, the minimum value is a QName that references a dimension member object defined in the taxonomy model. For typed dimensions, the minimum value is a typed value that is valid for the dimension.
    max: Any # (required) The maximum value for the dimension in the data source identified by the factSource object. For explicit dimensions, the maximum value is a QName that references a dimension member object defined in the taxonomy model. For typed dimensions, the maximum value is a typed value that is valid for the dimension.

class XbrlFactSourceDimensionSummary(XbrlObject):
    """ Fact Source Dimension Summary Object
        Reference: oim-taxonomy#factsourcedimensionsummary-object
    """
    dimensionName: QName # (required) A QName that identifies the dimension.
    memberCount: int # (required) The number of unique members for the dimension in the data source identified by the factSource object. This can be used to determine the size of the data source and to optimize processing of the data source.
    isTyped: bool # (required) A boolean value that indicates whether the dimension is a typed dimension. This can be used to determine how to process the dimension values in the data source identified by the factSource object.
    sampleMembers: Optional[OrderedSet[Any]] # (optional) An ordered set of sample members for the dimension in the data source identified by the factSource object. This can be used to provide examples of the dimension values in the data source and to optimize processing of the data source. For explicit dimensions, the sample members are QNames that reference dimension member objects defined in the taxonomy model. For typed dimensions, the sample members are typed values that are valid for the dimension.
    memberRange: Optional[XbrlFactSourceDimensionSummaryRange] # (optional) A tuple that provides the range of members for the dimension in the data source identified by the factSource object. This can be used to provide information about the distribution of dimension values in the data source and to optimize processing of the data source. For explicit dimensions, the member range is a tuple of QNames that reference dimension member objects defined in the taxonomy model. For typed dimensions, the member range is a tuple of typed values that are valid for the dimension.

class XbrlFactSourceMetadata(XbrlObject):
    """ Fact Source Metadata Object
        Reference: oim-taxonomy#factsourcemetadata-object
    """
    factCount: int # (required) The factCount property is the number of facts that are obtained from the data source identified by the factSource object. This can be used to determine the size of the data source and to optimize processing of the data source.
    validationTimestamp: str # (required) The validationTimestamp property is the date and time when the data source identified by the factSource object was last validated. This can be used to determine the freshness of the data source and to optimize processing of the data source.
    concepts: OrderedSet[QName] # (required) An ordered set of QNames that reference concept objects defined in the taxonomy model. If provided, the factSource object only applies to the facts with these concepts. If not provided, the factSource object applies to all facts in the report.
    dimensions: OrderedSet[XbrlFactSourceDimensionSummary] # (required) An ordered set of QNames that reference dimension objects defined in the taxonomy model. If provided, the factSource object only applies to the facts with these dimensions. If not provided, the factSource object applies to all facts inAn ordered set of factSourceDimensionSummary objects that describe the dimensions used in the fact collection, including the xbrl:concept dimension.
    threshold: Optional[int] # (optional) The threshold property is a numeric value that can be used to determine when to apply certain processing rules or optimizations to the data source identified by the factSource object. For example, if the factCount property exceeds the threshold value, certain processing rules or optimizations may be applied to improve performance.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to specify additional properties associated with the factSource using the property object.

class XbrlFactSource(XbrlReportObject):
    """ Fact Source Object
        Reference: oim-taxonomy#factsource-object
    """
    parent: Union[XbrlReportType,XbrlModuleType]  # table templates in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the factSource object.
    factMapName: QName # (required) The fact map name is a QName that references a factMap object defined in the taxonomy model.
    cubeName: Optional[QName] # (optional) A QName that references a cube object defined in the taxonomy model. If provided, the fact source object only applies to the facts with this cube. If not provided, the fact source object applies to all facts in the report.
    namespaceMaps: OptionalList[XbrlNamespaceMap] # (optional) An array of namespaceMap objects that maps the namespace of the model defined in a datasource to the namespace of an updated model. This MUST only used with an XBRL data source.
    factNames: Optional[OrderedSet[QName]] # (optional) An ordered set of QNames that reference fact objects defined in the taxonomy model. If provided, the factSource object only applies to the facts with these names. If not provided, the factSource object applies to all facts in the report.
    hash: Optional[str] # (optional) A hash value that can be used to verify the integrity of the data source. The specific hashing algorithm used is not defined in the specification and may be determined by the implementation.
    metadata: Optional[XbrlFactSourceMetadata] # (optional) A metadata object that can contain any additional information about the fact source. The structure and content of the metadata object is not defined in the specification and may be determined by the implementation.
    properties: OrderedSet[XbrlProperty] # (optional) an ordered set of property objects used to specify additional properties associated with the factSource using the property object.

class XbrlTableTemplate(XbrlReportObject):
    """ Table Template Object
        Reference: oim-taxonomy#tabletemplate-object
    """
    parent: Union[XbrlReportType,XbrlModuleType]  # table templates in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the tableTemplate object.
    rowIdColumn: Optional[str] # (optional) An identifier specifying the name of the row ID column.
    columns: dict # (required) A columns object. (See xbrl-csv specification)
    factDimensions: dict[QName, Any] # (required) A dimensions object that defines table dimensions. (See xbrl-csv specification)
    decimals: Optional[Decimal] # (optional) A decimals val
    extendTargetName: Optional[QName] # (required if no name property) Names the tableTemplate object that is appended to. The items in the table template with this property are appended to the end of the columns target table template object. This property cannot be used in conjunction with the name and rowIdColumn property.

class XbrlJSONTemplateMap(XbrlReportObject):
    """ JSON Template Map Object
        Reference: oim-taxonomy#jsontemplatemap-object
    """
    parent: Union[XbrlReportType,XbrlModuleType]  # table templates in taxonomy module are owned by the txmyMdl
    name: Optional[QNameKeyType] # (optional) The QName that identifies the JSON template map object.
    factDimensions: dict[QName, Any] # (required) A factDimensions object that defines map dimensions.
    valuePath: str # (required) A JSONPath expression that identifies the location of the fact values in the JSON data.
    decimals: Optional[int] # (optional) A decimals value.

class XbrlXMLTemplateMap(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlModuleType]  # table templates in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The QName that identifies the XML template map object.
    factDimensions: dict[QName, Any] # (required) A factDimensions object that defines map dimensions.
    valuePath: str # (required) A JSONPath expression that identifies the location of the fact values in the JSON data.
    decimals: Optional[int] # (optional) A decimals value.
    namespaceMap: Optional[XbrlNamespaceMap] # (optional) A namespace mapping object that defines the namespace prefixes used in the XPath expression.

class XbrlFactMap(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlModuleType]  # table templates in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the fact map object.
    templateName: Optional[QName] # (optional) A QName that references a tableTemplate, jsonTemplateMap or xmlTemplateMap object defined in the taxonomy model. If provided, the fact map object only applies to the facts with this template. If not provided, the fact map object applies to all facts in the report.

class XbrlFactLocatorType(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlModuleType]  # fact locator types in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies this locator type.
    sourceMediaType: str # (optional) Advisory MIME type or media format hint (e.g. text/html, application/pdf, text/csv). Informational only; does not restrict which source documents a locator of this type may reference.
    requiredProperties: OrderedSet[QName] # (optional) A set of property QNames that MUST be present on any factValueSource object using this type.
    allowedProperties: OrderedSet[QName] # (optional) A set of property QNames that MAY be present on any factValueSource object using this type. If not provided, there are no restrictions on the properties that may be used with this locator type.

class XbrlReport(XbrlReportObject):
    txmyMdl: XbrlTaxonomyModelType
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    factPositions: OrderedDict[QNameKeyType, XbrlFact]
    footnotes: OrderedDict[QNameKeyType, XbrlFootnote]
    factSources: OrderedSet[XbrlFactSource] # (optional) ordered set of tableTemplate objects.

    @property
    def factsByName(self):
        try:
            return self._factPositionsByName
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