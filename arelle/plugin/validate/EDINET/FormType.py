"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from enum import Enum


class FormType(Enum):
    FORM_1 = '第一号様式'
    FORM_1_AND_2 = '第一号及び第二号様式'
    FORM_2 = '第二号様式'
    FORM_2_2 = '第二号の二様式'
    FORM_2_3 = '第二号の三様式'
    FORM_2_4 = '第二号の四様式'
    FORM_2_5 = '第二号の五様式'
    FORM_2_6 = '第二号の六様式'
    FORM_2_7 = '第二号の七様式'
    FORM_3 = '第三号様式'
    FORM_3_2 = '第三号の二様式'
    FORM_4 = '第四号様式'
    FORM_4_3 = '第四号の三様式'
    FORM_4_3_2 = '第四号の三の二様式'
    FORM_4_3_3 = '第四号の三の三様式'
    FORM_5 = '第五号様式'
    FORM_5_2 = '第五号の二様式'
    FORM_5_3 = '第五号の三様式'
    FORM_5_4 = '第五号の四様式'
    FORM_6 = '第六号様式'
    FORM_6_5 = '第六号の五様式'
    FORM_6_7_AND_FORM_7 = '第六号の七及び第七号様式'
    FORM_6_9_AND_FORM_9 = '第六号の九及び第九号様式'
    FORM_7 = '第七号様式'
    FORM_7_3 = '第七号の三様式'
    FORM_7_4 = '第七号の四様式'
    FORM_8 = '第八号様式'
    FORM_8_2 = '第八号の二様式'
    FORM_8_4 = '第八号の四様式'
    FORM_9 = '第九号様式'
    FORM_9_3 = '第九号の三様式'
    FORM_9_5 = '第九号の五様式'
    FORM_10 = '第十号様式'
    FORM_10_3 = '第十号の三様式'
    FORM_11 = '第十一号様式'
    FORM_11_2 = '第十一号の二様式'
    FORM_11_2_2 = '第十一号の二の二様式'
    FORM_11_4 = '第十一号の四様式'
    FORM_12 = '第十二号様式'
    FORM_12_2 = '第十二号の二様式'
    FORM_12_5 = '第十二号の五様式'
    FORM_15 = '第十五号様式'
    FORM_15_3 = '第十五号の三様式'
    FORM_17 = '第十七号様式'
    FORM_21 = '第二十一号様式'
    FORM_25_3 = '第二十五号の三様式'
    NONE_SPECIFIED = '様式なし'

    @classmethod
    def parse(cls, value: str) -> FormType | None:
        try:
            return cls(value)
        except ValueError:
            return None

    @property
    def isCorporateForm(self) -> bool:
        return self in CORPORATE_FORMS

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
