"""
See COPYRIGHT.md for copyright information.
"""
import regex as re
from arelle.ModelValue import qname
from arelle.XbrlConst import xsd

# MERGE TO arelle.XbrlConst when promoting plugin to infrastructure

# Sniffs a candidate OIM taxonomy document. Accepts any status date -- including
# the specification's own template -- so that recognition and acceptance are
# separate decisions: a document with an unknown date is recognised here and then
# reported against the namespace policy, rather than as an unknown document type.
oimTaxonomyDocTypePattern = re.compile(r"\s*\{.*\"documentType\"\s*:\s*\"https://xbrl.org/[^\"/]+/(?:module|compiled|archive|labelBundle|referenceBundle)\"", flags=re.DOTALL)
# Bundle doctypes: a labelBundle contains only label objects, a referenceBundle only reference objects
# (oim-taxonomy §bundle module constraints). "bundle" was renamed to "labelBundle" (2026-07-17).
# ---------------------------------------------------------------------------
# Dated specification namespaces
#
# A specification namespace carries a status date that moves as the spec goes
# PWD -> CR -> REC, and the specification source itself carries a template in
# place of a date until one is settled -- which may be a year of review away.
# A document under development may legitimately use any of these; strictly, only
# a REC date is legitimate in production, and a specification revised after
# publication will have more than one REC date.
#
# The legacy arelle.XbrlConst idiom for this is a constant per date unioned into
# acceptance sets (see qnEnumerationItemType2014 / 2020 / YYYY). It works, but
# every new date touches every set *and* every comparison site, because a site
# must then test set membership rather than equality.
#
# Here a recognised date is instead folded onto one canonical namespace as a
# document is read, so the ~111 `qname(xbrl, ...)` sites downstream keep
# comparing a single constant, and adding a date is a table entry.
#
# The fold is only sound where the dates mean the same thing, which is true of
# every pre-REC date: they are all "the specification we implement now". A
# future REC that changes meaning would NOT be an alias, and would need the
# model to record which era it was loaded as so that behaviour can branch. That
# seam is deliberately left until there is a second REC to be concrete about.
# ---------------------------------------------------------------------------

STATUS_TEMPLATE = "template"
STATUS_PWD = "pwd"
STATUS_CR = "cr"
STATUS_REC = "rec"

# The date this build emits, and that date's standing.
statusDate = "2026"
statusDateStatus = STATUS_PWD

# Date token -> standing. The template is a syntactically legal URI path segment
# (its characters are RFC 3986 sub-delims and unreserved), so it needs no
# handling beyond appearing here.
#
# Only Tavi-era dates belong in this table. XBRL 2.1-era namespaces that happen
# to carry a year -- xbrl.org/2003/instance, /2020/extensible-enumerations-2.0,
# /2021/oim-common/error -- are fixed by their own specifications and MUST NOT
# be folded.
recognisedStatusDates = {
    "((~status_date_uri~))": STATUS_TEMPLATE,
    "2025": STATUS_PWD,
    "2026": STATUS_PWD,
}

# Paths hanging off a dated https://xbrl.org/<date> stem, listed explicitly so
# that an unrelated xbrl.org URI is never rewritten by accident.
datedNamespacePaths = frozenset((
    "",                                     # the xbrl namespace itself
    "/report", "/model", "/ref", "/utr", "/transform-types",
    "/oimtaxonomy/error", "/oimtaxonomy/calculation/error",
    "/oimtaxonomy/documentation", "/accounting",
    # documentType values share the stem and fold by the same rule
    "/module", "/compiled", "/archive", "/labelBundle", "/referenceBundle",
))

# Which standings a policy accepts as input.
namespacePolicies = {
    "production": (STATUS_REC,),
    "draft": (STATUS_REC, STATUS_CR, STATUS_PWD),
    "development": (STATUS_REC, STATUS_CR, STATUS_PWD, STATUS_TEMPLATE),
}
# No REC exists yet, so a production default would accept nothing. Change this
# to "production" once the specification is published.
defaultNamespacePolicy = "development"

