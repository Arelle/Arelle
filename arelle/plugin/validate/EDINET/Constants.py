"""
See COPYRIGHT.md for copyright information.
"""
from enum import Enum

from arelle.ModelValue import qname

class DeiFormType(Enum):
    FORM_2_4 = '第二号の四様式'
    FORM_2_7 = '第二号の七様式'
    FORM_3 = '第三号様式'

CORPORATE_FORMS ={
    DeiFormType.FORM_2_4,
    DeiFormType.FORM_2_7,
    DeiFormType.FORM_3,
}

qnEdinetManifestInsert = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}insert")
qnEdinetManifestInstance = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance")
qnEdinetManifestItem = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}item")
qnEdinetManifestIxbrl = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl")
qnEdinetManifestList = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}list")
qnEdinetManifestTitle = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}title")
qnEdinetManifestTocComposition = qname("{http://disclosure.edinet-fsa.go.jp/2013/manifest}tocComposition")
