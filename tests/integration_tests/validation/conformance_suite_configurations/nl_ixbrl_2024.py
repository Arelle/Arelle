from pathlib import PurePath, Path

from tests.integration_tests.validation.assets import NL_PACKAGES
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig, ConformanceSuiteAssetConfig, AssetSource

config = ConformanceSuiteConfig(
    args=[
        '--disclosureSystem', 'INLINE-NT19',
        '--baseTaxonomyValidation', 'none',
    ],
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path('conformance-suite-2024-sbr-domein-handelsregister.zip'),
            entry_point=Path('conformance-suite-2024-sbr-domein-handelsregister/index.xml'),
            public_download_url='https://www.sbr-nl.nl/sites/default/files/2025-04/conformance-suite-2024-sbr-domein-handelsregister.zip',
            source=AssetSource.S3_PUBLIC,
        ),
        *NL_PACKAGES['NL-INLINE-2024'],
    ],
    # expected_failure_ids=frozenset([
    #     # The value of the xbrldt:targetRole attribute is valid
    #     # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    #     '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-03',
    #     # An all hypercube has an msdos path in the targetRole attribute to locate the domain - dimension arc network
    #     # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    #     '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-08',
    #     # A dimension-domain relationship has an msdos path in targetRole attribute to locate the domain-member arc network
    #     # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    #     '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-09',
    #     # A domain-member relationship has an msdos path in targetRole attribute to locate the domain-member arc network
    #     # Expected: sche:XmlSchemaError, Actual: xbrldte:TargetRoleNotResolvedError
    #     '000-Schema-invalid/001-Taxonomy/001-TestCase-Taxonomy.xml:V-10',
    # ]),
    info_url='https://www.sbr-nl.nl/sbr-domeinen/handelsregister/uitbreiding-elektronische-deponering-handelsregister',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    plugins=frozenset({'validate/NL'}),
    shards=4,
    test_case_result_options='match-any',
)
