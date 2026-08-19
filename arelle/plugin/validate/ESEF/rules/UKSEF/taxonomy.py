"""
See COPYRIGHT.md for copyright information.

UKSEF taxonomy validation rules (UKFRC1, UKFRC2).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import regex as re

from arelle import XbrlConst
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC, TARGET_UKFRS
from ...PluginValidationDataExtension import PluginValidationDataExtension

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
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
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
        return None

    model_xbrl = val.modelXbrl
    if pluginData.isUkfrsTarget(model_xbrl):
        return None

    ixds_html_elements = getattr(model_xbrl, "ixdsHtmlElements", None)
    if not ixds_html_elements:
        return None

    found_hrefs: list[str] = []
    is_valid_target = False
    for ixds_html_root_elt in ixds_html_elements:
        ix_ns_tag = getattr(ixds_html_root_elt.modelDocument, "ixNStag", "")
        for references_elt in ixds_html_root_elt.iterdescendants(tag=f"{ix_ns_tag}references"):
            if references_elt.get("target") != TARGET_UKFRS:
                continue

            is_valid_target = True
            for schema_ref in references_elt.iterdescendants(tag=_LINK_SCHEMA_REF):
                href = schema_ref.get(_XLINK_HREF, "").strip()
                if _UKSEF_ENTRY_POINT_PATTERN.match(href):
                    found_hrefs.append(href)

    if not is_valid_target:
        yield Validation.error(
            codes="ESEF.UKFRC1.incorrectTarget",
            msg=_(
                "UKSEF reports MUST have a \"UKFRS\" targeted ix:references element. "
                "No matching ix:references element was found in the report."
            ),
        )

    if len(found_hrefs) > 1:
        yield Validation.error(
            codes="ESEF.UKFRC1.multipleEntryPoints",
            msg=_(
                "UKSEF reports MUST have a single schemaRef in a \"UKFRS\" targeted ix:references element. "
                "Multiple matching schemaRefs were found in the report."
            ),
        )

    if not found_hrefs:
        yield Validation.error(
            codes="ESEF.UKFRC1.unsupportedEntryPoint",
            msg=_(
                "UKSEF reports MUST have a schemaRef in a \"UKFRS\" targeted ix:references element "
                "pointing to one of the FRC UKSEF entry-points for FRS-102 or IFRS from the 2023, "
                "2024, or 2025 Taxonomy Suites (e.g. "
                "https://xbrl.frc.org.uk/FRS-102/2025-01-01/UKSEF/FRS-102-2025-01-01.xsd or "
                "https://xbrl.frc.org.uk/IFRS/2025-01-01/UKSEF/IFRS-2025-01-01.xsd). "
                "No matching schemaRef was found in the report."
            ),
        )

    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC2: UKSEF 2025 reports MUST only be used in conjunction with ESEF 2022 or later.

    Locate the issuer's extension taxonomy via the schemaRef in the default target ix:references
    element, then inspect that extension schema's imports for the referenced ESEF taxonomy year.
    If the referenced ESEF taxonomy year is earlier than 2022, report an error.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None

    model_xbrl = val.modelXbrl
    ixds_html_elements = getattr(model_xbrl, "ixdsHtmlElements", None)
    if not ixds_html_elements:
        return None

    # Collect extension schema hrefs from the default-target ix:references elements.
    extension_hrefs: list[str] = []
    for ixds_html_root_elt in ixds_html_elements:
        ix_ns_tag = getattr(ixds_html_root_elt.modelDocument, "ixNStag", "")
        for references_elt in ixds_html_root_elt.iterdescendants(tag=f"{ix_ns_tag}references"):
            if references_elt.get("target") is not None:
                continue

            for schema_ref in references_elt.iterdescendants(tag=_LINK_SCHEMA_REF):
                href = schema_ref.get(_XLINK_HREF, "").strip()
                if href:
                    extension_hrefs.append(href)

    if not extension_hrefs:
        return None

    # Follow schemaRefs to the extension schema ModelDocuments and gather imported URLs.
    imported_urls: set[str] = set()
    url_docs = model_xbrl.urlDocs
    for href in extension_hrefs:
        extension_doc = url_docs.get(href)
        if extension_doc is None:
            # Try to resolve via referenced document uris (href may differ from normalized uri).
            for uri, doc in url_docs.items():
                if uri.endswith(href) or href.endswith(uri):
                    extension_doc = doc
                    break
        if extension_doc is None:
            continue
        for referenced_doc, doc_ref in extension_doc.referencesDocument.items():
            if "import" in doc_ref.referenceTypes:
                imported_urls.add(referenced_doc.uri)

    esef_years: list[int] = []
    for url in imported_urls:
        match = _ESEF_TAXONOMY_URL_PATTERN.match(url)
        if match:
            esef_years.append(int(match.group(1)))

    if esef_years and max(esef_years) < _MIN_ESEF_YEAR:
        yield Validation.error(
            codes="ESEF.UKFRC2.incorrectEsefTaxonomyVersionUsed",
            msg=_(
                "UKSEF 2025 reports MUST only be used in conjunction with ESEF 2022 or later. "
                "The extension taxonomy references ESEF taxonomy version %(year)s."
            ),
            year=max(esef_years),
        )

    return None
