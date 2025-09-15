"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .FormType import FormType


class Ordinance(Enum):
    # The below values are based on the "府令" ("Ordinance") column
    # of Table 2-3-1 in "Framework Design of EDINET Taxonomy" (ESE140301.pdf).
    DISCLOSURE = '開示府令'
    SPECIFIED_SECURITIES_DISCLOSURE = '特定有価証券開示府令'
    OTHER_SHARE_PURCHASE_TENDER_OFFER = '他社株買付府令'
    OWN_SHARE_PURCHASE_TENDER_OFFER = '自社株買付府令'
    LARGE_SHAREHOLDING = '大量保有府令'
    INTERNAL_CONTROL = '内部統制府令'


class DocumentType(Enum):
    # The below values are based on the "書類種別" ("Document Type") column
    # of Table 2-3-1 in "Framework Design of EDINET Taxonomy" (ESE140301.pdf).
    ANNUAL_SECURITIES_REPORT = '有価証券報告書'
    EXTRAORDINARY_REPORT = '臨時報告書'
    INTERNAL_CONTROL_REPORT = '内部統制報告書'
    LARGE_SHAREHOLDING_REPORT = '大量保有報告書'
    OPINION_STATEMENT = '意見表明報告書'
    REPORT_ON_STATUS_OF_OWN_SHARE_REPURCHASE = '自己株券買付状況報告書'
    RESPONSE_TO_QUESTIONS_REPORT = '対質問回答報告書'
    SECURITIES_REGISTRATION_STATEMENT = '有価証券届出書'
    SEMI_ANNUAL_REPORT = '半期報告書'
    SHELF_REGISTRATION_STATEMENT = '発行登録書'
    SHELF_REGISTRATION_SUPPLEMENT = '発行登録追補書類'
    TENDER_OFFER_REPORT = '公開買付報告書'
    TENDER_OFFER_STATEMENT = '公開買付届出書'
    WITHDRAWAL_OF_TENDER_OFFER_STATEMENT = '公開買付撤回届出書'


class Taxonomy(Enum):
    # The order of the below taxonomy values is based on Table 2-3-1 in
    # "Framework Design of EDINET Taxonomy" (ESE140301.pdf).The same table was used to
    # determine the applicable taxonomies in the FilingFormat configurations below.
    # The prefixes associated with each taxonomy were inferred from the above
    # document and "(Appendix) Conventions and Rules for EDINET Taxonomy" (ESE140304.pdf)
    DEI = 'jpdei' # 'ＤＥＩタクソノミ'
    FINANCIAL_STATEMENT = 'jppfs' # '財務諸表本表タクソノミ'
    IFRS = 'jpigp' # 国際会計基準タクソノミ
    DISCLOSURE_ORDINANCE = 'jpcrp' # '開示府令タクソノミ'
    EXTRAORDINARY_REPORT = 'jpcrp-esr' # '臨時報告書タクソノミ'
    STATUS_OF_SHARE_BUYBACKS = 'jpsps-esr' # '自己株券買付状況報告書タクソノミ'
    CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE = 'jpsps' # '特定有価証券開示府令タクソノミ'
    STATUS_OF_SPECIFIC_SECURITIES_TREASURY_STOCK_PURCHASES = 'jpsps-sbr' # '特定有価証券自己株券買付状況報告書タクソノミ'
    SPECIFIED_SECURITIES_EXTRAORDINARY_REPORT = 'jpsps-esr' # '特定有価証券臨時報告書タクソノミ'
    TENDER_OFFER_NOTIFICATION = 'jptoo-ton' # '他社株公開買付届出書タクソノミ'
    OTHER_COMPANY_OPINION_STATEMENT = 'jptoo-pst' # '他社株意見表明報告書タクソノミ'
    TENDER_OFFER_WITHDRAWAL_NOTIFICATION = 'jptoo-wto' # '他社株公開買付撤回届出書タクソノミ'
    TENDER_OFFER_REPORT = 'jptoo-tor' # '他社株公開買付報告書タクソノミ'
    OTHER_COMPANY_STOCK_QUESTION_AND_ANSWER_REPORT = 'jptoo-toa' # '他社株対質問回答報告書タクソノミ'
    TENDER_OFFER = 'jptoi' # '自社株公開買付タクソノミ'
    LARGE_VOLUME_HOLDINGS = 'jplvh' # '大量保有タクソノミ'
    INTERNAL_CONTROL = 'jpctl' # '内部統制タクソノミ'

    @classmethod
    def parse(cls, value: str) -> Taxonomy | None:
        try:
            return cls(value)
        except ValueError:
            return None

