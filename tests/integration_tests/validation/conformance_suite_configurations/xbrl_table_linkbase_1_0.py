from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path("table-linkbase-conformance-2024-12-17.zip"),
            entry_point=Path("table-linkbase-conformance-2024-12-17/testcases-index.xml"),
            public_download_url="https://www.xbrl.org/2024/table-linkbase-conformance-2024-12-17.zip",
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_additional_testcase_errors={f"*/tests/{s}": val for s, val in {
        "0100-table/0140-table-breakdown-arc/0140-table-breakdown-arc-testcase.xml:v-01": {
            "xbrlte:tableBreakdownSourceError": 1,
        },
        "0100-table/0140-table-breakdown-arc/0140-table-breakdown-arc-testcase.xml:v-02": {
            "exception:ValueError": 1,
            "xbrlte:tableBreakdownTargetError": 1,
        },
        "0100-table/0141-breakdown-tree-arc/0141-breakdown-tree-arc-testcase.xml:v-01": {
            "xbrlte:breakdownTreeSourceError": 1,
        },
        "0100-table/0141-breakdown-tree-arc/0141-breakdown-tree-arc-testcase.xml:v-02": {
            "xbrlte:aspectClashBetweenBreakdowns": 2,
            "xbrlte:breakdownTreeTargetError": 1,
            "xbrlte:missingAspectValue": 2,
        },
        "0100-table/0142-definition-node-subtree-arc/0142-definition-node-subtree-arc-testcase.xml:v-01": {
            "xbrlte:definitionNodeSubtreeSourceError": 1,
        },
        "0100-table/0142-definition-node-subtree-arc/0142-definition-node-subtree-arc-testcase.xml:v-02": {
            "xbrlte:definitionNodeSubtreeTargetError": 1,
        },
        "0100-table/0142-definition-node-subtree-arc/0142-definition-node-subtree-arc-testcase.xml:v-03": {
            "xbrlte:prohibitedDefinitionNodeSubtreeSourceError": 1,
        },
        "0100-table/0142-definition-node-subtree-arc/0142-definition-node-subtree-arc-testcase.xml:v-04": {
            "xbrlte:prohibitedDefinitionNodeSubtreeSourceError": 1,
        },
        "0100-table/0143-aspect-node-filter-arc/0143-aspect-node-filter-arc-testcase.xml:v-01": {
            "xbrlte:aspectNodeFilterSourceError": 1,
        },
        "0100-table/0143-aspect-node-filter-arc/0143-aspect-node-filter-arc-testcase.xml:v-02": {
            "xbrlte:aspectNodeFilterTargetError": 1,
        },
        "0100-table/0144-table-filter-arc/0144-table-filter-arc-testcase.xml:v-01": {
            "xbrlte:tableFilterSourceError": 1,
        },
        "0100-table/0144-table-filter-arc/0144-table-filter-arc-testcase.xml:v-02": {
            "xbrlte:tableFilterTargetError": 1,
        },
        "0100-table/0145-table-parameter-arc/0145-table-parameter-arc-testcase.xml:v-01": {
            "xbrlte:tableParameterSourceError": 1,
        },
        "0100-table/0145-table-parameter-arc/0145-table-parameter-arc-testcase.xml:v-02": {
            "xbrlte:tableParameterTargetError": 1,
        },
        "6000-aspect-node/6650-aspect-node-typed-dimension-filter/6650-aspect-node-typed-dimension-filter-testcase.xml:v-04i": {
            "xfie:invalidTypedDimensionQName": 1,
        },
        "1000-rule-node/1300-rule-node-rule-sets/1300-rule-node-rule-sets-testcase.xml:v-05": {
            "xbrlfe:conflictingAspectRules": 1,
        },
        "3100-concept-relationship-node/3110-concept-relationship-node-relationship-source/3110-concept-relationship-node-relationship-source-testcase.xml:v-11": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3120-concept-relationship-node-linkrole/3120-concept-relationship-node-linkrole-testcase.xml:v-05": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3130-concept-relationship-node-arcrole/3130-concept-relationship-node-arcrole-testcase.xml:v-06": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3140-concept-relationship-node-linkname/3140-concept-relationship-node-linkname-testcase.xml:v-05": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3150-concept-relationship-node-arcname/3150-concept-relationship-node-arcname-testcase.xml:v-05": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3160-concept-relationship-node-formula-axis/3160-concept-relationship-node-formula-axis-testcase.xml:v-17": {
            "err:XPST0003": 1,
        },
        "3100-concept-relationship-node/3170-concept-relationship-node-generations/3170-concept-relationship-node-generations-testcase.xml:v-08": {
            "err:XPST0003": 1,
        },
        "3200-dimension-relationship-node/3210-dimension-relationship-node-relationship-source/3210-dimension-relationship-node-relationship-source-testcase.xml:v-11": {
            "err:XPST0003": 1,
        },
        "3200-dimension-relationship-node/3220-dimension-relationship-node-linkrole/3220-dimension-relationship-node-linkrole-testcase.xml:v-06": {
            "err:XPST0003": 1,
        },
        "3200-dimension-relationship-node/3240-dimension-relationship-node-formula-axis/3240-dimension-relationship-node-formula-axis-testcase.xml:v-08": {
            "err:XPST0003": 1,
        },
        "3200-dimension-relationship-node/3250-dimension-relationship-node-generations/3250-dimension-relationship-node-generations-testcase.xml:v-08": {
            "err:XPST0003": 1,
        },
        "3200-dimension-relationship-node/3210-dimension-relationship-node-relationship-source/3210-dimension-relationship-node-relationship-source-testcase.xml:v-04": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
        },
        "3200-dimension-relationship-node/3210-dimension-relationship-node-relationship-source/3210-dimension-relationship-node-relationship-source-testcase.xml:v-05": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
        },
        "3200-dimension-relationship-node/3210-dimension-relationship-node-relationship-source/3210-dimension-relationship-node-relationship-source-testcase.xml:v-06": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
        },
        "3200-dimension-relationship-node/3210-dimension-relationship-node-relationship-source/3210-dimension-relationship-node-relationship-source-testcase.xml:v-07": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
        },
        "3200-dimension-relationship-node/3230-dimension-relationship-node-dimension/3230-dimension-relationship-node-dimension-testcase.xml:v-01": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
            "xbrlte:invalidDimensionRelationshipSource": 1,
        },
        "3200-dimension-relationship-node/3230-dimension-relationship-node-dimension/3230-dimension-relationship-node-dimension-testcase.xml:v-02": {
            "xbrlte:closedDefinitionNodeZeroCardinality": 1,
            "xbrlte:invalidDimensionRelationshipSource": 1,
        },
        "0100-table/0144-table-filter-arc/0144-table-filter-arc-testcase.xml:v-03": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "0100-table/0144-table-filter-arc/0144-table-filter-arc-testcase.xml:v-04": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "0100-table/0170-parent-child-order/0170-parent-child-order-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "1000-rule-node/1060-rule-node-unit-rule/1060-rule-node-unit-rule-testcase.xml:v-01": {
            "arelle:tableModelConstraintsMismatch": 2,
        },
        "1000-rule-node/1060-rule-node-unit-rule/1060-rule-node-unit-rule-testcase.xml:v-01i": {
            "arelle:tableModelConstraintsMismatch": 2,
        },
        "1000-rule-node/1070-rule-node-occ-rule/1070-rule-node-occ-rule-testcase.xml:v-05": {
            "arelle:tableModelConstraintsMismatch": 1,
        },
        "1000-rule-node/1070-rule-node-occ-rule/1070-rule-node-occ-rule-testcase.xml:v-05i": {
            "arelle:tableModelConstraintsMismatch": 1,
        },
        "1000-rule-node/1070-rule-node-occ-rule/1070-rule-node-occ-rule-testcase.xml:v-06": {
            "arelle:tableModelConstraintsMismatch": 1,
        },
        "1000-rule-node/1070-rule-node-occ-rule/1070-rule-node-occ-rule-testcase.xml:v-06i": {
            "arelle:tableModelConstraintsMismatch": 1,
        },
        "1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-03": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-04": {
            "arelle:tableModelConstraintsMismatch": 2,
        },
        "1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-04i": {
            "arelle:tableModelConstraintsMismatch": 2,
        },
        "1000-rule-node/1200-merged-rule-node/1200-merged-rule-node-testcase.xml:v-10": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "1000-rule-node/1300-rule-node-rule-sets/1300-rule-node-rule-sets-testcase.xml:v-08": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "1000-rule-node/1300-rule-node-rule-sets/1300-rule-node-rule-sets-testcase.xml:v-08i": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6100-concept-aspect-node/6100-concept-aspect-node-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6200-period-aspect-node/6200-period-aspect-node-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6300-entity-identifier-aspect-node/6300-entity-identifier-aspect-node-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6400-unit-aspect-node/6400-unit-aspect-node-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6400-unit-aspect-node/6400-unit-aspect-node-testcase.xml:v-01i": {
            "arelle:tableModelConstraintsMismatch": 3,
        },
        "6000-aspect-node/6500-dimension-aspect-node/6500-dimension-aspect-node-testcase.xml:v-01": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6500-dimension-aspect-node/6500-dimension-aspect-node-testcase.xml:v-02": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6500-dimension-aspect-node/6500-dimension-aspect-node-testcase.xml:v-05": {
            "arelle:tableModelConstraintsMismatch": 1,
        },
        "6000-aspect-node/6500-dimension-aspect-node/6500-dimension-aspect-node-testcase.xml:v-06": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6640-aspect-node-explicit-dimension-filter/6640-aspect-node-explicit-dimension-filter-testcase.xml:v-03": {
            "arelle:tableModelChildCountMismatch": 1,
        },
        "6000-aspect-node/6650-aspect-node-typed-dimension-filter/6650-aspect-node-typed-dimension-filter-testcase.xml:v-04": {
            "arelle:tableModelChildCountMismatch": 1,
        },
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-table-linkbase-table-linkbase-1.0.html",
    name=PurePath(__file__).stem,
    shards=4,
    test_case_result_options="match-all",
)
