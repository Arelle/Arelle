from pathlib import PurePath, Path

from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestcaseSet import TestcaseSet
from tests.integration_tests.validation.assets import ESEF_PACKAGES, NL_PACKAGES, NL_INLINE_2024_PACKAGES_WITHOUT_IFRS
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CiConfig
from tests.integration_tests.validation.preprocessing_util import swap_id

ZIP_PATH = Path('conformance-suite-2025-sbr-domein-handelsregister.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)


def _preprocessing_func(config: ConformanceSuiteConfig, testcase_set: TestcaseSet) -> TestcaseSet:
    id_swaps: dict[tuple[str, tuple[str, ...]], str] = {
        ('tests/G4-2-2_2/index.xml:TC3_invalid', ('TC4_invalid.xbri',)):  'tests/G4-2-2_2/index.xml:TC4_valid',
        ('tests/G5-1-3_2/index.xml:TC1_valid', ('TC2_valid.xbri',)):  'tests/G5-1-3_2/index.xml:TC2_valid',
    }
    testcases = [
        swap_id(testcase, id_swaps)
        for testcase in testcase_set.testcases
    ]
    assert not id_swaps, \
        f'Some ID replacements were not applied: {id_swaps}'
    return TestcaseSet(
        load_errors=testcase_set.load_errors,
        skipped_testcases=testcase_set.skipped_testcases,
        testcases=testcases,
    )


config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'conformance-suite-2025-sbr-domein-handelsregister',
            entry_point=Path('index.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/2026-01/conformance-suite-2025-sbr-domein-handelsregister.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_INLINE_2024_PACKAGES_WITHOUT_IFRS,
        *NL_PACKAGES['NL-INLINE-2025'],
        *ESEF_PACKAGES[2024],
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(shard_count=2),
    custom_compare_patterns=[
        (r"^.*$", r"^NL.NL-KVK.*\.~$"),
    ],
    disclosure_system='NL-INLINE-2025',
    disclosure_system_by_prefix=[
        (f'tests/{s}', 'NL-INLINE-2025-GAAP-OTHER-PREVIEW') for s in [
        'G5-1-3_1/index.xml',
        'G5-1-3_2/index.xml',
        'G7-1-4_1/index.xml',
        'G7-1-4_2/index.xml',
    ]] + [
        (f'tests/{s}', 'NL-INLINE-MULTI-TARGET') for s in [
        'G6-1-3_1/index.xml',
        'G6-1-3_2/index.xml',
        'G6-1-3_3/index.xml',
        'G6-1-3_4/index.xml',
    ]],
    expected_additional_testcase_errors={f"tests/{s}": val for s, val in {
        'G3-1-3_1/index.xml:TC2_invalid': {
            'scenarioNotUsedInExtensionTaxonomy': 1,  # Also fails 4.2.1.1
        },
        'G3-1-3_2/index.xml:TC2_invalid': {
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 1,
            'usableConceptsNotIncludedInDefinitionLink': 1,
        },
        'G3-2-7_1/index.xml:TC1_valid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC2_valid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC3_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC4_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC5_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC6_valid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC7_valid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-4-1_1/index.xml:TC2_invalid': {
            'err:XPTY0004': 1,
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 1,
            'NL.NL-KVK.3.2.8.1': 1,
            'usableConceptsNotAppliedByTaggedFacts': 1,
            'usableConceptsNotIncludedInDefinitionLink': 1,
        },
        'G3-5-2_3/index.xml:TC2_invalid': {
            'missingLabelForRoleInReportLanguage': 1,
        },
        'G3-6-3_1/index.xml:TC2_invalid': {
            # deconformancebvdeponeringsgegevens-2024-12-31-nl.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
        },
        'G3-6-3_2/index.xml:TC2_invalid': {
            # formulier-deponeren-kvk.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
        },
        'G3-6-3_3/index.xml:TC2_invalid': {
            # kvk()-2024-12-31-nl.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
        },
        'G3-7-1_1/index.xml:TC2_invalid': {
            'message:valueKvKIdentifier': 13,
            'nonIdenticalIdentifier': 1,
        },
        'G4-1-1_1/index.xml:TC3_invalid': {
            'extensionConceptNoLabel': 1,
        },
        'G4-1-1_1/index.xml:TC5_invalid': {
            'usableConceptsNotIncludedInPresentationLink': 1,
        },
        'G4-1-1_1/index.xml:TC7_invalid': {
            'usableConceptsNotIncludedInPresentationLink': 1,
        },
        'G4-1-2_1/index.xml:TC2_valid': {
            # filing_information-2024-12-31-en.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'G4-1-2_1/index.xml:TC3_invalid': {
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 11,
        },
        'G4-1-2_2/index.xml:TC3_invalid': {
            'anchoringRelationshipsForConceptsDefinedInElrContainingDimensionalRelationships': 1,
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 10,
            'incorrectSummationItemArcroleUsed': 1,
            'missingRelevantPlaceholder': 1,
            'requiredEntryPointNotImported': 1,
            'usableConceptsNotAppliedByTaggedFacts': 1,
        },
        'G4-2-0_1/index.xml:TC2_invalid': {
            'extensionConceptNoLabel': 1,
        },
        'G4-2-3_1/index.xml:TC2_invalid': {
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 1,
            'extensionConceptNoLabel': 1,
            'missingRelevantPlaceholder': 1,
        },
        'G4-3-1_1/index.xml:TC3_invalid': {
            'incompatibleDataTypeAnchoringRelationship': 1,
        },
        'G4-4-2_1/index.xml:TC2_invalid': {
            'closedNegativeHypercubeInDefinitionLinkbase': 1,  # Also fails 4.4.2.3
        },
        'G4-4-2_4/index.xml:TC2_invalid': {
            'usableConceptsNotIncludedInDefinitionLink': 1,
        },
        'G5-1-3_1/index.xml:TC1_valid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'G5-1-3_1/index.xml:TC2_invalid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'G5-1-3_2/index.xml:TC1_valid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'G5-1-3_2/index.xml:TC2_valid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G6-1-3_4/index.xml:TC1_valid': {
            'incorrectVersionEntryPointOtherReferenced': 1,
            'requiredEntryPointOtherNotReferenced': 1,
        },
        'G6-1-3_4/index.xml:TC2_invalid': {
            'incorrectVersionEntryPointOtherReferenced': 1,
            'requiredEntryPointOtherNotReferenced': 1,
        },
        'G7-1-4_1/index.xml:TC1_valid': {
            'arelle:nonIxdsDocument': 1,
        },
        'G7-1-4_2/index.xml:TC1_valid': {
            'arelle:nonIxdsDocument': 1,
        },
        'G7-1-4_2/index.xml:TC2_invalid': {
            'arelle:nonIxdsDocument': 1,
            'message:valueAnnualReportOfForeignGroupHeadForExemptionUnderArticle403': 1,
            'targetXBRLDocumentWithFormulaErrors': 1,
        },
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC2_valid': {
            # filing_information-2024-12-31-en.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC4_invalid': {
            # filing_information-2024-12-31-en.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'RTS_Annex_IV_Par_1_G3-1-4_1/index.xml:TC2_invalid': {
            'message:valueKvKIdentifier': 13,
            'nonIdenticalIdentifier': 1,
        },
        'RTS_Annex_IV_Par_1_G3-1-4_2/index.xml:TC2_invalid': {
            'message:valueKvKIdentifier': 13,
        },
        'RTS_Annex_IV_Par_2_G3-1-1_1/index.xml:TC2_invalid': {
            'message:valueKvKIdentifier': 13,
        },
        'RTS_Annex_IV_Par_2_G3-1-1_2/index.xml:TC2_invalid': {
            'message:lei-identifier-format': 105,
            'message:valueKvKIdentifierScheme': 105,
        },
        'RTS_Annex_IV_Par_4_3/index.xml:TC4_invalid': {
            'extensionTaxonomyWrongFilesStructure': 1,
        },
        'RTS_Annex_IV_Par_6/index.xml:TC2_valid': {
            # filing_information-2024-12-31-en.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'RTS_Annex_IV_Par_6/index.xml:TC4_invalid': {
            # filing_information-2024-12-31-en.html
            'kvkFilingDocumentNameDoesNotFollowNamingConvention': 1,
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 4,
        },
        'RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC2_invalid': {
            # "https://www.nltaxonomie.nl/bw2-titel9/2025-12-31/bw2-titel9-cor-ref.xml#bw2-titel9_BW2_2024-01-01_364_1_ref"
            'xbrl.3.5.4:hrefIdNotFound': 1,
            'xbrl.5.2.3.1:referenceLinkLocTarget': 1,
        },
        'RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC3_invalid': {
            'incompatibleDataTypeAnchoringRelationship': 1,
        },
        # New variation for 2025
        'RTS_Art_6_a/index.xml:TC2_valid': {
            'usableConceptsNotAppliedByTaggedFacts': 1,
        },
    }.items()},
    expected_failure_ids=frozenset(f"tests/{s}" for s in [
        # Conformance Suite Errors
        'G3-4-1_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'G3-6-3_5/index.xml:TC2_invalid',  # Expects kvkFilingDocumentNameDoesNotFollowNamingConvention, should be elementsReferencedInKvkFilingDocumentNotLimitedToMandatoryElements.
        'G4-2-0_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'G4-3-1_2/index.xml:TC1_valid',  # Expects valid, but incompatibleDataTypeAnchoringRelationship is appropriate for noDecimalsMonetaryItemType in different DTR versions.
        'G4-4-1_1/index.xml:TC2_invalid',  # Expects IncorrectSummationItemArcroleUsed.  Note the capital first character.
        'G4-4-6_1/index.xml:TC2_invalid',  # Expects UsableConceptsNotAppliedByTaggedFacts.  Note the capital first character.
        'G4-4-6_1/index.xml:TC3_invalid',  # Expects UsableConceptsNotAppliedByTaggedFacts.  Note the capital first character.
        'G5-1-3_2/index.xml:TC3_invalid',  # Expects incorrectVersionEntryPointOtherGaapReferenced, should be incorrectVersionEntryPointOtherReferenced.
        'RTS_Annex_III_Par_1/index.xml:TC3_invalid',  # Expects invalidInlineXbrl, but this is valid.
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC4_invalid',  # Expects inconsistentDuplicateNonnumericFactInInlineXbrlDocumentSet, should be inconsistentDuplicateNumericFactInInlineXbrlDocument.
        'RTS_Art_6_a/index.xml:TC3_invalid',  # Expects noInlineXbrlTags, but kvk-2025-12-31-nl.xhtml has a hidden nonNumeric fact.

        # Conformance Suite Uncertainty
        'G3-2-7_1/index.xml:TC3_invalid',  # Expects improperApplicationOfEscapeAttribute, but we tentatively assume they intended to match ESEF.

        # Not Implemented
        'G7-1-4_1/index.xml:TC2_invalid',
        'RTS_Annex_II_Par_1/index.xml:TC3_invalid',
        'RTS_Annex_IV_Par_14_G3-5-1_1/index.xml:TC2_invalid',

        # Not Implemented: NL-INLINE-MULTI-TARGET
        'G6-1-3_1/index.xml:TC1_valid',
        'G6-1-3_1/index.xml:TC2_invalid',
        'G6-1-3_2/index.xml:TC1_valid',
        'G6-1-3_2/index.xml:TC2_invalid',
        'G6-1-3_3/index.xml:TC1_valid',
        'G6-1-3_3/index.xml:TC2_invalid',

        # Expects invalidInlineXbrl.  Instead, we depend on the underlying XML Schema and iXBRL validation errors.
        'RTS_Annex_III_Par_1/index.xml:TC2_invalid',
    ]),
    expected_load_errors=frozenset([
        "Testcase document contained no testcases: */tests/G3-7-1_2/index.xml",
        "Testcase document contained no testcases: */tests/G7-2-1_1/index.xml",
        "Testcase document contained no testcases: */tests/G7-2-1_2/index.xml",
    ]),
    ignore_levels=frozenset({
        ErrorLevel.NOT_SATISFIED,
        ErrorLevel.OK,
        ErrorLevel.WARNING,
    }),
    info_url='https://www.sbr-nl.nl/sbr-domeinen/handelsregister/uitbreiding-elektronische-deponering-handelsregister',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    preprocessing_func=_preprocessing_func,
    test_case_result_options='match-all',
)
