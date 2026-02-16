from pathlib import PurePath, Path

from arelle.testengine.ErrorLevel import ErrorLevel
from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource, CiConfig

ZIP_PATH = Path('conformance-suite-2024-sbr-domein-handelsregister_update-20251231.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'conformance-suite-2024-sbr-domein-handelsregister',
            entry_point=Path('index.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/2026-01/conformance-suite-2024-sbr-domein-handelsregister_update-20251231.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NL-INLINE-2024'],
    ],
    base_taxonomy_validation='none',
    ci_config=CiConfig(shard_count=2),
    custom_compare_patterns=[
        (r"^.*$", r"^NL.NL-KVK.*\.~$"),
    ],
    disclosure_system='NL-INLINE-2024',
    disclosure_system_by_prefix=[(f'tests/{s}', 'NL-INLINE-2024-GAAP-OTHER') for s in [
        'G5-1-3_1/index.xml',
        'G5-1-3_2/index.xml',
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
        'G3-2-7_1/index.xml:TC3_valid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC4_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC5_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC6_invalid': {
            'missingRelevantPlaceholder': 1,
        },
        'G3-2-7_1/index.xml:TC7_invalid': {
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
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G4-1-2_1/index.xml:TC3_invalid': {
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 11,
        },
        'G4-1-2_2/index.xml:TC2_invalid': {
            'anchoringRelationshipsForConceptsDefinedInElrContainingDimensionalRelationships': 1,  # Also fails 4.3.2.1
            'incorrectSummationItemArcroleUsed': 1,  # Also fails 4.4.1.1
            # Test imports https://www.nltaxonomie.nl/kvk/2024-03-31/kvk-annual-report-nlgaap-ext.xsd which is the draft taxonomy and not the final
            'requiredEntryPointNotImported': 1,
            'missingRelevantPlaceholder': 1,
            'usableConceptsNotAppliedByTaggedFacts': 1,  # Also fails 4.4.6.1
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 10,
        },
        'G4-2-0_1/index.xml:TC2_invalid': {
            'extensionConceptNoLabel': 1,
        },
        'G4-2-3_1/index.xml:TC2_invalid': {
            'extensionTaxonomyLineItemNotLinkedToAnyHypercube': 1,
            'extensionConceptNoLabel': 1,
            'missingRelevantPlaceholder': 1,
        },
        'G4-4-2_1/index.xml:TC2_invalid': {
            'closedNegativeHypercubeInDefinitionLinkbase': 1,  # Also fails 4.4.2.3
        },
        'G4-4-2_4/index.xml:TC2_invalid': {
            'usableConceptsNotIncludedInDefinitionLink': 1,
        },
        'G5-1-3_1/index.xml:TC1_valid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G5-1-3_1/index.xml:TC2_invalid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G5-1-3_2/index.xml:TC1_valid': {
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G5-1-3_2/index.xml:TC2_invalid': {
            'documentNameDoesNotFollowNamingConvention': 1,
            'requiredEntryPointOtherGaapNotReferenced': 1,
        },
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC2_valid': {
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC4_invalid': {
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
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
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'RTS_Annex_IV_Par_6/index.xml:TC4_invalid': {
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
    }.items()},
    expected_failure_ids=frozenset(f"tests/{s}" for s in [
        # Conformance Suite Errors
        'G3-4-1_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'G4-2-0_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'G4-4-1_1/index.xml:TC2_invalid',  # Expects IncorrectSummationItemArcroleUsed.  Note the capital first character.
        'G4-4-6_1/index.xml:TC2_invalid',  # Expects UsableConceptsNotAppliedByTaggedFacts.  Note the capital first character.
        'G4-4-6_1/index.xml:TC3_invalid',  # Expects UsableConceptsNotAppliedByTaggedFacts.  Note the capital first character.
        'RTS_Annex_III_Par_1/index.xml:TC3_invalid',  # Expects invalidInlineXbrl, but this is valid.
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC4_invalid',  # Expects inconsistentDuplicateNonnumericFactInInlineXbrlDocumentSet, should be inconsistentDuplicateNumericFactInInlineXbrlDocument.
        'RTS_Art_6_a/index.xml:TC2_invalid',  # Expects noInlineXbrlTags, but kvk-2024-12-31-nl.xhtml has a hidden nonNumeric fact.

        # Expects invalidInlineXbrl.  Instead, we depend on the underlying XML Schema and iXBRL validation errors.
        'RTS_Annex_III_Par_1/index.xml:TC2_invalid',

        # Not Implemented
        'RTS_Annex_II_Par_1/index.xml:TC3_invalid',
        'RTS_Annex_IV_Par_14_G3-5-1_1/index.xml:TC2_invalid',
    ]),
    expected_load_errors=frozenset([
        "Testcase document contained no testcases: */tests/G3-7-1_2/index.xml"
    ]),
    ignore_levels=frozenset({
        ErrorLevel.NOT_SATISFIED,
        ErrorLevel.OK,
        ErrorLevel.WARNING,
    }),
    info_url='https://www.sbr-nl.nl/sbr-domeinen/handelsregister/uitbreiding-elektronische-deponering-handelsregister',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    test_case_result_options='match-all',
)