# Irregular aliases: a namespace whose canonical form does not follow the dated
# stem, so the fold cannot derive it. The accounting domain is here because
# tavi.md writes it dated -- https://xbrl.org/<date>/accounting -- while the
# shipped xbrla.json declares it undated as http://xbrl.org/accounting. Both
# spellings are accepted, and mapped to the resource's, until the two are
# reconciled; then this entry goes away.
irregularNamespaceAliases = {
    "/accounting": "http://xbrl.org/accounting",
}

_datedNamespacePattern = re.compile(
    r"^https://xbrl\.org/(?P<date>[^/]+)(?P<path>/.*)?$")


def datedNamespaceParts(uri):
    """Split a dated specification namespace into (date, path), or None.

    None for anything that is not https://xbrl.org/<date><knownPath>, which
    leaves XBRL 2.1-era and undated namespaces untouched.
    """
    if not isinstance(uri, str):
        return None
    match = _datedNamespacePattern.match(uri)
    if match is None:
        return None
    path = match.group("path") or ""
    if path not in datedNamespacePaths:
        return None
    return match.group("date"), path


def namespaceStatus(uri):
    """The standing of a dated namespace's date, or None if it is not one."""
    parts = datedNamespaceParts(uri)
    return None if parts is None else recognisedStatusDates.get(parts[0])


def normalizeNamespace(uri, policy=None):
    """Fold a recognised dated namespace onto the canonical date.

    Returns (uri, status). `status` is None where the URI is not a dated
    specification namespace, in which case it is returned unchanged. An
    unrecognised date is also returned unchanged, so that it reaches the
    caller's own error reporting rather than being quietly accepted.
    """
    parts = datedNamespaceParts(uri)
    if parts is None:
        return uri, None
    date, path = parts
    status = recognisedStatusDates.get(date)
    if status is None:
        return uri, None
    if not isAcceptedNamespaceStatus(status, policy):
        return uri, status
    irregular = irregularNamespaceAliases.get(path)
    if irregular is not None:
        return irregular, status
    return f"https://xbrl.org/{statusDate}{path}", status


def isAcceptedNamespaceStatus(status, policy=None):
    if status is None:
        return True
    accepted = namespacePolicies.get(policy or defaultNamespacePolicy,
                                     namespacePolicies[defaultNamespacePolicy])
    return status in accepted


def isOimTaxonomyDocType(documentType, policy=None):
    """Whether a documentType names an OIM taxonomy document, at any known date."""
    normalized, _status = normalizeNamespace(documentType, policy)
    return normalized in oimTaxonomyDocTypes


oimLabelBundleDocType = f"https://xbrl.org/{statusDate}/labelBundle"
oimReferenceBundleDocType = f"https://xbrl.org/{statusDate}/referenceBundle"
oimBundleDocTypes = (oimLabelBundleDocType, oimReferenceBundleDocType)
oimTaxonomyDocTypes = (
        f"https://xbrl.org/{statusDate}/module",
        f"https://xbrl.org/{statusDate}/compiled",
        f"https://xbrl.org/{statusDate}/archive",
        oimLabelBundleDocType,
        oimReferenceBundleDocType,
    )

xbrl = f"https://xbrl.org/{statusDate}"
# The accounting domain namespace is deliberately undated: it is a domain model
# rather than a specification, so it does not move with the specification's
# status date. tavi.md documents it as dated; the two should reconcile.
xbrla = "http://xbrl.org/accounting"
xbrlr = f"https://xbrl.org/{statusDate}/report"
# Provisional terms implemented ahead of the specification (see resources/xbrlx.json).
# Deliberately not an xbrl.org URI: these are not sanctioned by the standards body,
# and naming them under one would misrepresent their status.
xbrlx = "https://arelle.org/2026/oim-taxonomy/experimental"

reservedPrefixNamespaces = {
    "xbrl": xbrl,
    "xbrla": xbrla,
    "xbrlr": xbrlr,
    "xbrli-2003": "https://xbrl.org/2003/instance",
    "xs": "https://www.w3.org/2001/XMLSchema",
    "enum2": "https://xbrl.org/2020/extensible-enumerations-2.0",
    "oimce": "https://xbrl.org/2021/oim-common/error",
    "oime": "http://www.xbrl.org/2021/oim/error",
    "oimte": f"https://xbrl.org/{statusDate}/oimtaxonomy/error",
    "iso4217": "http://www.xbrl.org/2003/iso4217",
    "lei": "http://standards.iso.org/iso/17442",
    "utr": f"https://xbrl.org/{statusDate}/utr",
    "ref": f"https://xbrl.org/{statusDate}/ref",
    "xbrltt": f"https://xbrl.org/{statusDate}/transform-types",
    "xbrlx": xbrlx
    }

