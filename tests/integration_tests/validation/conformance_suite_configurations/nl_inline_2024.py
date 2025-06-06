from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'NL-INLINE-2024',
        '--baseTaxonomyValidation', 'none',
        '--testcaseResultsCaptureWarnings',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('conformance-suite-2024-sbr-domein-handelsregister.zip'),
            entry_point=Path('conformance-suite-2024-sbr-domein-handelsregister/index.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/2025-04/conformance-suite-2024-sbr-domein-handelsregister.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NL-INLINE-2024'],
    ],
    expected_additional_testcase_errors={f"conformance-suite-2024-sbr-domein-handelsregister/tests/{s}": val for s, val in {
        'G3-1-3_1/index.xml:TC2_invalid': {
            'scenarioNotUsedInExtensionTaxonomy': 1,  # Also fails 4.2.1.1
        },
        'G3-5-3_1/index.xml:TC2_invalid': {
            'arelle:ixdsTargetNotDefined': 1,
            'extensionTaxonomyWrongFilesStructure': 1,
            # This test is looking at the usage of the target attribute and does not import the correct taxonomy urls
            'requiredEntryPointNotImported': 1,
            'incorrectKvkTaxonomyVersionUsed': 1,
        },
        'G3-6-3_3/index.xml:TC2_invalid': {
            # Testcase expects only 3.6.3.3, but has a filename that has invalid characters (3.6.3.3)
            # AND {base} with > 20 characters (3.6.3.1)
            'baseComponentInDocumentNameExceedsTwentyCharacters': 1,
        },
        'G3-7-1_1/index.xml:TC2_invalid': {
            'message:valueKvKIdentifier': 13,
            'nonIdenticalIdentifier': 1,
        },
        'G4-1-2_1/index.xml:TC2_valid': {
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
        'G4-1-2_2/index.xml:TC2_invalid': {
            'incorrectSummationItemArcroleUsed': 1,  # Also fails 4.4.1.1
            # Test imports https://www.nltaxonomie.nl/kvk/2024-03-31/kvk-annual-report-nlgaap-ext.xsd which is the draft taxonomy and not the final
            'requiredEntryPointNotImported': 1,
        },
        'G4-4-2_1/index.xml:TC2_invalid': {
            'closedNegativeHypercubeInDefinitionLinkbase': 1,  # Also fails 4.4.2.3
        },
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC2_valid': {
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
        'RTS_Annex_IV_Par_2_G3-1-1_2/index.xml:TC2_invalid': {
            'message:lei-identifier-format': 105,
            'message:valueKvKIdentifierScheme': 105,
        },
        'RTS_Annex_IV_Par_6/index.xml:TC2_valid': {
            'undefinedLanguageForTextFact': 1,
            'taggedTextFactOnlyInLanguagesOtherThanLanguageOfAReport': 5,
        },
    }.items()},
    expected_failure_ids=frozenset([
        # Conformance Suite Errors
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-3-1_2/index.xml:TC3_invalid',  # Expects an error code with a preceding double quote. G3-3-1_3 expects the same code without the typo.
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-4-1_1/index.xml:TC2_invalid',  # Produces: [err:XPTY0004] Variable set Het entity identifier scheme dat bij dit feit hoort MOET het standaard KVK identifier scheme zijn
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-4-1_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-4-2_1/index.xml:TC2_invalid',  # Produces 'EFM.6.03.11' and 'NL.NL-KVK.3.4.2.1.htmlOrXmlBaseUsed'
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-2-0_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-4-1_1/index.xml:TC2_invalid',  # Expects IncorrectSummationItemArcroleUsed.  Note the capital first character.
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_2_G3-1-1_1/index.xml:TC2_invalid',  # Expects NonIdenticalIdentifier instead of nonIdenticalIdentifier (note the cap N)


        # Not Implemented
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_1/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_1/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_2/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_3/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_4/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_5/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-5-1_5/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G3-6-2_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-3-1_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-3-1_1/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-3-1_1/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-3-2_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-4-2_4/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-4-5_2/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G4-4-5_2/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G5-1-3_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP Other
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G5-1-3_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP Other
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G5-1-3_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP Other
        'conformance-suite-2024-sbr-domein-handelsregister/tests/G5-1-3_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP Other
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_II_Par_1/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_III_Par_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_III_Par_1/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_14_G3-5-1_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_4_1/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_4_2/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_4_3/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_4_3/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_4_3/index.xml:TC5_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_5/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_5/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_6/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC2_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Annex_IV_Par_9_Par_10/index.xml:TC3_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Art_3/index.xml:TC4_invalid',
        'conformance-suite-2024-sbr-domein-handelsregister/tests/RTS_Art_6_a/index.xml:TC2_invalid',
    ]),
    info_url='https://www.sbr-nl.nl/sbr-domeinen/handelsregister/uitbreiding-elektronische-deponering-handelsregister',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/NL'}),
    shards=8,
    test_case_result_options='match-all',
)
