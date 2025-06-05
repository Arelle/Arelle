"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelValue import qname
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .DisclosureSystems import (DISCLOSURE_SYSTEM_NT16, DISCLOSURE_SYSTEM_NT17, DISCLOSURE_SYSTEM_NT18,
                                DISCLOSURE_SYSTEM_NT19, DISCLOSURE_SYSTEM_NL_INLINE_2024,
                                DISCLOSURE_SYSTEM_NL_INLINE_2024_GAAP_OTHER)
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        disclosureSystem = validateXbrl.disclosureSystem.name
        if disclosureSystem == DISCLOSURE_SYSTEM_NT16:
            jenvNamespace = 'http://www.nltaxonomie.nl/nt16/jenv/20211208/dictionary/jenv-bw2-data'
            kvkINamespace = 'http://www.nltaxonomie.nl/nt16/kvk/20211208/dictionary/kvk-data'
            nlTypesNamespace = 'http://www.nltaxonomie.nl/nt16/sbr/20210301/dictionary/nl-types'
            entrypointRoot = 'http://www.nltaxonomie.nl/nt16/kvk/20211208/entrypoints/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-rpt-jaarverantwoording-2021-ifrs-full.xsd',
                'kvk-rpt-jaarverantwoording-2021-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd',
                'kvk-rpt-jaarverantwoording-2021-ifrs-smes.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-banken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-beleggingsentiteiten.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-cooperaties.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-cv-vof.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-fondsenwervende-organisaties-klein.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-fondsenwervende-organisaties.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-groot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-groot.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-klein-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-klein-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-klein-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-klein.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-micro-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-micro.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-middelgroot.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-organisaties-zonder-winststreven-klein.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-organisaties-zonder-winststreven.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-pensioenfondsen.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-premiepensioeninstellingen.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-stichtingen.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-verzekeringsmaatschappijen.xsd',
                'kvk-rpt-jaarverantwoording-2021-nlgaap-zorginstellingen.xsd',
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT17:
            jenvNamespace = 'http://www.nltaxonomie.nl/nt17/jenv/20221214/dictionary/jenv-bw2-data'
            kvkINamespace = 'http://www.nltaxonomie.nl/nt17/kvk/20221214/dictionary/kvk-data'
            nlTypesNamespace = 'http://www.nltaxonomie.nl/nt17/sbr/20220301/dictionary/nl-types'
            entrypointRoot = 'http://www.nltaxonomie.nl/nt17/kvk/20221214/entrypoints/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-rpt-jaarverantwoording-2022-ifrs-full.xsd',
                'kvk-rpt-jaarverantwoording-2022-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd',
                'kvk-rpt-jaarverantwoording-2022-ifrs-smes.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-banken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-beleggingsentiteiten.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-cooperaties.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-cv-vof.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-fondsenwervende-organisaties-klein.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-fondsenwervende-organisaties.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-groot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-groot.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-klein-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-klein-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-klein-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-klein.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-micro-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-micro.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-plus.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-middelgroot.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-organisaties-zonder-winststreven-klein.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-organisaties-zonder-winststreven.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-pensioenfondsen.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-premiepensioeninstellingen.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-stichtingen.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-verzekeringsmaatschappijen.xsd',
                'kvk-rpt-jaarverantwoording-2022-nlgaap-zorginstellingen.xsd',
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT18:
            jenvNamespace = 'http://www.nltaxonomie.nl/nt18/jenv/20231213/dictionary/jenv-bw2-data'
            kvkINamespace = 'http://www.nltaxonomie.nl/nt18/kvk/20231213/dictionary/kvk-data'
            nlTypesNamespace = 'http://www.nltaxonomie.nl/nt18/sbr/20230301/dictionary/nl-types'
            entrypointRoot = 'http://www.nltaxonomie.nl/nt18/kvk/20231213/entrypoints/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-rpt-jaarverantwoording-2023-ifrs-full.xsd',
                'kvk-rpt-jaarverantwoording-2023-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd',
                'kvk-rpt-jaarverantwoording-2023-ifrs-smes.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-banken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-beleggingsentiteiten.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-cooperaties.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-cv-vof.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-fondsenwervende-organisaties-klein.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-fondsenwervende-organisaties.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-groot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-groot.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-klein-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-klein-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-klein-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-klein.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-micro-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-micro.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-plus.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-middelgroot.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-organisaties-zonder-winststreven-klein.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-organisaties-zonder-winststreven.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-pensioenfondsen.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-premiepensioeninstellingen.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-stichtingen.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-verzekeringsmaatschappijen.xsd',
                'kvk-rpt-jaarverantwoording-2023-nlgaap-zorginstellingen.xsd',
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NT19:
            jenvNamespace = 'http://www.nltaxonomie.nl/nt19/jenv/20241211/dictionary/jenv-bw2-data'
            kvkINamespace = 'http://www.nltaxonomie.nl/nt19/kvk/20241211/dictionary/kvk-data'
            nlTypesNamespace = 'http://www.nltaxonomie.nl/nt19/sbr/20240301/dictionary/nl-types'
            entrypointRoot = 'http://www.nltaxonomie.nl/nt19/kvk/20241211/entrypoints/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-rpt-jaarverantwoording-2024-ifrs-full.xsd',
                'kvk-rpt-jaarverantwoording-2024-ifrs-geconsolideerd-nlgaap-enkelvoudig.xsd',
                'kvk-rpt-jaarverantwoording-2024-ifrs-smes.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-banken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-beleggingsentiteiten.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-cooperaties.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-cv-vof.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-fondsenwervende-organisaties-klein.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-fondsenwervende-organisaties.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-groot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-groot.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-klein-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-klein-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-klein-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-klein.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-micro-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-micro.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-plus.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-verticaal-publicatiestukken.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot-verticaal.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-middelgroot.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-organisaties-zonder-winststreven-klein.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-organisaties-zonder-winststreven.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-pensioenfondsen.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-premiepensioeninstellingen.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-stichtingen.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-toegelaten-instellingen-volkshuisvesting.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-verzekeringsmaatschappijen.xsd',
                'kvk-rpt-jaarverantwoording-2024-nlgaap-zorginstellingen.xsd',
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2024:
            jenvNamespace = 'https://www.nltaxonomie.nl/bw2-titel9/2024-12-31/bw2-titel9-cor'
            kvkINamespace = None
            nlTypesNamespace = None
            entrypointRoot = 'http://www.nltaxonomie.nl/kvk/2024-12-31/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-annual-report-ifrs-ext.xsd',
                'kvk-annual-report-nlgaap-ext.xsd',
            ]}
        elif disclosureSystem == DISCLOSURE_SYSTEM_NL_INLINE_2024_GAAP_OTHER:
            jenvNamespace = 'https://www.nltaxonomie.nl/bw2-titel9/2024-12-31/bw2-titel9-cor'
            kvkINamespace = None
            nlTypesNamespace = None
            entrypointRoot = 'http://www.nltaxonomie.nl/kvk/2024-12-31/'
            entrypoints = {entrypointRoot + e for e in [
                'kvk-annual-report-other-gaap.xsd',
            ]}
        else:
            raise ValueError(f'Invalid NL disclosure system: {disclosureSystem}')
        return PluginValidationDataExtension(
            self.name,
            chamberOfCommerceRegistrationNumberQn=qname(f'{{{jenvNamespace}}}ChamberOfCommerceRegistrationNumber'),
            documentAdoptionDateQn=qname(f'{{{jenvNamespace}}}DocumentAdoptionDate'),
            documentAdoptionStatusQn=qname(f'{{{jenvNamespace}}}DocumentAdoptionStatus'),
            documentResubmissionUnsurmountableInaccuraciesQn=qname(f'{{{kvkINamespace}}}DocumentResubmissionDueToUnsurmountableInaccuracies'),
            entrypointRoot=entrypointRoot,
            entrypoints=entrypoints,
            financialReportingPeriodQn=qname(f'{{{jenvNamespace}}}FinancialReportingPeriod'),
            financialReportingPeriodCurrentStartDateQn=qname(f'{{{jenvNamespace}}}FinancialReportingPeriodCurrentStartDate'),
            financialReportingPeriodCurrentEndDateQn=qname(f'{{{jenvNamespace}}}FinancialReportingPeriodCurrentEndDate'),
            financialReportingPeriodPreviousStartDateQn=qname(f'{{{jenvNamespace}}}FinancialReportingPeriodPreviousStartDate'),
            financialReportingPeriodPreviousEndDateQn=qname(f'{{{jenvNamespace}}}FinancialReportingPeriodPreviousEndDate'),
            formattedExplanationItemTypeQn=qname(f'{{{nlTypesNamespace}}}formattedExplanationItemType'),
            textFormattingSchemaPath='sbr-text-formatting.xsd',
            textFormattingWrapper='<formattedText xmlns="http://www.nltaxonomie.nl/2017/xbrl/sbr-text-formatting">{}</formattedText>',
        )

    def modelXbrlLoadComplete(self, modelXbrl: ModelXbrl, *args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
        if self.disclosureSystemFromPluginSelected(modelXbrl):
            disclosureSystem = modelXbrl.modelManager.disclosureSystem.name
            if disclosureSystem in (DISCLOSURE_SYSTEM_NT16, DISCLOSURE_SYSTEM_NT17, DISCLOSURE_SYSTEM_NT18, DISCLOSURE_SYSTEM_NT19, DISCLOSURE_SYSTEM_NL_INLINE_2024):
                # Dutch taxonomies prior to 2025 incorrectly used hypercube linkrole for roots instead of dimension linkrole.
                paramQName = qname('tlbDimRelsUseHcRoleForDomainRoots', noPrefixIsNoNamespace=True)
                modelXbrl.modelManager.formulaOptions.parameterValues[paramQName] = (None, "true")
        return None
