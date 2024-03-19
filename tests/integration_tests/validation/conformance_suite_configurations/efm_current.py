from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    additional_plugins_by_prefix=[(f'conf/{t}', frozenset({'EdgarRenderer'})) for t in [
        '612-presentation-syntax/612-09-presented-units-order',
        '626-rendering-syntax',
    ]],
    args=[
        '--disclosureSystem', 'efm-pragmatic',
        '--formula', 'run',
    ],
    expected_failure_ids=frozenset(f'conf/{t}' for t in [
        '525-ix-syntax/efm/17-redaction/17-redaction-testcase.xml:_002gd',
        '525-ix-syntax/efm/17-redaction/17-redaction-testcase.xml:_003gd',
        '525-ix-syntax/efm/17-redaction/17-redaction-testcase.xml:_004gd',
        '605-instance-syntax/605-20-required-document-elts/605-20-man/605-20-man-testcase.xml:_381gd',
        '605-instance-syntax/605-20-required-document-elts/605-20-man/605-20-man-testcase.xml:_385gd',
        '622-only-supported-locations/622-01-all-supported-locations/622-01-all-supported-locations-testcase.xml:_024gd',
        '624-rendering/13-flow-through/gd/13-flow-through-gd-testcase.xml:_000gd',
    ]),
    cache_version_id='CViqzeIjNViN4sDmRI1agtkw_1cCHy7b',
    file='conf/testcases.xml',
    info_url='https://www.sec.gov/structureddata/osdinteractivedatatestsuite',
    local_filepath='efm-69d-240220.zip',
    name=PurePath(__file__).stem,
    plugins=frozenset({'validate/EFM', 'inlineXbrlDocumentSet'}),
    public_download_url='https://www.sec.gov/files/efm-69d-240220.zip',
    shards=40,
)
