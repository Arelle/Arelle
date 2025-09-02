"""
See COPYRIGHT.md for copyright information.
"""
from enum import Enum

from arelle.ModelValue import qname

class AccountingStandard(Enum):
    IFRS = 'IFRS'
    JAPAN_GAAP = 'Japan GAAP'
    US_GAAP = 'US GAAP'

class FormType(Enum):
    FORM_2_4 = '第二号の四様式'
    FORM_2_7 = '第二号の七様式'
    FORM_3 = '第三号様式'
    FORM_4 = '第四号様式'

    @property
    def isStockReport(self) -> bool:
        return self in STOCK_REPORT_FORMS

CORPORATE_FORMS =frozenset([
    FormType.FORM_2_4,
    FormType.FORM_2_7,
    FormType.FORM_3,
])
STOCK_REPORT_FORMS = frozenset([
    FormType.FORM_3,
    FormType.FORM_4,
])
qnEdinetManifestInsert = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}insert")
qnEdinetManifestInstance = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance")
qnEdinetManifestItem = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}item")
qnEdinetManifestIxbrl = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl")
qnEdinetManifestList = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}list")
qnEdinetManifestTitle = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}title")
qnEdinetManifestTocComposition = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}tocComposition")
xhtmlDtdExtension = "xhtml1-strict-ix.dtd"

COVER_PAGE_FILENAME_PREFIX = "0000000_header_"

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
