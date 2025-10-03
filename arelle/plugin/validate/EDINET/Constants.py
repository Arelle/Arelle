"""
See COPYRIGHT.md for copyright information.
"""
from enum import Enum

import regex

from arelle.ModelValue import qname

class AccountingStandard(Enum):
    IFRS = 'IFRS'
    JAPAN_GAAP = 'Japan GAAP'
    US_GAAP = 'US GAAP'


domainItemTypeQname = qname("{http://www.xbrl.org/dtr/type/non-numeric}nonnum:domainItemType")

qnEdinetManifestInsert = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}insert")
qnEdinetManifestInstance = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance")
qnEdinetManifestItem = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}item")
qnEdinetManifestIxbrl = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl")
qnEdinetManifestList = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}list")
qnEdinetManifestTitle = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}title")
qnEdinetManifestTocComposition = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}tocComposition")
xhtmlDtdExtension = "xhtml1-strict-ix.dtd"

COVER_PAGE_FILENAME_PREFIX = "0000000_header_"

PROHIBITED_HTML_ATTRIBUTES = frozenset({
    'onblur',
    'onchange',
    'onclick',
    'ondblclick',
    'onfocus',
    'onkeydown',
    'onkeypress',
    'onkeyup',
    'onload',
    'onmousedown',
    'onmousemove',
    'onmouseout',
    'onmouseover',
    'onmouseup',
    'onreset',
    'onselect',
    'onsubmit',
    'onunload',
})

PROHIBITED_HTML_TAGS = frozenset({
    'applet',
    'embed',
    'form',
    'frame',
    'frameset',
    'iframe',
    'input',
    'object',
    'plaintext',
    'pre',
    'script',
    'select',
    'textarea',
})

NUMERIC_LABEL_ROLES = frozenset({
    'http://www.xbrl.org/2003/role/positiveLabel',
    'http://www.xbrl.org/2003/role/positiveTerseLabel',
    'http://www.xbrl.org/2003/role/positiveVerboseLabel',
    'http://www.xbrl.org/2003/role/negativeLabel',
    'http://www.xbrl.org/2003/role/negativeTerseLabel',
    'http://www.xbrl.org/2003/role/negativeVerboseLabel',
    'http://www.xbrl.org/2003/role/zeroLabel',
    'http://www.xbrl.org/2003/role/zeroTerseLabel',
    'http://www.xbrl.org/2003/role/zeroVerboseLabel',
    'http://www.xbrl.org/2003/role/totalLabel',
    'http://www.xbrl.org/2009/role/negatedLabel',
    'http://www.xbrl.org/2009/role/negatedPeriodEndLabel',
    'http://www.xbrl.org/2009/role/negatedPeriodStartLabel',
    'http://www.xbrl.org/2009/role/negatedTotalLabel',
    'http://www.xbrl.org/2009/role/negatedNetLabel',
    'http://www.xbrl.org/2009/role/negatedTerseLabel',
})

PATTERN_CODE = r'(?P<code>[A-Za-z\d]*)'
PATTERN_CONSOLIDATED = r'(?P<consolidated>c|n)'
PATTERN_COUNT = r'(?P<count>\d{2})'
PATTERN_DATE1 = r'(?P<year1>\d{4})-(?P<month1>\d{2})-(?P<day1>\d{2})'
PATTERN_DATE2 = r'(?P<year2>\d{4})-(?P<month2>\d{2})-(?P<day2>\d{2})'
PATTERN_FORM = r'(?P<form>\d{6})'
PATTERN_LINKBASE = r'(?P<linkbase>lab|lab-en|gla|pre|def|cal)'
PATTERN_MAIN = r'(?P<main>\d{7})'
PATTERN_NAME = r'(?P<name>[a-z]{6})'
PATTERN_ORDINANCE = r'(?P<ordinance>[a-z]*)'
PATTERN_PERIOD = r'(?P<period>c|p)'  # TODO: Have only seen "c" in sample/public filings, assuming "p" for previous.
PATTERN_REPORT = r'(?P<report>[a-z]*)'
PATTERN_REPORT_SERIAL = r'(?P<report_serial>\d{3})'
PATTERN_SERIAL = r'(?P<serial>\d{3})'

