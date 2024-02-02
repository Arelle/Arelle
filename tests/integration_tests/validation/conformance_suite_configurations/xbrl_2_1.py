from pathlib import PurePath
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

TIMING = {f'XBRL-CONF-2014-12-10/Common/{k}': v for k, v in {
    '100-schema/102-item.xml': 0.062,
    '100-schema/103-type.xml': 0.006,
    '100-schema/104-tuple.xml': 0.162,
    '100-schema/105-balance.xml': 0.032,
    '100-schema/106-targetNamespace.xml': 0.023,
    '100-schema/107-DTSWithLinkbaseInSchema.xml': 0.006,
    '100-schema/114-lax-validation-testcase.xml': 0.029,
    '100-schema/115-ArcroleAndRoleRefs-testcase.xml': 0.028,
    '100-schema/155-TypeExtension.xml': 0.006,
    '100-schema/160-UsedOn.xml': 0.055,
    '100-schema/161-Appinfo.xml': 0.027,
    '200-linkbase/201-linkref.xml': 0.084,
    '200-linkbase/202-xlinkLocator.xml': 0.142,
    '200-linkbase/204-arcCycles.xml': 0.247,
    '200-linkbase/205-roleDeclared.xml': 0.088,
    '200-linkbase/206-arcDeclared.xml': 0.078,
    '200-linkbase/207-arcDeclaredCycles.xml': 0.145,
    '200-linkbase/208-balance.xml': 0.076,
    '200-linkbase/209-Arcs.xml': 0.040,
    '200-linkbase/210-relationshipEquivalence.xml': 0.044,
    '200-linkbase/211-Testcase-sEqualUsedOn.xml': 0.002,
    '200-linkbase/212-Testcase-linkbaseDocumentation.xml': 0.055,
    '200-linkbase/213-SummationItemArcEndpoints.xml': 0.021,
    '200-linkbase/214-lax-validation-testcase.xml': 0.029,
    '200-linkbase/215-ArcroleAndRoleRefs-testcase.xml': 0.071,
    '200-linkbase/220-NonStandardArcsAndTypes.xml': 0.058,
    '200-linkbase/230-CustomLinkbasesAndLocators.xml': 0.013,
    '200-linkbase/231-SyntacticallyEqualArcsThatAreNotEquivalentArcs.xml': 0.027,
    '200-linkbase/291-inferArcOverride.xml': 0.108,
    '200-linkbase/292-Embeddedlinkbaseinthexsd.xml': 0.037,
    '200-linkbase/293-UsedOn.xml': 0.043,
    '200-linkbase/preferredLabel.xml': 0.039,
    '300-instance/301-idScope.xml': 0.125,
    '300-instance/302-context.xml': 0.081,
    '300-instance/303-periodType.xml': 0.037,
    '300-instance/304-unitOfMeasure.xml': 0.225,
    '300-instance/305-decimalPrecision.xml': 0.063,
    '300-instance/306-required.xml': 0.024,
    '300-instance/307-schemaRef.xml': 0.020,
    '300-instance/308-ArcroleAndRoleRefs-testcase.xml': 0.014,
    '300-instance/314-lax-validation-testcase.xml': 0.042,
    '300-instance/320-CalculationBinding.xml': 0.326,
    '300-instance/321-internationalization.xml': 0.025,
    '300-instance/322-XmlXbrlInteraction.xml': 0.055,
    '300-instance/330-s-equal-testcase.xml': 0.155,
    '300-instance/331-equivalentRelationships-testcase.xml': 0.128,
    '300-instance/391-inferDecimalPrecision.xml': 20.331,
    '300-instance/392-inferEssenceAlias.xml': 0.170,
    '300-instance/395-inferNumericConsistency.xml': 0.063,
    '300-instance/397-Testcase-SummationItem.xml': 0.248,
    '300-instance/398-Testcase-Nillable.xml': 0.006,
    '400-misc/400-nestedElements.xml': 0.008,
    '400-misc/401-datatypes.xml': 0.014,
    'related-standards/xlink/arc-duplication/arc-duplication-testcase.xml': 0.029,
    'related-standards/xml-schema/uniqueParticleAttribution/uniqueParticleAttribution-testcase.xml': 0.033,
}.items()}

config = ConformanceSuiteConfig(
    approximate_relative_timing=TIMING,
    args=[
        '--formula', 'run',
        '--calcPrecision',
    ],
    expected_failure_ids=frozenset(f'XBRL-CONF-2014-12-10/Common/{s}' for s in [
        # 202.02b in the absence of source/target constraints, an empty href doesn't pose a problem
        # 202-02b-HrefResolutionCounterExample-custom.xml Expected: valid, Actual: arelle:hrefWarning
        '200-linkbase/202-xlinkLocator.xml:V-02b',
        # Tests that a decimals 0 value 0 is not treated as precision 0 (invalid) but as numeric zero.
        # In the prior approach where decimals 0 value 0 converted to precision 0 value 0, this would have been invalid.
        # 320-30-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
        '300-instance/320-CalculationBinding.xml:V-30',
        # Edge case tests that decimal rounding with is performed.
        # 320-31-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
        '300-instance/320-CalculationBinding.xml:V-31',
        # Checks that .5 rounds half to nearest even sum.
        # 320-32-BindCalculationInferDecimals-instance.xbrl Expected: invalid, Actual: valid
        '300-instance/320-CalculationBinding.xml:V-32',
        # Checks that .5 rounds half to nearest even regardless whether a processor uses float sum.
        # 320-34-BindCalculationInferDecimals-instance.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
        '300-instance/320-CalculationBinding.xml:V-34',
        # 397-28-PrecisionDifferentScales.xbrl Expected: valid, Actual: xbrl.5.2.5.2:calcInconsistency
        '300-instance/397-Testcase-SummationItem.xml:V-28',
    ]),
    file='XBRL-CONF-2014-12-10/xbrl.xml',
    info_url='https://specifications.xbrl.org/work-product-index-group-base-spec-base-spec.html',
    local_filepath='XBRL-CONF-2014-12-10.zip',
    name=PurePath(__file__).stem,
    network_or_cache_required=False,
    public_download_url='https://www.xbrl.org/2014/XBRL-CONF-2014-12-10.zip',
    shards=3,
)
