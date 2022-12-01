import os
from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import (
    CONFORMANCE_SUITE_PATH_PREFIX, ConformanceSuiteConfig
)

ZIP_PATH = 'inlineXBRL-1.1-conformanceSuite-2020-04-08.zip'
# needs to be extracted because arelle can't load a taxonomy package ZIP from within a ZIP
EXTRACTED_PATH = ZIP_PATH.replace('.zip', '')
config = ConformanceSuiteConfig(
    args=[
        '--packages', os.path.join(CONFORMANCE_SUITE_PATH_PREFIX, EXTRACTED_PATH, 'inlineXBRL-1.1-conformanceSuite-2020-04-08/schemas/www.example.com.zip'),
        '--plugins', 'inlineXbrlDocumentSet.py|../examples/plugin/testcaseIxExpectedHtmlFixup.py',
    ],
    capture_warnings=False,
    extract_path=EXTRACTED_PATH,
    file='inlineXBRL-1.1-conformanceSuite-2020-04-08/index.xml',
    info_url='https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.1.html',
    local_filepath=ZIP_PATH,
    name=PurePath(__file__).stem,
    public_download_url='https://www.xbrl.org/2020/inlineXBRL-1.1-conformanceSuite-2020-04-08.zip',
)
