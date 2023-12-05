from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
        '--httpsRedirectCache',
    ],
    expected_failure_ids=frozenset(f'oim-conformance-2023-04-19/{s}' for s in [
        '600-xml/index-xbrl-xml.xml:V-05',
        '600-xml/index-xbrl-xml.xml:V-06',
    ]),
    file='oim-conformance-2023-04-19/oim-index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-open-information-model-open-information-model.html',
    local_filepath='oim-conformance-2023-04-19.zip',
    membership_url='https://www.xbrl.org/join',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'loadFromOIM'}),
)
