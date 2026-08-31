"""
See COPYRIGHT.md for copyright information.

UKSEF taxonomy validation rules (UKFRC1, UKFRC2).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import regex as re

from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC, TARGET_UKFRS
from ...PluginValidationDataExtension import PluginValidationDataExtension
from ...Util import isExtensionDoc

_: TypeGetText

_UKSEF_ENTRY_POINT_PATTERN = re.compile(
    r"^https://xbrl\.frc\.org\.uk/(FRS-102|IFRS)/(2023|2024|2025)-01-01/UKSEF/\1-\2-01-01\.xsd$"
)
_ESEF_TAXONOMY_URL_PATTERN = re.compile(
    r"^http[s]?://www\.esma\.europa\.eu/taxonomy/(\d{4})-\d{2}-\d{2}/esef_"
)
_MIN_ESEF_YEAR = 2022
_LINK_SCHEMA_REF = f"{{{XbrlConst.link}}}schemaRef"
_XLINK_HREF = f"{{{XbrlConst.xlink}}}href"


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking for the UKFRS target
    hook=ValidationHook.FINALLY,
)
def rule_ukfrc1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC1: UKSEF 2025 reports MUST have a reference (a schemaRef in a “UKFRS” targeted ix:references element)
    to one of the three possible FRC taxonomy entry-points for either FRS102 or IFRS. Companies House allow use
    of the current and last two annual versions of the FRC’s Taxonomy Suite. The 2025, 2024 or 2023 Taxonomy
    Suites all contain the relevant UKSEF entry-points:
    2025 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2025-01-01/UKSEF/FRS-102-2025-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2025-01-01/UKSEF/IFRS-2025-01-01.xsd
    2024 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2024-01-01/UKSEF/FRS-102-2024-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2024-01-01/UKSEF/IFRS-2024-01-01.xsd
    2023 Taxonomy Suite
    *	https://xbrl.frc.org.uk/FRS-102/2023-01-01/UKSEF/FRS-102-2023-01-01.xsd; or
    *	https://xbrl.frc.org.uk/IFRS/2023-01-01/UKSEF/IFRS-2023-01-01.xsd
    The reference must be in the report, NOT in the extension taxonomy.
    """
    if val.authority != AUTHORITY_UKFRC:
        return

    if val.ixdsReferences and TARGET_UKFRS not in val.ixdsReferences:
        yield Validation.error(
            codes="ESEF.UKFRC1.incorrectTarget",
            msg=_(
                'UKSEF reports MUST have a "UKFRS" targeted ix:references element. '
                'No matching ix:references element was found in the report.'
                ),
            )

    if not pluginData.isUkfrsTarget(val.modelXbrl):
        return

    if targetIxReferences := val.ixdsReferences.get(TARGET_UKFRS, []):
        uksefSchemaRefs: list[ModelObject] = []
        for referencesElt in targetIxReferences:
            for schemaRef in referencesElt.iterdescendants(tag=_LINK_SCHEMA_REF):
                href = schemaRef.get(_XLINK_HREF, "").strip()
                if _UKSEF_ENTRY_POINT_PATTERN.match(href):
                    uksefSchemaRefs.append(schemaRef)

        if len(uksefSchemaRefs) > 1:
            yield Validation.error(
                codes="ESEF.UKFRC1.multipleEntryPoints",
                msg=_(
                    'UKSEF reports MUST have a single schemaRef in a "UKFRS" targeted ix:references element. '
                    'Multiple matching schemaRefs were found in the report.'
                    ),
                modelObject=uksefSchemaRefs,
                )

        if not uksefSchemaRefs:
            yield Validation.error(
                codes="ESEF.UKFRC1.unsupportedEntryPoint",
                msg=_(
                    'UKSEF reports MUST have a schemaRef in a "UKFRS" targeted ix:references element '
                    'pointing to one of the FRC UKSEF entry-points for FRS-102 or IFRS from the 2023, '
                    '2024, or 2025 Taxonomy Suites (e.g. '
                    'https://xbrl.frc.org.uk/FRS-102/2025-01-01/UKSEF/FRS-102-2025-01-01.xsd or '
                    'https://xbrl.frc.org.uk/IFRS/2025-01-01/UKSEF/IFRS-2025-01-01.xsd). '
                    'No matching schemaRef was found in the report.'
                    ),
                )
    return


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC2: UKSEF 2025 reports MUST only be used in conjunction with ESEF 2022 or later.

    Locate the issuer's extension taxonomy via the schemaRef in the default target ix:references
    element, then inspect that extension schema's imports for the referenced ESEF taxonomy year.
    If the referenced ESEF taxonomy year is earlier than 2022, report an error.
    """
    if val.authority != AUTHORITY_UKFRC:
        return

    # Follow schemaRefs to the extension schema ModelDocuments and gather imported URLs.
    importedUrls: set[str] = set()
    for doc in val.modelXbrl.urlDocs.values():
        if not isExtensionDoc(val, doc):
            continue
        for referencedDoc, docRef in doc.referencesDocument.items():
            if "import" in docRef.referenceTypes:
                importedUrls.add(referencedDoc.uri)

    esefYears: list[int] = []
    for url in importedUrls:
        match = _ESEF_TAXONOMY_URL_PATTERN.match(url)
        if match:
            esefYears.append(int(match.group(1)))

    if esefYears and max(esefYears) < _MIN_ESEF_YEAR:
        yield Validation.error(
            codes="ESEF.UKFRC2.incorrectEsefTaxonomyVersionUsed",
            msg=_(
                "UKSEF 2025 reports MUST only be used in conjunction with ESEF 2022 or later. "
                "The extension taxonomy references ESEF taxonomy version %(year)s."
            ),
            year=max(esefYears),
        )

    return
