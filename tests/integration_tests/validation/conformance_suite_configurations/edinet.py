from collections import defaultdict
from pathlib import PurePath, Path

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

VALID_EXPECTED_ERRORS = {
    "valid/index.xml:valid01": {
        "EDINET.EC2002W": 1,
        "EDINET.EC8027W": 2,
    },
    "valid/index.xml:valid02": {
        "EDINET.EC2002W": 1,
        "EDINET.EC8027W": 2,
    },
    "valid/index.xml:valid03": {
        "EDINET.EC2002W": 1,
        "EDINET.EC5700W.GFM.1.8.4": 2,
        "EDINET.EC8027W": 1,
    },
    "valid/index.xml:valid04": {
        "EDINET.EC2002W": 2,
        "EDINET.EC2005E": 1,
    },
    "valid/index.xml:valid05": {
        "EDINET.EC2002W": 1,
    },
    "valid/index.xml:valid10": {
        "EDINET.EC2002W": 2,
    },
    "valid/index.xml:valid11": {
        "EDINET.EC2002W": 3,
    },
    "valid/index.xml:valid12": {
        "EDINET.EC2002W": 1,
    },
    "valid/index.xml:valid20": {
        "EDINET.EC2002W": 1,
        "EDINET.EC8027W": 2,
    },
    "valid/index.xml:valid21": {
        "EDINET.EC2002W": 3,
    },
    "valid/index.xml:valid22": {
        "EDINET.EC2002W": 3,
    },
}

INVALID_TESTCASE_PARENTS = {
    "EC1057E/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5002E/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5613W/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.13/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.10.14/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.1.7/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.10/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.14/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.22/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.26/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.27/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.3/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.4/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.5/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.7/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.8/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.2.9/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.1/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.10/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.13/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.16/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.17/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.19/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.20/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.21/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.22/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.23/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.25/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.26/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.28/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.29/index.xml:invalid01": "valid/index.xml:valid04",
    "EC5700W.GFM.1.3.30/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.31/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.3.8/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.10/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.6/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.7/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.7/index.xml:invalid02": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.8/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.5.8/index.xml:invalid02": "valid/index.xml:valid05",
    "EC5700W.GFM.1.6.1/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.6.2/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.6.5/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.1/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.2/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.3/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.4/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.5/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.7.6/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.8.1/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.8.10/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.8.11/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.8.3/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.9.1/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5700W.GFM.1.10.3/index.xml:invalid01": "valid/index.xml:valid05",
    "EC5806E/index.xml:invalid01": "valid/index.xml:valid09",
    "EC8013W/index.xml:invalid01": "valid/index.xml:valid05",
    "EC8024E/index.xml:invalid01": "valid/index.xml:valid03",
    "EC8033W/index.xml:invalid01": "valid/index.xml:valid22",
    "EC8054W/index.xml:invalid01": "valid/index.xml:valid05",
    "EC8057W/index.xml:invalid01": "valid/index.xml:valid04",
    "EC8058W/index.xml:invalid01": "valid/index.xml:valid03",
    "EC8062W/index.xml:invalid01": "valid/index.xml:valid03",
    "EC8075W/index.xml:invalid01": "valid/index.xml:valid02",
    "EC8076W/index.xml:invalid01": "valid/index.xml:valid05",
}

ADDITIONAL_INVALID_ERRORS = {
    # EDINET.EC5700W.GFM.1.1.3: valid05.zip (and testcases built from it) references
    # non-existent and non-standard "http://www.xbrl.org/2003/xbrl-instance-2003-09-30.xsd".
    # EDINET.EC8027W: Some of our "valid" documents define presentation and/or definition
    # links with multiple root elements. Keeping these out of the conformance suite
    # until we are more confident in our interpretation of the EDINET rule.
    "EC5700W.GFM.1.2.13/index.xml:invalid01": {
        "EDINET.EC5700W.GFM.1.1.3": 1,
    },
    "EC5700W.GFM.1.7.3/index.xml:invalid01": {
        "EDINET.EC5700W.GFM.1.7.5": 1,
    },
    "EC5700W.GFM.1.8.4/index.xml:invalid01": {
        # Modified version of valid03
        "EDINET.EC2002W": 1,
    },
    "EC5806E/index.xml:invalid01": {
        # Instance duplicated means table of contents are included twice.
        "EDINET.EC2005E": 2,
        "EDINET.EC3002E": 2,
    },
}

EXPECTED_ADDITIONAL_TESTCASE_ERRORS = defaultdict(lambda: defaultdict(int))
# Apply expected errors to valid testcases.
for test_id, errors in VALID_EXPECTED_ERRORS.items():
    for k, v in errors.items():
        EXPECTED_ADDITIONAL_TESTCASE_ERRORS[test_id][k] += v
# Apply expected errors to invalid testcases based on their valid parent.
for invalid_id, valid_id in INVALID_TESTCASE_PARENTS.items():
    for k, v in VALID_EXPECTED_ERRORS.get(valid_id, {}).items():
        EXPECTED_ADDITIONAL_TESTCASE_ERRORS[invalid_id][k] += v
# Apply additional expected errors to invalid testcases.
for test_id, errors in ADDITIONAL_INVALID_ERRORS.items():
    for k, v in errors.items():
        EXPECTED_ADDITIONAL_TESTCASE_ERRORS[test_id][k] += v


config = ConformanceSuiteConfig(
    args=[
        '--baseTaxonomyValidation', 'none',
        '--disclosureSystem', 'EDINET',
        '--testcaseResultsCaptureWarnings',
    ],
    assets=[
        ConformanceSuiteAssetConfig.local_conformance_suite(
            Path('edinet'),
            entry_point=Path('index.xml'),
        ),
    ],
    cache_version_id='cs2wODrDheJqDIm1kEU4Qwk8jwd7DfQu',
    expected_additional_testcase_errors={f"*{s}": val for s, val in EXPECTED_ADDITIONAL_TESTCASE_ERRORS.items()},
    expected_failure_ids=frozenset([]),
    info_url='https://disclosure2.edinet-fsa.go.jp/weee0020.aspx',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EDINET', 'inlineXbrlDocumentSet'}),
    shards=4,
    test_case_result_options='match-all',
)
