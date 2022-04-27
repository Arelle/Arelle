import os
import zipfile

from arelle.CntlrCmdLine import parseAndRun

# from https://specifications.xbrl.org/work-product-index-registries-units-registry-1.0.html
REGISTRY_CONFORMANCE_SUITE = 'tests/resources/conformance_suites/utr/registry/utr-conf-cr-2013-05-17.zip/utr-conf-cr-2013-05-17/2013-05-17'
STRUCTURE_CONFORMANCE_SUITE_ZIP = 'tests/resources/conformance_suites/utr/structure/utr-structure-conf-cr-2013-11-18.zip'
STRUCTURE_CONFORMANCE_SUITE = os.path.join(STRUCTURE_CONFORMANCE_SUITE_ZIP, 'conf/utr-structure')

BASE_ARGS = [
    '--testcaseResultsCaptureWarnings',
    '--utr',
    '--validate',
]
REGISTRY_ARGS = BASE_ARGS + [
    '--file', os.path.join(REGISTRY_CONFORMANCE_SUITE, 'index.xml'),
    '--utrUrl', 'tests/resources/conformance_suites/utr/registry/utr.xml',

    '--csvTestReport', 'UTRunit-report.csv',
    '--logFile', 'UTRunit-log.txt',
]
STRUCTURE_ARGS = BASE_ARGS + [
    '--file', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'index.xml'),
    '--utrUrl', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'utr-for-structure-conformance-tests.xml'),

    '--csvTestReport', 'UTRstr-report.csv',
    '--logFile', 'UTRstr-log.txt',
]


if __name__ == "__main__":
    print('Running registry tests...')
    parseAndRun(REGISTRY_ARGS)

    print('Running structure tests...')
    parseAndRun(STRUCTURE_ARGS)

    print('Running malformed UTRs tests...')
    malformed_utr_files = []
    with zipfile.ZipFile(STRUCTURE_CONFORMANCE_SUITE_ZIP, 'r') as zipf:
        for f in zipfile.Path(zipf, 'conf/utr-structure/malformed-utrs/').iterdir():
            if f.is_file() and f.name.endswith('.xml'):
                malformed_utr_files.append((f.at, f.name))
    for path_in_zip, name in malformed_utr_files:
        basename = name.removesuffix('.xml')
        args = BASE_ARGS + [
            '--file', os.path.join(STRUCTURE_CONFORMANCE_SUITE, 'tests', '01-simple', 'simpleValid.xml'),
            '--utrUrl', os.path.join(STRUCTURE_CONFORMANCE_SUITE_ZIP, path_in_zip),

            '--csvTestReport', f'UTRstr-report-{basename}.csv',
            '--logFile', f'UTRstr-log-{basename}.txt',
        ]
        parseAndRun(args)
