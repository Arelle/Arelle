from __future__ import annotations

from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig
from tests.integration_tests.validation.conformance_suite_configurations.cipc_current import config as cipc_current
from tests.integration_tests.validation.conformance_suite_configurations.dba_current import config as dba_current
from tests.integration_tests.validation.conformance_suite_configurations.efm_current import config as efm_current
from tests.integration_tests.validation.conformance_suite_configurations.efm_reg_dqc import config as efm_reg_dqc
from tests.integration_tests.validation.conformance_suite_configurations.efm_reg_pragmatic import config as efm_reg_pragmatic
from tests.integration_tests.validation.conformance_suite_configurations.esef_ixbrl_2021 import config as esef_ixbrl_2021
from tests.integration_tests.validation.conformance_suite_configurations.esef_ixbrl_2022 import config as esef_ixbrl_2022
from tests.integration_tests.validation.conformance_suite_configurations.esef_ixbrl_2023 import config as esef_ixbrl_2023
from tests.integration_tests.validation.conformance_suite_configurations.esef_ixbrl_2024 import config as esef_ixbrl_2024
from tests.integration_tests.validation.conformance_suite_configurations.esef_xhtml_2021 import config as esef_xhtml_2021
from tests.integration_tests.validation.conformance_suite_configurations.esef_xhtml_2022 import config as esef_xhtml_2022
from tests.integration_tests.validation.conformance_suite_configurations.esef_xhtml_2023 import config as esef_xhtml_2023
from tests.integration_tests.validation.conformance_suite_configurations.esef_xhtml_2024 import config as esef_xhtml_2024
from tests.integration_tests.validation.conformance_suite_configurations.hmrc_current import config as hmrc_current
from tests.integration_tests.validation.conformance_suite_configurations.kvk_nt16 import config as kvk_nt16
from tests.integration_tests.validation.conformance_suite_configurations.kvk_nt17 import config as kvk_nt17
from tests.integration_tests.validation.conformance_suite_configurations.kvk_nt18 import config as kvk_nt18
from tests.integration_tests.validation.conformance_suite_configurations.kvk_nt19 import config as kvk_nt19
from tests.integration_tests.validation.conformance_suite_configurations.nl_nt16 import config as nl_nt16
from tests.integration_tests.validation.conformance_suite_configurations.nl_nt17 import config as nl_nt17
from tests.integration_tests.validation.conformance_suite_configurations.nl_nt18 import config as nl_nt18
from tests.integration_tests.validation.conformance_suite_configurations.nl_nt19 import config as nl_nt19
from tests.integration_tests.validation.conformance_suite_configurations.ros_current import config as ros_current
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_2_1 import config as xbrl_2_1
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_calculations_1_1 import config as xbrl_calculations_1_1
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_dimensions_1_0 import config as xbrl_dimensions_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_dtr_2024_01_31 import config as xbrl_dtr_2024_01_31
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_extensible_enumerations_1_0 import config as xbrl_extensible_enumerations_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_extensible_enumerations_2_0 import config as xbrl_extensible_enumerations_2_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_formula_1_0 import config as xbrl_formula_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_formula_1_0_assertion_severity_2_0 import config as xbrl_formula_1_0_assertion_severity_2_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_formula_1_0_function_registry import config as xbrl_formula_1_0_function_registry
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_ixbrl_1_1 import config as xbrl_ixbrl_1_1
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_link_role_registry_1_0 import config as xbrl_link_role_registry_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_oim_1_0 import config as xbrl_oim_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_report_packages_1_0 import config as xbrl_report_packages_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_table_linkbase_1_0 import config as xbrl_table_linkbase_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_taxonomy_packages_1_0 import config as xbrl_taxonomy_packages_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_transformation_registry_3 import config as xbrl_transformation_registry_3
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_transformation_registry_4 import config as xbrl_transformation_registry_4
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_transformation_registry_5 import config as xbrl_transformation_registry_5
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_utr_malformed_1_0 import configs as xbrl_utr_malformed_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_utr_registry_1_0 import config as xbrl_utr_registry_1_0
from tests.integration_tests.validation.conformance_suite_configurations.xbrl_utr_structure_1_0 import config as xbrl_utr_structure_1_0


ALL_CONFORMANCE_SUITE_CONFIGS: tuple[ConformanceSuiteConfig, ...] = (
    cipc_current,
    dba_current,
    efm_current,
    efm_reg_dqc,
    efm_reg_pragmatic,
    esef_ixbrl_2021,
    esef_ixbrl_2022,
    esef_ixbrl_2023,
    esef_ixbrl_2024,
    esef_xhtml_2021,
    esef_xhtml_2022,
    esef_xhtml_2023,
    esef_xhtml_2024,
    hmrc_current,
    kvk_nt16,
    kvk_nt17,
    kvk_nt18,
    kvk_nt19,
    nl_nt16,
    nl_nt17,
    nl_nt18,
    nl_nt19,
    ros_current,
    xbrl_2_1,
    xbrl_calculations_1_1,
    xbrl_dimensions_1_0,
    xbrl_dtr_2024_01_31,
    xbrl_extensible_enumerations_1_0,
    xbrl_extensible_enumerations_2_0,
    xbrl_formula_1_0,
    xbrl_formula_1_0_assertion_severity_2_0,
    xbrl_formula_1_0_function_registry,
    xbrl_ixbrl_1_1,
    xbrl_link_role_registry_1_0,
    xbrl_oim_1_0,
    xbrl_report_packages_1_0,
    xbrl_table_linkbase_1_0,
    xbrl_taxonomy_packages_1_0,
    xbrl_transformation_registry_3,
    xbrl_transformation_registry_4,
    xbrl_transformation_registry_5,
    *xbrl_utr_malformed_1_0,
    xbrl_utr_registry_1_0,
    xbrl_utr_structure_1_0,
)
CI_CONFORMANCE_SUITE_CONFIGS = tuple(c for c in ALL_CONFORMANCE_SUITE_CONFIGS if c.ci_enabled)
PUBLIC_CONFORMANCE_SUITE_CONFIGS = tuple(c for c in ALL_CONFORMANCE_SUITE_CONFIGS if c.entry_point_asset.public_download_url)