PATTERN_AUDIT_REPORT_PREFIX = rf'jpaud-{PATTERN_REPORT}-{PATTERN_PERIOD}{PATTERN_CONSOLIDATED}'
PATTERN_REPORT_PREFIX = rf'jp{PATTERN_ORDINANCE}{PATTERN_FORM}-{PATTERN_REPORT}'
PATTERN_SUFFIX = rf'{PATTERN_REPORT_SERIAL}_{PATTERN_CODE}-{PATTERN_SERIAL}_{PATTERN_DATE1}_{PATTERN_COUNT}_{PATTERN_DATE2}'

PATTERN_URI_HOST = r'http:\/\/disclosure\.edinet-fsa\.go\.jp'
PATTERN_AUDIT_URI_PREFIX = rf'jpaud\/{PATTERN_REPORT}\/{PATTERN_PERIOD}{PATTERN_CONSOLIDATED}'
PATTERN_REPORT_URI_PREFIX = rf'jp{PATTERN_ORDINANCE}{PATTERN_FORM}\/{PATTERN_REPORT}'
PATTERN_URI_SUFFIX = rf'{PATTERN_REPORT_SERIAL}\/{PATTERN_CODE}-{PATTERN_SERIAL}\/{PATTERN_DATE1}\/{PATTERN_COUNT}\/{PATTERN_DATE2}'

# Extension namespace URI for report
# Example: http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/X99002-000/2025-03-31/01/2025-06-28
REPORT_NAMESPACE_URI_PATTERN = regex.compile(rf'{PATTERN_URI_HOST}\/{PATTERN_REPORT_URI_PREFIX}\/{PATTERN_URI_SUFFIX}')

# Extension namespace URI for audit report
# Example: http://disclosure.edinet-fsa.go.jp/jpaud/aar/cn/001/X99002-000/2025-03-31/01/2025-06-28
AUDIT_NAMESPACE_URI_PATTERN = regex.compile(rf'{PATTERN_URI_HOST}\/{PATTERN_AUDIT_URI_PREFIX}\/{PATTERN_URI_SUFFIX}')

# Extension namespace prefix for report
# Example: jpcrp040300-ssr_X99005-000
REPORT_PREFIX_PATTERN = regex.compile(rf'{PATTERN_REPORT_PREFIX}_{PATTERN_CODE}-{PATTERN_SERIAL}')

# Extension namespace prefix for audit report
# Example: jpaud-qrr-cn_X99005-000
AUDIT_PREFIX_PATTERN = regex.compile(rf'{PATTERN_AUDIT_REPORT_PREFIX}_{PATTERN_CODE}-{PATTERN_SERIAL}')

# Schema file for report
# Example: jpcrp050300-esr-001_X99007-000_2025-04-10_01_2025-04-10.xsd
REPORT_SCHEMA_FILENAME_PATTERN = regex.compile(rf'{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}.xsd')

# Schema file for audit report
# Example: jpaud-aar-cn-001_X99001-000_2025-03-31_01_2025-06-28.xsd
AUDIT_SCHEMA_FILENAME_PATTERN = regex.compile(rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}.xsd')

# Linkbase file for report
# Example: jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_cal.xml
REPORT_LINKBASE_FILENAME_PATTERN = regex.compile(rf'{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_{PATTERN_LINKBASE}.xml')

# Linkbase file for audit report
# Example: jpaud-qrr-cc-001_X99001-000_2025-03-31_01_2025-11-20_pre.xml
AUDIT_LINKBASE_FILENAME_PATTERN = regex.compile(rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}_{PATTERN_LINKBASE}.xml')

# Cover page file for report
# Example: 0000000_header_jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_ixbrl.htm
REPORT_COVER_FILENAME_PATTERN = regex.compile(rf'{COVER_PAGE_FILENAME_PREFIX}{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm')

# Main file for report
# Example: 0205020_honbun_jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_ixbrl.htm
REPORT_MAIN_FILENAME_PATTERN = regex.compile(rf'{PATTERN_MAIN}_{PATTERN_NAME}_{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm')

# Main file for audit report
# Example: jpaud-qrr-cc-001_X99001-000_2025-03-31_01_2025-11-20_pre.xml
AUDIT_MAIN_FILENAME_PATTERN = regex.compile(rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm')
