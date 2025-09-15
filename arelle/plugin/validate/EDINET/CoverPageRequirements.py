"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from arelle.ModelValue import QName
from arelle.plugin.validate.EDINET.FilingFormat import FilingFormat


# Cover page requirements parsing is designed so that the contents of Attachment #5
# in "(Appendix) Taxonomy Extension Guideline" (ESE140111.zip), or future versions,
# can be easily exported to a CSV file where the rows correspond to Cover Page items
# andt the columns correspond to different formats.
class CoverPageRequirements:
    _coverPageItems: tuple[QName, ...]
    _csvPath: Path
    _data: list[list[CoverPageItemStatus | None]] | None
    _filingFormats: tuple[FilingFormat, ...]

    def __init__(self, csvPath: Path, coverPageItems: tuple[QName, ...], filingFormats: tuple[FilingFormat, ...]):
        self._coverPageItems = coverPageItems
        self._csvPath = csvPath
        self._data = None
        self._filingFormats = filingFormats

    def _load(self) -> list[list[CoverPageItemStatus | None]]:
        if self._data is None:
            with open(self._csvPath, encoding='utf-8') as f:
                self._data = [
                    [
                        CoverPageItemStatus.parse(cell) for cell in line.strip().split(',')
                    ]
                    for line in f.readlines()
                ]
        return self._data


    def get(self, coverPageItem: QName, filingFormat: FilingFormat) -> CoverPageItemStatus | None:
        try:
            coverPageItemIndex = self._coverPageItems.index(coverPageItem)
            filingFormatIndex = self._filingFormats.index(filingFormat)
            return self._load()[coverPageItemIndex][filingFormatIndex]
        except (IndexError, ValueError):
            return None


class CoverPageItemStatus(Enum):
    # The values of the enum correspond to the symbols used in the spreadsheet.
    PROHIBITED = '×'
    OPTIONAL = '△'
    CONDITIONAL = '○'
    REQUIRED = '◎'

    @classmethod
    def parse(cls, value: str) -> CoverPageItemStatus | None:
        try:
            return cls(value)
        except ValueError:
            return None

# The below values are based on Attachment #5 in "(Appendix) Taxonomy Extension Guideline" (ESE140111.zip).
# Column D lists the elements of the cover page. Rows purely for grouping are omitted.
# The order is preserved. The index is used to map to other data structures.
COVER_PAGE_ITEM_LOCAL_NAMES = (
    # Submitter Information (提出者情報)
    'EDINETCodeDEI',
    'FundCodeDEI',
    'SecurityCodeDEI',
    'FilerNameInJapaneseDEI',
    'FilerNameInEnglishDEI',
    'FundNameInJapaneseDEI',
    'FundNameInEnglishDEI',

    # Document Submission Information (提出書類情報)
    'CabinetOfficeOrdinanceDEI',
    'DocumentTypeDEI',
    'AccountingStandardsDEI',
    'WhetherConsolidatedFinancialStatementsArePreparedDEI',
    'IndustryCodeWhenConsolidatedFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI',
    'IndustryCodeWhenFinancialStatementsArePreparedInAccordanceWithIndustrySpecificRegulationsDEI',

    # Current Fiscal Year (当会計期間)
    'CurrentFiscalYearStartDateDEI',
    'CurrentPeriodEndDateDEI',
    'TypeOfCurrentPeriodDEI',
    'CurrentFiscalYearEndDateDEI',

    # Previous Fiscal Year (比較対象会計期間)
    'PreviousFiscalYearStartDateDEI',
    'ComparativePeriodEndDateDEI',
    'PreviousFiscalYearEndDateDEI',

    # Next Fiscal Year (次の中間期の会計期間)
    'NextFiscalYearStartDateDEI',
    'EndDateOfQuarterlyOrSemiAnnualPeriodOfNextFiscalYearDEI',

    'NumberOfSubmissionDEI',
    'AmendmentFlagDEI',
    'IdentificationOfDocumentSubjectToAmendmentDEI',

    # Type of Correction (訂正の種類)
    'ReportAmendmentFlagDEI',
    'XBRLAmendmentFlagDEI',
)
