import re

from arelle.FunctionIxt import ixtNamespaces
from arelle.ModelValue import qname

DEFAULT_MEMBER_ROLE_URI = 'https://www.nltaxonomie.nl/kvk/role/axis-defaults'
XBRLI_IDENTIFIER_PATTERN = re.compile(r"^(?!00)\d{8}$")
XBRLI_IDENTIFIER_SCHEMA = 'http://www.kvk.nl/kvk-id'
MAX_REPORT_PACKAGE_SIZE_MBS = 100

DISALLOWED_IXT_NAMESPACES = frozenset((
    ixtNamespaces["ixt v1"],
    ixtNamespaces["ixt v2"],
    ixtNamespaces["ixt v3"],
))
UNTRANSFORMABLE_TYPES = frozenset((
    "anyURI",
    "base64Binary",
    "duration",
    "hexBinary",
    "NOTATION",
    "QName",
    "time",
    "token",
    "language",
))
STYLE_IX_HIDDEN_PATTERN = re.compile(r"(.*[^\w]|^)ix-hidden\s*:\s*([\w.-]+).*")
STYLE_CSS_HIDDEN_PATTERN = re.compile(r"(.*[^\w]|^)display\s*:\s*none([^\w].*|$)")

ALLOWABLE_LANGUAGES = frozenset((
    'nl',
    'en',
    'de',
    'fr'
))

EFFECTIVE_KVK_GAAP_IFRS_ENTRYPOINT_FILES = frozenset((
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-nlgaap-ext.xsd',
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-ifrs-ext.xsd',
    'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-nlgaap-ext.xsd',
    'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-ifrs-ext.xsd',
))

EFFECTIVE_KVK_GAAP_OTHER_ENTRYPOINT_FILES = frozenset((
    'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-other-gaap.xsd',
    'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-other.xsd'
))

NON_DIMENSIONALIZED_LINE_ITEM_LINKROLES = frozenset((
    'https://www.nltaxonomie.nl/kvk/role/lineitems-nondimensional-usage',
))

TAXONOMY_URLS_BY_YEAR = {
    2024: {
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-nlgaap-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-ifrs-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-annual-report-other-gaap.xsd',
    },
    2025: {
        'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-nlgaap-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-ifrs-ext.xsd',
        'https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-annual-report-other.xsd',
    }
}

QN_DOMAIN_ITEM_TYPES = frozenset((
    qname("{http://www.xbrl.org/dtr/type/2022-03-31}nonnum:domainItemType"),
    qname("{http://www.xbrl.org/dtr/type/2024-01-31}nonnum:domainItemType")
))

STANDARD_TAXONOMY_URL_PREFIXES = frozenset((
    'http://www.nltaxonomie.nl/ifrs/20',
    'https://www.nltaxonomie.nl/ifrs/20',
    'http://www.nltaxonomie.nl/',
    'https://www.nltaxonomie.nl/',
    'http://www.xbrl.org/taxonomy/int/lei/',
    'https://www.xbrl.org/taxonomy/int/lei/',
    'http://www.xbrl.org/20',
    'https://www.xbrl.org/20',
    'http://www.xbrl.org/lrr/',
    'https://www.xbrl.org/lrr/',
    'http://xbrl.org/20',
    'https://xbrl.org/20',
    'http://xbrl.ifrs.org/',
    'https://xbrl.ifrs.org/',
    'http://www.xbrl.org/dtr/',
    'https://www.xbrl.org/dtr/',
    'http://xbrl.org/2020/extensible-enumerations-2.0',
    'https://xbrl.org/2020/extensible-enumerations-2.0',
    'http://www.w3.org/1999/xlink',
    'https://www.w3.org/1999/xlink'
))

SUPPORTED_IMAGE_TYPES_BY_IS_FILE = {
    True: ('gif', 'jpg', 'jpeg', 'png'),
    False: ('gif', 'jpeg', 'png'),
}
