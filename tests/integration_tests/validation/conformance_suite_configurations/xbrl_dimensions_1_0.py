from pathlib import PurePath, Path
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('xdt-conf-cr4-2009-10-06.zip'),
            entry_point=Path('xdt.xml'),
            public_download_url='https://www.xbrl.org/2009/xdt-conf-cr4-2009-10-06.zip',
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    args=[
        '--infoset',
    ],
    expected_failure_ids=frozenset([
        # The value of the xbrldt:targetRole attribute is valid
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-03',
        # An all hypercube has an msdos path in the targetRole attribute to locate the domain - dimension arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-08',
        # A dimension-domain relationship has an msdos path in targetRole attribute to locate the domain-member arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-09',
        # A domain-member relationship has an msdos path in targetRole attribute to locate the domain-member arc network
        # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
        '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-10',
    ]),
    info_url='https://specifications.xbrl.org/work-product-index-group-dimensions-dimensions.html',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    test_case_result_options='match-any',
)
