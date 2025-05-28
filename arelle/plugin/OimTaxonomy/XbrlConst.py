"""
See COPYRIGHT.md for copyright information.
"""
import regex as re
from arelle.ModelValue import qname
from arelle.XbrlConst import xsd

# MERGE TO arelle.XbrlConst when promoting plugin to infrastructure

oimTaxonomyDocTypePattern = re.compile(r"\s*\{.*\"documentType\"\s*:\s*\"https://xbrl.org/[0-9]{4}/taxonomy\"", flags=re.DOTALL)
oimTaxonomyDocTypes = (
        "https://xbrl.org/2025/taxonomy",
    )

xbrl = "https://xbrl.org/2025"

qnStdLabel = qname(xbrl, "xbrli:label")
qnXsDate = qname(xsd, "xs:date")
qnXsDateTime = qname(xsd, "xs:dateTime")
qnXsDuration = qname(xsd, "xs:duration")
qnXsQName = qname(xsd, "xs:QName")

qnXbrlLabelObj = qname(xbrl, "xbrl:labelObject")

objectsWithProperties = {
    qname(xbrl, "xbrl:taxonomyObject"),
    qname(xbrl, "xbrl:conceptObject"),
    qname(xbrl, "xbrl:abstractObject"),
    qname(xbrl, "xbrl:cubeObject"),
    qname(xbrl, "xbrl:dimensionObject"),
    qname(xbrl, "xbrl:domainObject"),
    qname(xbrl, "xbrl:entityObject"),
    qname(xbrl, "xbrl:groupObject"),
    qname(xbrl, "xbrl:networkObject"),
    qnXbrlLabelObj,
    qname(xbrl, "xbrl:memberObject"),
    qname(xbrl, "xbrl:referenceObject"),
    qname(xbrl, "xbrl:relationshipObject"),
    }

xbrlTaxonomyObjects = {
    "documentInfo": {
        "documentType": oimTaxonomyDocTypes[0],
        "namespaces": {
            "xbrl": xbrl,
            "xbrli": "https://xbrl.org/2025/instance",
            "xs": xsd
        }
    },
    "taxonomy": {
        "name": "xbrl:BuiltInCoreObjectsTaxonomy",
        "frameworkName": "types",
        "version": "2025",
        "resolved": False,
        "dataTypes": [
            {
                "name": "xs:string",
                "baseType": "xs:string"
            },
            {
                "name": "xs:boolean",
                "baseType": "xs:boolean"
            },
            {
                "name": "xs:decimal",
                "baseType": "xs:decimal"
            },
            {
                "name": "xs:float",
                "baseType": "xs:float"
            },
            {
                "name": "xs:double",
                "baseType": "xs:double"
            },
            {
                "name": "xs:duration",
                "baseType": "xs:duration"
            },
            {
                "name": "xs:dateTime",
                "baseType": "xs:dateTime"
            },
            {
                "name": "xs:time",
                "baseType": "xs:time"
            },
            {
                "name": "xs:date",
                "baseType": "xs:date"
            },
            {
                "name": "xs:gYearMonth",
                "baseType": "xs:gYearMonth"
            },
            {
                "name": "xs:gYear",
                "baseType": "xs:gYear"
            },
            {
                "name": "xs:gMonthDay",
                "baseType": "xs:gMonthDay"
            },
            {
                "name": "xs:gDay",
                "baseType": "xs:gDay"
            },
            {
                "name": "xs:gMonth",
                "baseType": "xs:gMonth"
            },
            {
                "name": "xs:hexBinary",
                "baseType": "xs:hexBinary"
            },
            {
                "name": "xs:base64Binary",
                "baseType": "xs:base64Binary"
            },
            {
                "name": "xs:anyURI",
                "baseType": "xs:anyURI"
            },
            {
                "name": "xs:QName",
                "baseType": "xs:QName"
            },
            {
                "name": "xs:NOTATION",
                "baseType": "xs:NOTATION"
            },
            {
                "name": "xs:normalizedString",
                "baseType": "xs:string"
            },
            {
                "name": "xs:token",
                "baseType": "xs:normalizedString"
            },
            {
                "name": "xs:language",
                "baseType": "xs:token"
            },
            {
                "name": "xs:NMTOKEN",
                "baseType": "xs:token"
            },
            {
                "name": "xs:NMTOKENS",
                "baseType": "xs:NMTOKEN"
            },
            {
                "name": "xs:Name",
                "baseType": "xs:token"
            },
            {
                "name": "xs:NCName",
                "baseType": "xs:Name"
            },
            {
                "name": "xs:ID",
                "baseType": "xs:NCName"
            },
            {
                "name": "xs:IDREF",
                "baseType": "xs:NCName"
            },
            {
                "name": "xs:IDREFS",
                "baseType": "xs:IDREF"
            },
            {
                "name": "xs:ENTITY",
                "baseType": "xs:IDREF"
            },
            {
                "name": "xs:ENTITIES",
                "baseType": "xs:ENTITY"
            },
            {
                "name": "xs:integer",
                "baseType": "xs:decimal"
            },
            {
                "name": "xs:nonPositiveInteger",
                "baseType": "xs:integer",
                "maxInclusive": 0

            },
            {
                "name": "xs:negativeInteger",
                "baseType": "xs:nonPositiveInteger",
                "maxInclusive": -1
            },
            {
                "name": "xs:long",
                "baseType": "xs:integer"
            },
            {
                "name": "xs:int",
                "baseType": "xs:long",
                "maxInclusive": 2147483647,
                "minInclusive":  -2147483648
            },
            {
                "name": "xs:short",
                "baseType": "xs:int",
                "maxInclusive": 32767,
                "minInclusive":  -32768
            },
            {
                "name": "xs:byte",
                "baseType": "xs:short",
                "maxInclusive": 127,
                "minInclusive":  -128
            },
            {
                "name": "xs:nonNegativeInteger",
                "baseType": "xs:integer",
                "minInclusive":  0
            },
            {
                "name": "xs:unsignedLong",
                "baseType": "xs:nonNegativeInteger",
                "maxInclusive": 18446744073709551615
            },
            {
                "name": "xs:unsignedInt",
                "baseType": "xs:unsignedInt",
                "maxInclusive": 4294967295
            },
            {
                "name": "xs:unsignedShort",
                "baseType": "xs:unsignedInt",
                "maxInclusive": 65535
            },
            {
                "name": "xs:unsignedByte",
                "baseType": "xs:unsignedShort",
                "maxInclusive": 255
            },
            {
                "name": "xs:positiveInteger",
                "baseType": "xs:nonNegativeInteger",
                "minInclusive":  1
            },
            {
                "name": "xs:yearMonthDuration",
                "baseType": "xs:duration"
            },
            {
                "name": "xs:dayTimeDuration",
                "baseType": "xs:duration"
            },
            {
                "name": "xs:dateTimeStamp",
                "baseType": "xs:dateTime"
            }
        ]
    }
}
