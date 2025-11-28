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

class XbrlFactValueSource(XbrlObject):
    medium: Optional[str] # (optional) The document medium, which may be implied when the taxonomy (report) object is encapsulated in a document file: html, pdf, tabular.
    href: Optional[str] # (required for HTML only) The HTML element containing mapped (inner) text content. May be an id such as #elt1, to identify inner text of that element, if present (else ineffective and contributes nothing to the value).
    formField: Optional[str] # (optional for PDF only) The field name of a PDF form field. Identifies that field contents (if any) or default (if any) contribute to the value.
    page: Optional[int] # (required for PDF non-form text only) The page number.
    mcid: Optional[str] # (optional for PDF non-form structure text identified by mcid)
    elementId: Optional[str] # (optional for PDF non-form text identified by structure element Id)
    tabularPath: Optional[str] # (optional for tabular sources to identify a tabular path (e.g. RevenueByRegion!row[@Year=2024 and @Region='NA']/Revenue). See Appendix I for the tabularPath grammar.
    transformation: Optional[QName] # (optional for html/pdf) identifes a transformation for the document file text, such as conversion from dates in some locale format. Not relevant for workbook cells with number or date formats specified.
    scale: Optional[int] # (optional) identifies a power of 10 to multiply source text number (such as when in billions in the source document_
    sign: Optional[str] # (optional) identifies a sign when not part of transformation of value. Not relevant for workbook cells with number or date formats specified.

class XbrlFactValueAnchor(XbrlObject):
    medium: Optional[str] # (optional) The document medium, which may be implied when the taxonomy (report) object is encapsulated in a document file: html, pdf, tabular.
    href: Optional[str] # (required for HTML only) The HTML element containing mapped (inner) text content. May be an id such as #elt1, to identify inner text of that element, if present (else ineffective and contributes nothing to the value).
    formField: Optional[str] # (optional for PDF only) The field name of a PDF form field. Identifies that field contents (if any) or default (if any) contribute to the value.
    page: Optional[int] # (required for PDF non-form text only) The page number.
    mcid: Optional[str] # (optional for PDF non-form structure text identified by mcid)
    elementId: Optional[str] # (optional for PDF non-form text identified by structure element Id)
    tabularPath: Optional[str] # (optional for tabular sources to identify a tabular path (e.g. RevenueByRegion!row[@Year=2024 and @Region='NA']/Revenue). See Appendix I for the tabularPath grammar.

class XbrlFactValue(XbrlObject):
    name: QNameKeyType
    value: Optional[Any] # (required if valueSources not provided) The value of the fact. This can be a numeric value, a string, or any other type of value that is valid for the fact.
    decimals: Optional[int] # An integer providing the value of the {decimals} property, or absent if the value is infinitely precise or not applicable (for nil or non-numeric facts).
    language: Optional[str] # (optional) The language of the fact value, specified using the BCP 47 standard language code (e.g., "en" for English, "fr" for French).
    valueSources: OrderedSet[XbrlFactValueSource] # (required if value not provided) An ordered set of factValueSource objects that identify where the values are obtained from content of an embedding or accompanying document file (html, pdf or tabular).
    valueAnchors: OrderedSet[XbrlFactValueAnchor] # (optional if valueSources not provided) An ordered set of factAnchor objects that identify corresponding content of an embedding document file (html, pdf or tabular) for cases where the value is provided in the value property instead of obtained from the content of document file. For example, non-transformable values, such as a QName value, may correspond to prose text in the document file. Used by tools to highlight and detect mouse-over correspondence between fact values and document text.
    # language?

class XbrlFact(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlTaxonomyModuleType]  # facts in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    factValues: OrderedSet[XbrlFactValue]
    factDimensions: dict[QName, Any] # (required) A dimensions object with properties corresponding to the members of the {dimensions} property.
    _propertyMap: ClassVar[dict[type,dict[str, str]]] = {}

class XbrlFootnote(XbrlReportObject):
    parent: Union[XbrlReportType,XbrlTaxonomyModuleType]  # facts in taxonomy module are owned by the txmyMdl
    name: QNameKeyType # (required) The name is a QName that uniquely identifies the abstract object.
    content: Optional[str] # (required) The content of the footnote.
    language: Optional[str] # ((optional) The language of the footnote text, specified using the BCP 47 standard language code (e.g., "en" for English, "fr" for French).

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
    footnotes: OrderedDict[QNameKeyType, XbrlFootnote]
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