import re
from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--check-formula-restricted-XPath',
        '--noValidateTestcaseSchema',
    ],
    file='formula/function-registry/registry-index.xml',
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    local_filepath='formula.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'formulaXPathChecker', 'functionsMath'}),
    strict_testcase_index=False,
    required_locale_by_ids={f'formula/function-registry/{t}': p for t, p in [
        ('xbrl/90701 xfi.format-number/90701 xfi.format-number testcase.xml:V-05', re.compile(r"^(en|English).*$")),
    ]},
)
