"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
    DISCLOSURE_SYSTEM_NT18,
    DISCLOSURE_SYSTEM_NT19,
    DISCLOSURE_SYSTEM_NT20,

    DISCLOSURE_SYSTEM_NL_INLINE_2024,
    DISCLOSURE_SYSTEM_NL_INLINE_2024_GAAP_OTHER,
    DISCLOSURE_SYSTEM_NL_INLINE_2025,
    DISCLOSURE_SYSTEM_NL_INLINE_2025_GAAP_OTHER,

    DISCLOSURE_SYSTEM_NL_INLINE_MULTI_TARGET,
    ALL_NL_INLINE_DISCLOSURE_SYSTEMS,
)
from .PluginValidationDataExtension import PluginValidationDataExtension

_BW2_TITEL9_PREFIX = "bw2-titel9"
_KVK_PREFIX = "kvk"

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginValidationDataExtension:
        assert validateXbrl is not None
        disclosureSystem = validateXbrl.disclosureSystem.name
        if disclosureSystem == DISCLOSURE_SYSTEM_NT16:
            ifrsNamespace = None
            jenvNamespace = "http://www.nltaxonomie.nl/nt16/jenv/20211208/dictionary/jenv-bw2-data"
            kvkINamespace = "http://www.nltaxonomie.nl/nt16/kvk/20211208/dictionary/kvk-data"
            nlTypesNamespace = "http://www.nltaxonomie.nl/nt16/sbr/20210301/dictionary/nl-types"
            rjNamespace = None
            entrypointRoot = "http://www.nltaxonomie.nl/nt16/kvk/20211208/entrypoints/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-rpt-jaarverantwoording-2021-ifrs-full.xsd",
                "kvk-rpt-jaarverantwoording-2021-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd",
                "kvk-rpt-jaarverantwoording-2021-ifrs-smes.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-banken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-beleggingsentiteiten.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-cooperaties.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-cv-vof.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-fondsenwervende-organisaties-klein.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-fondsenwervende-organisaties.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-groot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-groot.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-klein-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-klein-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-klein-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-klein.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-micro-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-micro.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-organisaties-zonder-winststreven-klein.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-organisaties-zonder-winststreven.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-pensioenfondsen.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-premiepensioeninstellingen.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-stichtingen.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-verzekeringsmaatschappijen.xsd",
                "kvk-rpt-jaarverantwoording-2021-nlgaap-zorginstellingen.xsd",
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT17:
            ifrsNamespace = None
            jenvNamespace = "http://www.nltaxonomie.nl/nt17/jenv/20221214/dictionary/jenv-bw2-data"
            kvkINamespace = "http://www.nltaxonomie.nl/nt17/kvk/20221214/dictionary/kvk-data"
            nlTypesNamespace = "http://www.nltaxonomie.nl/nt17/sbr/20220301/dictionary/nl-types"
            rjNamespace = None
            entrypointRoot = "http://www.nltaxonomie.nl/nt17/kvk/20221214/entrypoints/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-rpt-jaarverantwoording-2022-ifrs-full.xsd",
                "kvk-rpt-jaarverantwoording-2022-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd",
                "kvk-rpt-jaarverantwoording-2022-ifrs-smes.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-banken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-beleggingsentiteiten.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-cooperaties.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-cv-vof.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-fondsenwervende-organisaties-klein.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-fondsenwervende-organisaties.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-groot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-groot.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-klein-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-klein-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-klein-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-klein.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-micro-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-micro.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-plus.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-organisaties-zonder-winststreven-klein.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-organisaties-zonder-winststreven.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-pensioenfondsen.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-premiepensioeninstellingen.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-stichtingen.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-verzekeringsmaatschappijen.xsd",
                "kvk-rpt-jaarverantwoording-2022-nlgaap-zorginstellingen.xsd",
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT18:
            ifrsNamespace = None
            jenvNamespace = "http://www.nltaxonomie.nl/nt18/jenv/20231213/dictionary/jenv-bw2-data"
            kvkINamespace = "http://www.nltaxonomie.nl/nt18/kvk/20231213/dictionary/kvk-data"
            nlTypesNamespace = "http://www.nltaxonomie.nl/nt18/sbr/20230301/dictionary/nl-types"
            rjNamespace = None
            entrypointRoot = "http://www.nltaxonomie.nl/nt18/kvk/20231213/entrypoints/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-rpt-jaarverantwoording-2023-ifrs-full.xsd",
                "kvk-rpt-jaarverantwoording-2023-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd",
                "kvk-rpt-jaarverantwoording-2023-ifrs-smes.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-banken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-beleggingsentiteiten.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-cooperaties.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-cv-vof.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-fondsenwervende-organisaties-klein.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-fondsenwervende-organisaties.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-groot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-groot.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-klein-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-klein-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-klein-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-klein.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-micro-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-micro.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-plus.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-organisaties-zonder-winststreven-klein.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-organisaties-zonder-winststreven.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-pensioenfondsen.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-premiepensioeninstellingen.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-stichtingen.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-verzekeringsmaatschappijen.xsd",
                "kvk-rpt-jaarverantwoording-2023-nlgaap-zorginstellingen.xsd",
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT19:
            ifrsNamespace = None
            jenvNamespace = "http://www.nltaxonomie.nl/nt19/jenv/20241211/dictionary/jenv-bw2-data"
            kvkINamespace = "http://www.nltaxonomie.nl/nt19/kvk/20241211/dictionary/kvk-data"
            nlTypesNamespace = "http://www.nltaxonomie.nl/nt19/sbr/20240301/dictionary/nl-types"
            rjNamespace = None
            entrypointRoot = "http://www.nltaxonomie.nl/nt19/kvk/20241211/entrypoints/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-rpt-jaarverantwoording-2024-nlgaap-banken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-beleggingsentiteiten.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-cooperaties.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-cv-vof.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-fondsenwervende-organisaties-klein.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-fondsenwervende-organisaties.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-groot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-groot.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-klein-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-klein-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-klein-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-klein.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-micro-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-micro.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-plus.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-organisaties-zonder-winststreven-klein.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-organisaties-zonder-winststreven.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-pensioenfondsen.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-premiepensioeninstellingen.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-stichtingen.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-verzekeringsmaatschappijen.xsd",
                "kvk-rpt-jaarverantwoording-2024-nlgaap-zorginstellingen.xsd",
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT20:
            ifrsNamespace = None
            jenvNamespace = "http://www.nltaxonomie.nl/nt20/jenv/20251210/dictionary/jenv-bw2-data"
            kvkINamespace = "http://www.nltaxonomie.nl/nt20/kvk/20251210/dictionary/kvk-data"
            nlTypesNamespace = "http://www.nltaxonomie.nl/nt20/sbr/20250301/dictionary/nl-types"
            rjNamespace = None
            entrypointRoot = "http://www.nltaxonomie.nl/nt20/kvk/20251210/entrypoints/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-rpt-jaarverantwoording-2025-nlgaap-banken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-beleggingsentiteiten.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-cooperaties.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-cv-vof.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-fondsenwervende-organisaties-klein.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-fondsenwervende-organisaties.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-groot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-groot.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-klein-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-klein-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-klein-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-klein.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-micro-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-micro.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-middelgroot-plus.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-middelgroot-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-middelgroot-verticaal-publicatiestukken.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-middelgroot-verticaal.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-middelgroot.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-organisaties-zonder-winststreven-klein.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-organisaties-zonder-winststreven.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-pensioenfondsen.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-premiepensioeninstellingen.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-stichtingen.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-verzekeringsmaatschappijen.xsd",
                "kvk-rpt-jaarverantwoording-2025-nlgaap-zorginstellingen.xsd",
            ]}
        elif (
            disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2024
            or
            disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2025
            and not any(ns.startswith("https://www.nltaxonomie.nl/kvk/2025-12-31/") for ns in validateXbrl.modelXbrl.namespaceDocs.keys())
        ):
            ifrsNamespace = "https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full"
            jenvNamespace = "https://www.nltaxonomie.nl/bw2-titel9/2024-12-31/bw2-titel9-cor"
            kvkINamespace = "https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-cor"
            nlTypesNamespace = None
            rjNamespace = "https://www.nltaxonomie.nl/rj/2024-12-31/rj-cor"
            entrypointRoot = "https://www.nltaxonomie.nl/kvk/2024-12-31/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-annual-report-ifrs-ext.xsd",
                "kvk-annual-report-nlgaap-ext.xsd",
            ]}
        elif (
            disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2024_GAAP_OTHER
            or
            disclosureSystem in (
                DISCLOSURE_SYSTEM_NL_INLINE_2025_GAAP_OTHER,
                DISCLOSURE_SYSTEM_NL_INLINE_MULTI_TARGET,
            ) and not any(ns.startswith("https://www.nltaxonomie.nl/kvk/2025-12-31/") for ns in validateXbrl.modelXbrl.namespaceDocs.keys())
        ):
            ifrsNamespace = "https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full"
            jenvNamespace = "https://www.nltaxonomie.nl/bw2-titel9/2024-12-31/bw2-titel9-cor"
            kvkINamespace = "https://www.nltaxonomie.nl/kvk/2024-12-31/kvk-cor"
            nlTypesNamespace = None
            rjNamespace = "https://www.nltaxonomie.nl/rj/2024-12-31/rj-cor"
            entrypointRoot = "https://www.nltaxonomie.nl/kvk/2024-12-31/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-annual-report-other-gaap.xsd",
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2025:
            ifrsNamespace = "https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full"
            jenvNamespace = "https://www.nltaxonomie.nl/bw2-titel9/2025-12-31/bw2-titel9-cor"
            kvkINamespace = "https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-cor"
            nlTypesNamespace = None
            rjNamespace = "https://www.nltaxonomie.nl/rj/2025-12-31/rj-cor"

            entrypointRoot = "https://www.nltaxonomie.nl/kvk/2025-12-31/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-annual-report-ifrs-ext.xsd",
                "kvk-annual-report-nlgaap-ext.xsd",
            ]}
        elif disclosureSystem in (
            DISCLOSURE_SYSTEM_NL_INLINE_2025_GAAP_OTHER,
            DISCLOSURE_SYSTEM_NL_INLINE_MULTI_TARGET,
        ):
            ifrsNamespace = "https://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full"
            jenvNamespace = "https://www.nltaxonomie.nl/bw2-titel9/2025-12-31/bw2-titel9-cor"
            kvkINamespace = "https://www.nltaxonomie.nl/kvk/2025-12-31/kvk-cor"
            nlTypesNamespace = None
            rjNamespace = "https://www.nltaxonomie.nl/rj/2025-12-31/rj-cor"
            entrypointRoot = "https://www.nltaxonomie.nl/kvk/2025-12-31/"
            entrypoints = {entrypointRoot + e for e in [
                "kvk-annual-report-other.xsd",
            ]}
        else:
            raise ValueError(f"Invalid NL disclosure system: {disclosureSystem}")
        if disclosureSystem in ALL_NL_INLINE_DISCLOSURE_SYSTEMS:
            assert rjNamespace
            namespaces = {
                _BW2_TITEL9_PREFIX: jenvNamespace,
                _KVK_PREFIX: kvkINamespace,
                "rj": rjNamespace,
            }
            mandatoryFactQNames = frozenset(
                QName.fromParts(localName, namespaces[prefix], prefix) for prefix, localName in [
                    (_BW2_TITEL9_PREFIX, "ChamberOfCommerceRegistrationNumber"),
                    (_BW2_TITEL9_PREFIX, "LegalEntityName"),
                    (_BW2_TITEL9_PREFIX, "LegalEntityLegalForm"),
                    (_BW2_TITEL9_PREFIX, "LegalEntityRegisteredOffice"),
                    (_KVK_PREFIX, "LegalEntitySize"),
                    (_BW2_TITEL9_PREFIX, "FinancialReportingPeriodEndDate"),
                    (_BW2_TITEL9_PREFIX, "FinancialReportingPeriod"),
                    ("rj", "FinancialStatementsConsolidated"),
                    (_KVK_PREFIX, "AuditorsReportFinancialStatementsPresent"),
                    (_BW2_TITEL9_PREFIX, "DocumentAdoptionStatus"),

                    # conditionally mandatory
                    (_BW2_TITEL9_PREFIX, "DocumentAdoptionDate"),
                    (_KVK_PREFIX, "AnnualReportOfForeignGroupHeadForExemptionUnderArticle403"),
                    (_KVK_PREFIX, "AnnualReportOfForeignGroupHeadForExemptionUnderArticle408"),
                ]
            )
        else:
            mandatoryFactQNames = None
        permissibleMandatoryFactsRootAbstracts=frozenset([
            QName.fromParts("AnnualReportFilingInformationTitle", kvkINamespace),
        ]) if kvkINamespace else frozenset()
        return PluginValidationDataExtension(
            self.name,
            AnnualReportOfForeignGroupHeadForExemptionUnderArticle403Qn=QName.fromParts("AnnualReportOfForeignGroupHeadForExemptionUnderArticle403", kvkINamespace),
            AnnualReportOfForeignGroupHeadForExemptionUnderArticle408Qn=QName.fromParts("AnnualReportOfForeignGroupHeadForExemptionUnderArticle408", kvkINamespace),
            chamberOfCommerceRegistrationNumberQn=QName.fromParts("ChamberOfCommerceRegistrationNumber", jenvNamespace),
            consolidatedMemberQn=QName.fromParts("ConsolidatedMember", jenvNamespace),
            documentAdoptionDateQn=QName.fromParts("DocumentAdoptionDate", jenvNamespace),
            documentAdoptionStatusQn=QName.fromParts("DocumentAdoptionStatus", jenvNamespace),
            documentResubmissionUnsurmountableInaccuraciesQn=QName.fromParts("DocumentResubmissionDueToUnsurmountableInaccuracies", kvkINamespace),
            entrypointRoot=entrypointRoot,
            entrypoints=entrypoints,
            financialReportingPeriodQn=QName.fromParts("FinancialReportingPeriod", jenvNamespace),
            financialReportingPeriodCurrentStartDateQn=QName.fromParts("FinancialReportingPeriodCurrentStartDate", jenvNamespace),
            financialReportingPeriodCurrentEndDateQn=QName.fromParts("FinancialReportingPeriodCurrentEndDate", jenvNamespace),
            financialReportingPeriodPreviousStartDateQn=QName.fromParts("FinancialReportingPeriodPreviousStartDate", jenvNamespace),
            financialReportingPeriodPreviousEndDateQn=QName.fromParts("FinancialReportingPeriodPreviousEndDate", jenvNamespace),
            financialStatementsTypeAxisQn=QName.fromParts("FinancialStatementsTypeAxis", jenvNamespace),
            formattedExplanationItemTypeQn=QName.fromParts("formattedExplanationItemType", nlTypesNamespace) if nlTypesNamespace else None,
            ifrsConsolidatedAndSeparateFinancialStatementsAxisQn=QName.fromParts("ConsolidatedAndSeparateFinancialStatementsAxis", ifrsNamespace) if ifrsNamespace else None,
            ifrsConsolidatedMemberQn=QName.fromParts("ConsolidatedMember", ifrsNamespace) if ifrsNamespace else None,
            ifrsIdentifier = "https://xbrl.ifrs.org",
            ifrsSeparateMemberQn=QName.fromParts("SeparateMember", ifrsNamespace) if ifrsNamespace else None,
            mandatoryFactQNames=mandatoryFactQNames,
            nonDimensionalLineItemsQName=QName.fromParts("NonDimensionalLineItems", kvkINamespace) if kvkINamespace else None,
            permissibleGAAPRootAbstracts=permissibleMandatoryFactsRootAbstracts | frozenset([
                QName.fromParts("BalanceSheetTitle", jenvNamespace),
                QName.fromParts("IncomeStatementTitle", jenvNamespace),
                QName.fromParts("StatementOfComprehensiveIncomeTitle", jenvNamespace),
                QName.fromParts("EquityStatementOfChangesTitle", jenvNamespace),
                QName.fromParts("CashFlowStatementTitle", rjNamespace),
            ]) if jenvNamespace and rjNamespace else frozenset(),
            permissibleIFRSRootAbstracts=permissibleMandatoryFactsRootAbstracts | frozenset([
                QName.fromParts("StatementOfFinancialPositionAbstract", ifrsNamespace),
                QName.fromParts("IncomeStatementAbstract", ifrsNamespace),
                QName.fromParts("StatementOfComprehensiveIncomeAbstract", ifrsNamespace),
                QName.fromParts("StatementOfCashFlowsAbstract", ifrsNamespace),
                QName.fromParts("StatementOfChangesInEquityAbstract", ifrsNamespace),
            ]) if ifrsNamespace else frozenset(),
            separateMemberQn=QName.fromParts("SeparateMember", jenvNamespace),
            textFormattingSchemaPath="sbr-text-formatting.xsd",
            textFormattingWrapper='<formattedText xmlns="http://www.nltaxonomie.nl/2017/xbrl/sbr-text-formatting">{}</formattedText>',
        )

    def modelXbrlLoadComplete(self, modelXbrl: ModelXbrl, *args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
        if self.disclosureSystemFromPluginSelected(modelXbrl):
            disclosureSystem = modelXbrl.modelManager.disclosureSystem.name
            if disclosureSystem in (DISCLOSURE_SYSTEM_NT16, DISCLOSURE_SYSTEM_NT17, DISCLOSURE_SYSTEM_NT18, DISCLOSURE_SYSTEM_NT19, DISCLOSURE_SYSTEM_NL_INLINE_2024):
                # Dutch taxonomies prior to 2025 incorrectly used hypercube linkrole for roots instead of dimension linkrole.
                paramQName = QName.fromParts("tlbDimRelsUseHcRoleForDomainRoots")
                modelXbrl.modelManager.formulaOptions.parameterValues[paramQName] = (None, "true")
        return None
