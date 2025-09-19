"""
See COPYRIGHT.md for copyright information.
"""
from enum import Enum

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
