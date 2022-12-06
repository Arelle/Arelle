from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    file='60111 AssertionSeverity-2.0-Processing/60111 Assertion Severity 2.0 Processing.xml',
    info_url='https://specifications.xbrl.org/release-history-formula-1.0-formula-conf.html',
    local_filepath='60111 AssertionSeverity-2.0-Processing.zip',
    name=PurePath(__file__).stem,
)