@dataclass(frozen=True)
class FilingFormat:
    ordinance: Ordinance
    documentType: DocumentType
    formType: FormType
    taxonomies: frozenset[Taxonomy]

    def includesTaxonomyPrefix(self, prefix: str) -> bool:
        taxonomy = Taxonomy.parse(prefix.split('_')[0])
        return taxonomy is not None and (
            taxonomy == Taxonomy.DEI or # DEI is always included
            taxonomy in self.taxonomies
        )

DEFAULT_DISCLOSURE_TAXONOMIES = frozenset({
    Taxonomy.FINANCIAL_STATEMENT,
    Taxonomy.IFRS,
    Taxonomy.DISCLOSURE_ORDINANCE,
})
DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES = frozenset({
    Taxonomy.FINANCIAL_STATEMENT,
    Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE,
})
FINANCIAL_STATEMENT_TAXONOMIES = frozenset({
    Taxonomy.DISCLOSURE_ORDINANCE,
    Taxonomy.FINANCIAL_STATEMENT,
})

# The below values are based on Table 2-3-1 in "Framework Design of EDINET Taxonomy" (ESE140301.pdf).
# The order is preserved. The index is used to map to other data structures. EDINET documentation often
# references this same list of formats in this same order.
FILING_FORMATS = (
    # 開示府令

    # 有価証券届出書 第二号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第二号の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_2, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 有価証券届出書 第二号の三様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_3, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 有価証券届出書 第二号の四様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_4, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第二号の五様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_5, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第二号の六様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_6, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第二号の七様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_2_7, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第三号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_3, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第三号の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_3_2, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第四号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_4, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第四号の三様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_4_3, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第五号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_5, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第五号の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_5_2, DEFAULT_DISCLOSURE_TAXONOMIES),
    # 臨時報告書 第五号の三様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.EXTRAORDINARY_REPORT, FormType.FORM_5_3, frozenset({Taxonomy.EXTRAORDINARY_REPORT})),
    # 有価証券届出書 第七号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_7, FINANCIAL_STATEMENT_TAXONOMIES),
    # 有価証券届出書 第七号の四様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_7_4, FINANCIAL_STATEMENT_TAXONOMIES),
    # 有価証券報告書 第八号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_8, FINANCIAL_STATEMENT_TAXONOMIES),
    # 有価証券報告書 第九号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_9, FINANCIAL_STATEMENT_TAXONOMIES),

    # 半期報告書 第九号の三様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_9_3, FINANCIAL_STATEMENT_TAXONOMIES),
    # 半期報告書 第十号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_10, FINANCIAL_STATEMENT_TAXONOMIES),
    # 発行登録書 第十一号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SHELF_REGISTRATION_STATEMENT, FormType.FORM_11, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 発行登録書 第十一号の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SHELF_REGISTRATION_STATEMENT, FormType.FORM_11_2, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 発行登録書 第十一号の二の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SHELF_REGISTRATION_STATEMENT, FormType.FORM_11_2_2, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 発行登録追補書類 第十二号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SHELF_REGISTRATION_SUPPLEMENT, FormType.FORM_12, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 発行登録追補書類 第十二号の二様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.SHELF_REGISTRATION_SUPPLEMENT, FormType.FORM_12_2, frozenset({Taxonomy.DISCLOSURE_ORDINANCE})),
    # 自己株券買付状況報 告書 第十七号様式
    FilingFormat(Ordinance.DISCLOSURE,  DocumentType.REPORT_ON_STATUS_OF_OWN_SHARE_REPURCHASE, FormType.FORM_17, frozenset({Taxonomy.STATUS_OF_SHARE_BUYBACKS})),

    # 特定有価証券開示府令

    # 有価証券届出書 第四号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_4, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第四号の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_4_3, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第四号の三の二様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_4_3_2, frozenset({Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE})),
    # 有価証券届出書 第四号の三の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_4_3_3, frozenset({Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE})),
    # 有価証券届出書 第五号の二様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_5_2, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第五号の四様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_5_4, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第六号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_6, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券届出書 第六号の五様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SECURITIES_REGISTRATION_STATEMENT, FormType.FORM_6_5, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書【みなし有価証券届出書】第六号の七及び第七号 様式 - manually switched to ANNUAL_SECURITIES_REPORT
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_6_7_AND_FORM_7, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書【みなし有価証券届出書】第六号の九及び第九号 様式 - manually switched to ANNUAL_SECURITIES_REPORT
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_6_9_AND_FORM_9, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第七号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_7, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第七号の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_7_3, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第八号の二様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_8_2, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第八号の四様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_8_4, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第九号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_9, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 有価証券報告書 第九号の五様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.ANNUAL_SECURITIES_REPORT, FormType.FORM_9_5, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_10, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十号の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_10_3, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十一号の二様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_11_2, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十一号の四様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_11_4, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十二号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_12, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 半期報告書 第十二号の五様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SEMI_ANNUAL_REPORT, FormType.FORM_12_5, DEFAULT_SPECIFIED_SECURITIES_DISCLOSURE_TAXONOMIES),
    # 発行登録書 第十五号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SHELF_REGISTRATION_STATEMENT, FormType.FORM_15, frozenset({Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE})),
    # 発行登録書 第十五号の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SHELF_REGISTRATION_STATEMENT, FormType.FORM_15_3, frozenset({Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE})),
    # 発行登録追補書類 第二十一号様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.SHELF_REGISTRATION_SUPPLEMENT, FormType.FORM_21, frozenset({Taxonomy.CABINET_OFFICE_ORDINANCE_ON_SPECIFIED_SECURITIES_DISCLOSURE})),
    # 自己株券買付状況報 告書 第二十五号の三様式
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.REPORT_ON_STATUS_OF_OWN_SHARE_REPURCHASE, FormType.FORM_25_3, frozenset({Taxonomy.STATUS_OF_SPECIFIC_SECURITIES_TREASURY_STOCK_PURCHASES})),
    # 臨時報告書
    FilingFormat(Ordinance.SPECIFIED_SECURITIES_DISCLOSURE,  DocumentType.EXTRAORDINARY_REPORT, FormType.NONE_SPECIFIED, frozenset({Taxonomy.SPECIFIED_SECURITIES_EXTRAORDINARY_REPORT})),

    # 他社株買付府令

    # 公開買付届出書 第二号様式
    FilingFormat(Ordinance.OTHER_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.TENDER_OFFER_STATEMENT, FormType.FORM_2, frozenset({Taxonomy.TENDER_OFFER_NOTIFICATION})),
    # 意見表明報告書 第四号様式
    FilingFormat(Ordinance.OTHER_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.OPINION_STATEMENT, FormType.FORM_4, frozenset({Taxonomy.OTHER_COMPANY_OPINION_STATEMENT})),
    # 公開買付撤回届出書 第五号様式
    FilingFormat(Ordinance.OTHER_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.WITHDRAWAL_OF_TENDER_OFFER_STATEMENT, FormType.FORM_5, frozenset({Taxonomy.TENDER_OFFER_WITHDRAWAL_NOTIFICATION})),
    # 公開買付報告書 第六号様式
    FilingFormat(Ordinance.OTHER_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.TENDER_OFFER_REPORT, FormType.FORM_6, frozenset({Taxonomy.TENDER_OFFER_REPORT})),
    # 対質問回答報告書 第八号様式
    FilingFormat(Ordinance.OTHER_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.RESPONSE_TO_QUESTIONS_REPORT, FormType.FORM_8, frozenset({Taxonomy.OTHER_COMPANY_STOCK_QUESTION_AND_ANSWER_REPORT})),

    # 自社株買付府令

    # 公開買付届出書 第二号様式
    FilingFormat(Ordinance.OWN_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.TENDER_OFFER_STATEMENT, FormType.FORM_2, frozenset({Taxonomy.TENDER_OFFER})),
    # 公開買付撤回届出書 第三号様式
    FilingFormat(Ordinance.OWN_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.WITHDRAWAL_OF_TENDER_OFFER_STATEMENT, FormType.FORM_3, frozenset({Taxonomy.TENDER_OFFER})),
    # 公開買付報告書 第四号様式
    FilingFormat(Ordinance.OWN_SHARE_PURCHASE_TENDER_OFFER,  DocumentType.TENDER_OFFER_REPORT, FormType.FORM_4, frozenset({Taxonomy.TENDER_OFFER})),

    # 大量保有府令

    # 大量保有報告書 第一号様式
    FilingFormat(Ordinance.LARGE_SHAREHOLDING,  DocumentType.LARGE_SHAREHOLDING_REPORT, FormType.FORM_1, frozenset({Taxonomy.LARGE_VOLUME_HOLDINGS})),
    # 大量保有報告書 第一号及び第二号様式
    FilingFormat(Ordinance.LARGE_SHAREHOLDING,  DocumentType.LARGE_SHAREHOLDING_REPORT, FormType.FORM_1_AND_2, frozenset({Taxonomy.LARGE_VOLUME_HOLDINGS})),
    # 大量保有報告書 第三号様式
    FilingFormat(Ordinance.LARGE_SHAREHOLDING,  DocumentType.LARGE_SHAREHOLDING_REPORT, FormType.FORM_3, frozenset({Taxonomy.LARGE_VOLUME_HOLDINGS})),

    # 内部統制府令

    # 内部統制報告書 第一号様式
    FilingFormat(Ordinance.INTERNAL_CONTROL,  DocumentType.INTERNAL_CONTROL_REPORT, FormType.FORM_1, frozenset({Taxonomy.INTERNAL_CONTROL})),
)
