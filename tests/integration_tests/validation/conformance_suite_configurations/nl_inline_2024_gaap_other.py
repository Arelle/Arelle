from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

ZIP_PATH = Path('conformance-suite-2024-sbr-domein-handelsregister.zip')
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / 'conformance-suite-2024-sbr-domein-handelsregister',
            entry_point=Path('index.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/2025-04/conformance-suite-2024-sbr-domein-handelsregister.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NL-INLINE-2024'],
    ],
    base_taxonomy_validation='none',
    disclosure_system='NL-INLINE-2024-GAAP-OTHER',
    expected_additional_testcase_errors={f"*tests/{s}": val for s, val in {
        'G5-1-3_1/index.xml:TC1_valid': {
            'noInlineXbrlTags': 1,
        },
        'G5-1-3_1/index.xml:TC2_invalid': {
            'noInlineXbrlTags': 1,
        },
        'G5-1-3_2/index.xml:TC1_valid': {
            'noInlineXbrlTags': 1,
        },
        'G5-1-3_2/index.xml:TC2_invalid': {
            'documentNameDoesNotFollowNamingConvention': 1,
            'noInlineXbrlTags': 1,
            'requiredEntryPointOtherGaapNotReferenced': 1,
        },
    }.items()},
    expected_failure_ids=frozenset(f"tests/{s}" for s in [
        # Conformance Suite Errors
        'G3-3-1_2/index.xml:TC3_invalid',  # Expects an error code with a preceding double quote. G3-3-1_3 expects the same code without the typo.
        'G3-4-1_1/index.xml:TC2_invalid',  # Produces: [err:XPTY0004] Variable set Het entity identifier scheme dat bij dit feit hoort MOET het standaard KVK identifier scheme zijn
        'G3-4-1_2/index.xml:TC2_invalid',  # Expects fractionElementUsed”.  Note the double quote at the end.
        'G3-4-2_1/index.xml:TC2_invalid',  # Produces 'EFM.6.03.11' and 'NL.NL-KVK.3.4.2.1.htmlOrXmlBaseUsed'
        'RTS_Annex_IV_Par_2_G3-1-1_1/index.xml:TC2_invalid',  # Expects NonIdenticalIdentifier instead of nonIdenticalIdentifier (note the cap N)


        # Wont Run
        'G3-1-2_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-1-2_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-1-2_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-1-2_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-1-2_2/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-1-3_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-1-3_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-1-3_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-1-3_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-2-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-2-1_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-2-3_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-2-3_1/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-2-3_1/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-2-3_1/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'G3-2-4_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-2-4_2/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-2-4_2/index.xml:TC3_valid',  # Tested in NL-INLINE-2024
        'G3-2-4_2/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC3_valid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC5_invalid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC6_invalid',  # Tested in NL-INLINE-2024
        'G3-2-7_1/index.xml:TC7_invalid',  # Tested in NL-INLINE-2024
        'G3-3-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-3-1_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-3-1_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-3-1_2/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-3-1_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-3-1_3/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-4-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-1_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-1_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-1_3/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-4-1_4/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-1_4/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-4-1_5/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-1_5/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-4-2_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-4-2_1/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_1/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_1/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_1/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_3/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_4/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_4/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_5/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-1_5/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-1_5/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-5-2_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-2_1/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'G3-5-2_1/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'G3-5-2_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-2_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-2_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-2_3/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-3_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-3_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-5-4_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-5-4_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-6-2_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-6-2_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-6-3_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-6-3_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-6-3_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-6-3_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-6-3_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-6-3_3/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G3-7-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G3-7-1_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'G6-1-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'G6-1-1_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024

        'G4-1-1_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC5_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC6_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_1/index.xml:TC7_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-1_2/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-2_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-2_1/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-2_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-2_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-2_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC5_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC6_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-1-5_2/index.xml:TC7_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-0_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-0_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-0_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-0_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-1_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-1_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-2_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-2_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-3_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-2-3_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-1_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-1_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-1_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-1_1/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-2_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-3-2_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-1_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-1_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_3/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_3/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_4/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-2_4/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-3_2/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-4_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-4_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-5_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-5_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-5_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-5_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-5_2/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-6_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-6_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'G4-4-6_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS

        'RTS_Annex_II_Par_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_III_Par_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_III_Par_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_III_Par_1/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_11_G4-2-2_1/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC3_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_12_G3-2-4_1/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_14_G3-5-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_14_G3-5-1_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_1_G3-1-4_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_1_G3-1-4_1/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_1_G3-1-4_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_1_G3-1-4_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_2_G3-1-1_1/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_2_G3-1-1_2/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_2_G3-1-1_2/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_4_1/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_1/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_2/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_2/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_3/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_3/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_3/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_3/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_4_3/index.xml:TC5_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_5/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_5/index.xml:TC2_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_5/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_6/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_6/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_6/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_6/index.xml:TC4_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_8_G4-4-5/index.xml:TC3_invalid',  # Tested in NL-INLINE-2024
        'RTS_Annex_IV_Par_9_Par_10/index.xml:TC1_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_9_Par_10/index.xml:TC2_valid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Annex_IV_Par_9_Par_10/index.xml:TC3_invalid',  # Must be run with different disclosure system for GAAP/IFRS
        'RTS_Art_3/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Art_3/index.xml:TC2_valid',  # Tested in NL-INLINE-2024
        'RTS_Art_3/index.xml:TC3_valid',  # Tested in NL-INLINE-2024
        'RTS_Art_3/index.xml:TC4_invalid',  # Tested in NL-INLINE-2024
        'RTS_Art_6_a/index.xml:TC1_valid',  # Tested in NL-INLINE-2024
        'RTS_Art_6_a/index.xml:TC2_invalid',  # Tested in NL-INLINE-2024
    ]),
    info_url='https://www.sbr-nl.nl/sbr-domeinen/handelsregister/uitbreiding-elektronische-deponering-handelsregister',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/NL'}),
    shards=8,
    test_case_result_options='match-all',
)