builtInPrefixTaxonomies = { # these are in resources subdirectory
    "xbrl": "core.json",
    "xbrla": "xbrla.json",
    "xbrlm": "xbrlModel.json",
    "xbrlr": "types.json",
    "xbrli-2003": "https://xbrl.org/2003/instance",
    "xs": "xs-types.json",
    "enum2": "https://xbrl.org/2020/extensible-enumerations-2.0",
    "oimce": "oimce.json",
    "oime": "oime.json",
    "oimte": "oimte.json",
    "iso4217": "iso4217.json",
    "lei": "http://standards.iso.org/iso/17442",
    "utr": "utr.json",
    "ref": "ref.json",
    "xbrltt": "transform-types.json",
    # The SEC transformation registry, shipped alongside the standard one. Not an XBRL
    # International spec taxonomy, but a legacy US report names its transforms in this namespace
    # and a processor that cannot resolve them reports every such fact twice -- once for the
    # unresolvable transformation QName and once for the untransformed text failing its datatype.
    "ixt-sec": "sec-transform-types.json",
    "xbrlx": "xbrlx.json"
}

qnStdLabel = qname(xbrl, "xbrl:label")
qnXsDate = qname(xsd, "xs:date")
qnXsDateTime = qname(xsd, "xs:dateTime")
qnXsDuration = qname(xsd, "xs:duration")
qnXsQName = qname(xsd, "xs:QName")

qnXbrlHeadingObj = qname(xbrl, "xbrl:headingObject")
qnXbrlConceptObj = qname(xbrl, "xbrl:conceptObject")
qnXbrlDimensionObj = qname(xbrl, "xbrl:dimensionObject")
qnXbrlEntityObj = qname(xbrl, "xbrl:entityObject")
qnXbrlMemberObj = qname(xbrl, "xbrl:memberObject")
qnXbrlImportTaxonomyObj = qname(xbrl, "xbrl:importTaxonomyObject")
qnXbrlUnitObj = qname(xbrl, "xbrl:unitObject")
qnXbrlLabelObj = qname(xbrl, "xbrl:labelObject")
qnXbrlPropertyObj = qname(xbrl, "xbrl:propertyObject")
qnXbrlReferenceObj = qname(xbrl, "xbrl:referenceObject")

qnBuiltInCoreObjectsTaxonomy = qname(xbrl, "xbrl:BuiltInCoreObjectsTaxonomy")

qnErrorQname = qname(None, "InvalidQName")

objectsWithProperties = {
    qname(xbrl, "xbrl:xbrlModelObject"),
    qnXbrlConceptObj,   
    qnXbrlHeadingObj,
    qname(xbrl, "xbrl:cubeObject"),
    qname(xbrl, "xbrl:dimensionObject"),
    qname(xbrl, "xbrl:domainObject"),
    qname(xbrl, "xbrl:domainClassObject"),
    qnXbrlEntityObj,
    qname(xbrl, "xbrl:factObject"),
    qname(xbrl, "xbrl:factValueSourceObject"),
    qname(xbrl, "xbrl:factValueAnchorObject"),
    qname(xbrl, "xbrl:groupObject"),
    qname(xbrl, "xbrl:networkObject"),
    qnXbrlLabelObj,
    qnXbrlMemberObj,
    qnXbrlReferenceObj,
    qname(xbrl, "xbrl:relationshipObject"),
    }

qnXbrlRootSource = qname(xbrl, "xbrl:rootSource")

unsupportedTypedDimensionDataTypes = set(
    qname(xsd, n) for n in ("ENTITY", "ENTITIES", "ID", "IDREF", "IDREFS", "NMTOKEN", "NMTOKENS", "NOTATION"))

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

EMPTY_FROZENSET = frozenset()