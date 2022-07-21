import os.path
import pytest
from unittest.mock import patch

from arelle.WebCache import WebCache

from tests.integration_tests.validation.validation_util import get_test_data

# from https://specifications.xbrl.org/work-product-index-registries-lrr-1.0.html
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/lrr-conf-pwd-2005-06-21.zip'

ARGS = [
    '--file', os.path.join(CONFORMANCE_SUITE, 'lrr', 'conf', 'index.xml'),
    '--keepOpen',
    '--testcaseResultsCaptureWarnings',
    '--validate',
]

if os.getenv('CONFORMANCE_SUITES_TEST_MODE') == 'OFFLINE':
    ARGS.extend(['--internetConnectivity', 'offline'])


oldNormalizeUrl = WebCache.normalizeUrl


def normalizeUrl(self, url, base=None):
    bad = 'file:///c:/temp/conf/'
    if url.startswith(bad):
        return url.replace(bad, f'{CONFORMANCE_SUITE}/')
    return oldNormalizeUrl(self, url, base)


with patch('arelle.WebCache.WebCache.normalizeUrl', normalizeUrl):
    TEST_DATA = get_test_data(ARGS)


@pytest.mark.parametrize("result", TEST_DATA)
def test_lrr_conformance_suite(result):
    assert result['status'] == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            result.get('expected'), result.get('actual')
        )
