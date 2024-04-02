from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('table-linkbase-conf-2015-08-12.zip'),
            entry_point=Path('table-linkbase-conf-2015-08-12/conf/testcases-index.xml'),
            public_download_url='https://www.xbrl.org/2015/table-linkbase-conf-2015-08-12.zip',
        ),
    ],
    expected_failure_ids=frozenset(f'table-linkbase-conf-2015-08-12/conf/tests/{s}' for s in [
        '0200-table-parameters/0200-table-parameters-testcase.xml:v-02i',
        '1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-10i',
        '1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-12i',
        '3100-concept-relationship-node/3120-concept-relationship-node-linkrole/3120-concept-relationship-node-linkrole-testcase.xml:v-02',
        '6000-aspect-node/6660-aspect-node-aspect-cover-filter/6660-aspect-node-aspect-cover-filter-testcase.xml:v-01',
    ]),
    info_url='https://specifications.xbrl.org/work-product-index-table-linkbase-table-linkbase-1.0.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    shards=4,
    test_case_result_options='match-any',
)
