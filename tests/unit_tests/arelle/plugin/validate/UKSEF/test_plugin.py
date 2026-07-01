"""
Unit tests for the UKSEF validation plugin.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestPluginInfo:
    """Tests for plugin registration and metadata."""

    def test_plugin_loads(self):
        from arelle.plugin.validate.UKSEF import __pluginInfo__
        assert __pluginInfo__["name"] == "Validate UKSEF"
        assert __pluginInfo__["version"] == "0.0.1"

    def test_plugin_has_required_hooks(self):
        from arelle.plugin.validate.UKSEF import __pluginInfo__
        assert "DisclosureSystem.Types" in __pluginInfo__
        assert "DisclosureSystem.ConfigURL" in __pluginInfo__
        assert "Validate.XBRL.Finally" in __pluginInfo__

    def test_disclosure_system_types(self):
        from arelle.plugin.validate.UKSEF import disclosureSystemTypes
        types = disclosureSystemTypes()
        assert isinstance(types, tuple)
        assert len(types) >= 1
        # Each entry should be (validationType, disclosureSystemName)
        for entry in types:
            assert isinstance(entry, tuple)
            assert len(entry) == 2

    def test_disclosure_system_config_url(self):
        from arelle.plugin.validate.UKSEF import disclosureSystemConfigURL
        url = disclosureSystemConfigURL()
        assert isinstance(url, (str, Path))
        assert "config.xml" in str(url)

    def test_plugin_name_constant(self):
        from arelle.plugin.validate.UKSEF import PLUGIN_NAME
        assert PLUGIN_NAME == "Validate UKSEF"

    def test_validation_type_constant(self):
        from arelle.plugin.validate.UKSEF import DISCLOSURE_SYSTEM_VALIDATION_TYPE
        assert DISCLOSURE_SYSTEM_VALIDATION_TYPE == "UKSEF"


class TestDisclosureSystems:
    """Tests for disclosure system constants."""

    def test_uksef_2025_preview_value(self):
        from arelle.plugin.validate.UKSEF.DisclosureSystems import UKSEF_2025_PREVIEW
        assert UKSEF_2025_PREVIEW == "uksef-2025-preview"

    def test_all_disclosure_systems_contains_preview(self):
        from arelle.plugin.validate.UKSEF.DisclosureSystems import (
            ALL_DISCLOSURE_SYSTEMS,
            UKSEF_2025_PREVIEW,
        )
        assert UKSEF_2025_PREVIEW in ALL_DISCLOSURE_SYSTEMS

    def test_all_disclosure_systems_is_list(self):
        from arelle.plugin.validate.UKSEF.DisclosureSystems import ALL_DISCLOSURE_SYSTEMS
        assert isinstance(ALL_DISCLOSURE_SYSTEMS, list)
        assert len(ALL_DISCLOSURE_SYSTEMS) >= 1


class TestPluginValidationDataExtension:
    """Tests for the plugin data extension."""

    def test_data_extension_has_required_fields(self):
        from arelle.plugin.validate.UKSEF.PluginValidationDataExtension import (
            PluginValidationDataExtension,
        )
        import dataclasses
        field_names = [f.name for f in dataclasses.fields(PluginValidationDataExtension)]
        assert "isUksefFiling" in field_names
        assert "frcEntryPointPattern" in field_names
        assert "entityCurrentLegalOrRegisteredNameQn" in field_names
        assert "balanceSheetDateQn" in field_names
        assert "companyRegistrationNumberQn" in field_names

    def test_namespace_constants(self):
        from arelle.plugin.validate.UKSEF.PluginValidationDataExtension import (
            NAMESPACE_BUS,
            NAMESPACE_CORE,
            NAMESPACE_AUREP,
            NAMESPACE_DIREP,
        )
        assert "frc.org.uk" in NAMESPACE_BUS
        assert "frc.org.uk" in NAMESPACE_CORE
        assert "frc.org.uk" in NAMESPACE_AUREP
        assert "frc.org.uk" in NAMESPACE_DIREP


class TestValidationPluginExtension:
    """Tests for the validation plugin extension."""

    def test_extension_inherits_validation_plugin(self):
        from arelle.plugin.validate.UKSEF.ValidationPluginExtension import (
            ValidationPluginExtension,
        )
        from arelle.utils.validate.ValidationPlugin import ValidationPlugin
        assert issubclass(ValidationPluginExtension, ValidationPlugin)

    def test_frc_entry_point_pattern(self):
        from arelle.plugin.validate.UKSEF.ValidationPluginExtension import (
            FRC_ENTRY_POINT_PATTERN,
        )
        assert FRC_ENTRY_POINT_PATTERN.match("https://xbrl.frc.org.uk/fr/2025-01-01/core")
        assert FRC_ENTRY_POINT_PATTERN.match("http://xbrl.frc.org.uk/reports/2025-01-01/aurep")
        assert not FRC_ENTRY_POINT_PATTERN.match("https://example.com/taxonomy")


class TestRulesHelpers:
    """Tests for shared rule helper functions."""

    def test_is_uksef_filing_function_exists(self):
        from arelle.plugin.validate.UKSEF.rules import is_uksef_filing
        assert callable(is_uksef_filing)

    def test_get_ukfrs_ix_references_function_exists(self):
        from arelle.plugin.validate.UKSEF.rules import get_ukfrs_ix_references
        assert callable(get_ukfrs_ix_references)

    def test_get_default_ix_references_function_exists(self):
        from arelle.plugin.validate.UKSEF.rules import get_default_ix_references
        assert callable(get_default_ix_references)

    def test_get_inline_elements_by_target_function_exists(self):
        from arelle.plugin.validate.UKSEF.rules import get_inline_elements_by_target
        assert callable(get_inline_elements_by_target)


class TestRuleModules:
    """Tests that all rule modules load and have decorated functions."""

    def test_taxonomy_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import taxonomy
        assert hasattr(taxonomy, 'rule_ukfrc1')
        assert hasattr(taxonomy, 'rule_ukfrc2')

    def test_target_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import target
        assert hasattr(target, 'rule_ukfrc3')
        assert hasattr(target, 'rule_ukfrc4')
        assert hasattr(target, 'rule_ukfrc5')

    def test_entity_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import entity
        assert hasattr(entity, 'rule_ukfrc6')
        assert hasattr(entity, 'rule_ukfrc7')

    def test_context_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import context
        assert hasattr(context, 'rule_ukfrc8')

    def test_package_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import package
        assert hasattr(package, 'rule_ukfrc9')
        assert hasattr(package, 'rule_ukfrc19')

    def test_document_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import document
        assert hasattr(document, 'rule_ukfrc20')
        assert hasattr(document, 'rule_ukfrc21')

    def test_mandatory_module_loads(self):
        from arelle.plugin.validate.UKSEF.rules import mandatory
        assert hasattr(mandatory, 'rule_mandatory_facts')


class TestConfigXml:
    """Tests for the disclosure system config XML."""

    def test_config_xml_exists(self):
        config_path = Path(__file__).resolve().parents[6] / (
            "arelle/plugin/validate/UKSEF/resources/config.xml"
        )
        assert config_path.exists()

    def test_config_xml_parseable(self):
        from lxml import etree
        config_path = Path(__file__).resolve().parents[6] / (
            "arelle/plugin/validate/UKSEF/resources/config.xml"
        )
        tree = etree.parse(str(config_path))
        root = tree.getroot()
        assert root.tag == "DisclosureSystems"
        disclosure_systems = root.findall("DisclosureSystem")
        assert len(disclosure_systems) >= 1
        ds = disclosure_systems[0]
        assert "uksef-2025-preview" in ds.get("names", "")
        assert ds.get("validationType") == "UKSEF"
