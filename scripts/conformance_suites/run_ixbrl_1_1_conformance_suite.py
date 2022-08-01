import os.path
from shutil import unpack_archive

from arelle.CntlrCmdLine import parseAndRun

# from https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html
CONFORMANCE_SUITE_ZIP = 'tests/resources/conformance_suites/inlineXBRL-1.1-conformanceSuite-2020-04-08.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
CONFORMANCE_SUITE = 'tests/resources/conformance_suites/inlineXBRL-1.1-conformanceSuite-2020-04-08'

ARGS = [
    '--file', os.path.join(CONFORMANCE_SUITE, 'index.xml'),
    '--packages', os.path.join(CONFORMANCE_SUITE, 'schemas/www.example.com.zip'),
    '--plugins', 'inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py',
    '--validate',

    '--csvTestReport', 'Ix11-report.csv',
    '--logFile', 'Ix11-log.txt',
]


if __name__ == "__main__":
    print('Running Inline XBRL 1.1 tests...')
    if not os.path.exists(CONFORMANCE_SUITE):
        unpack_archive(CONFORMANCE_SUITE_ZIP, extract_dir=os.path.dirname(CONFORMANCE_SUITE))
    parseAndRun(ARGS)
