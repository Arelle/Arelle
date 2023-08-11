from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

TIMING = {f'esef_conformance_suite_2021/esef_conformance_suite_2021/tests/inline_xbrl/{k}': v for k, v in {
    'RTS_Annex_III_Par_3_G3-1-3/index.xml': 4.901,
    'RTS_Art_6_a/index.xml': 6.769,
    'G2-5-4_2/index.xml': 7.269,
    'RTS_Annex_IV_Par_14_G2-5-1/index.xml': 7.325,
    'RTS_Annex_IV_Par_6/index.xml': 7.347,
    'RTS_Annex_IV_Par_4_1/index.xml': 7.356,
    'RTS_Annex_II_Par_1_RTS_Annex_IV_par_7/index.xml': 7.37,
    'G2-5-3/index.xml': 7.388,
    'G2-4-2_2/index.xml': 7.564,
    'G2-5-4_1/index.xml': 7.766,
    'G2-5-4_3/index.xml': 7.796,
    'G2-4-1_2/index.xml': 7.832,
    'G3-2-5/index.xml': 7.84,
    'G3-5-1/index.xml': 7.865,
    'RTS_Annex_IV_Par_4_2/index.xml': 7.881,
    'G2-4-2_1/index.xml': 7.961,
    'G3-2-1/index.xml': 7.973,
    'G3-4-2_1/index.xml': 8.012,
    'RTS_Annex_II_Par_2/index.xml': 8.048,
    'RTS_Annex_IV_Par_1_G2-1-4/index.xml': 8.21,
    'G2-7-1_1/index.xml': 8.273,
    'G2-7-1_2/index.xml': 8.288,
    'G3-4-4/index.xml': 8.315,
    'G3-2-2/index.xml': 8.366,
    'G2-6-2/index.xml': 8.368,
    'G3-4-2_2/index.xml': 8.397,
    'G3-4-5_2/index.xml': 8.44,
    'G3-4-5_1/index.xml': 8.491,
    'G2-4-1_3/index.xml': 8.516,
    'G3-2-3/index.xml': 8.751,
    'G3-4-7/index.xml': 8.782,
    'G3-4-2_3/index.xml': 8.977,
    'RTS_Annex_IV_Par_8/index.xml': 9.929,
    'G2-5-1_3/index.xml': 10.567,
    'G3-4-3_2/index.xml': 11.164,
    'RTS_Annex_IV_Par_2_G2-1-1/index.xml': 11.229,
    'G3-4-3_1/index.xml': 11.231,
    'G2-6-1_2/index.xml': 11.548,
    'RTS_Annex_IV_Par_11_G3-2-2/index.xml': 11.728,
    'G3-4-2_4/index.xml': 11.803,
    'RTS_Annex_III_Par_1/index.xml': 12.161,
    'RTS_Annex_II_Par_1/index.xml': 12.197,
    'G2-6-1_1/index.xml': 12.314,
    'RTS_Art_3/index.xml': 12.818,
    'G3-1-1_2/index.xml': 13.467,
    'G2-2-1/index.xml': 13.522,
    'G2-1-3_1/index.xml': 13.528,
    'G2-1-3_2/index.xml': 13.635,
    'G2-2-2/index.xml': 13.687,
    'G2-3-1_2/index.xml': 13.766,
    'RTS_Annex_IV_Par_12_G2-2-4/index.xml': 14.174,
    'G2-5-1_2/index.xml': 15.168,
    'G2-5-2/index.xml': 15.286,
    'G2-5-1_1/index.xml': 15.782,
    'RTS_Annex_IV_Par_5_G3-4-6/index.xml': 15.947,
    'RTS_Annex_IV_Par_4_G1-1-1_G3-4-5/index.xml': 17.069,
    'G2-4-1_1/index.xml': 21.138,
    'G2-1-2/index.xml': 21.157,
    'RTS_Annex_IV_Par_9_Par_10_G1-4-1_G1-4-2_G3-3-1_G3-3-2/index.xml': 23.101,
    'G2-3-1_1/index.xml': 23.223,
    'G2-3-1_3/index.xml': 24.996,
    'G3-1-2/index.xml': 25.644,
    'G3-1-1_1/index.xml': 26.85,
    'G2-2-3/index.xml': 28.098,
    'G3-1-5/index.xml': 30.875,
}.items()}

config = ConformanceSuiteConfig(
    approximate_relative_timing=TIMING,
    args=[
        '--disclosureSystem', 'esef',
        '--formula', 'run',
    ],
    file='esef_conformance_suite_2021/esef_conformance_suite_2021/index_inline_xbrl.xml',
    info_url='https://www.esma.europa.eu/document/conformance-suite-2021',
    local_filepath='esef_conformance_suite_2021.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/ESEF'}),
    public_download_url='https://www.esma.europa.eu/sites/default/files/library/esef_conformance_suite_2021.zip',
    shards=5,
)