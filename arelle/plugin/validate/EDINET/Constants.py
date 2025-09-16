"""
See COPYRIGHT.md for copyright information.
"""
from enum import Enum

from arelle.ModelValue import qname

class AccountingStandard(Enum):
    IFRS = 'IFRS'
    JAPAN_GAAP = 'Japan GAAP'
    US_GAAP = 'US GAAP'


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
