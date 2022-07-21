import os.path
from unittest.mock import patch

from arelle.CntlrCmdLine import parseAndRun
from arelle.WebCache import WebCache

# from https://specifications.xbrl.org/work-product-index-registries-lrr-1.0.html
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/lrr-conf-pwd-2005-06-21.zip'

ARGS = [
    '--file', os.path.join(CONFORMANCE_SUITE, 'lrr', 'conf', 'index.xml'),
    '--testcaseResultsCaptureWarnings',
    '--validate',

    '--csvTestReport', 'lrr-report.csv',
    '--logFile', 'lrr-log.txt',
]

if __name__ == "__main__":
    print('Running Link Role Registry tests...')
    oldNormalizeUrl = WebCache.normalizeUrl

    def normalizeUrl(self, url, base=None):
        bad = 'file:///c:/temp/conf/'
        if url.startswith(bad):
            return url.replace(bad, f'{CONFORMANCE_SUITE}/')
        return oldNormalizeUrl(self, url, base)
    with patch('arelle.WebCache.WebCache.normalizeUrl', normalizeUrl):
        parseAndRun(ARGS)
