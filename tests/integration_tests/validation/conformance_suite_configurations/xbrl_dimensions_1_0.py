from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

config = ConformanceSuiteConfig(
    args=[
        '--formula', 'run',
        '--infoset',
    ],
    expected_failure_ids=frozenset([
        # The value of the xbrldt:targetRole attribute is valid
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '001-Taxonomy/001-TestCase-Taxonomy.xml/V-03',
        # An all hypercube has an msdos path in the targetRole attribute to locate the domain - dimension arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '001-Taxonomy/001-TestCase-Taxonomy.xml/V-08',
        # A dimension-domain relationship has an msdos path in targetRole attribute to locate the domain-member arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '001-Taxonomy/001-TestCase-Taxonomy.xml/V-09',
        # A domain-member relationship has an msdos path in targetRole attribute to locate the domain-member arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '001-Taxonomy/001-TestCase-Taxonomy.xml/V-10',
    ]),
    file='xdt.xml',
    info_url='https://specifications.xbrl.org/work-product-index-group-dimensions-dimensions.html',
    local_filepath='xdt-conf-cr4-2009-10-06.zip',
    name=PurePath(__file__).stem,
    public_download_url='https://www.xbrl.org/2009/xdt-conf-cr4-2009-10-06.zip',
)
