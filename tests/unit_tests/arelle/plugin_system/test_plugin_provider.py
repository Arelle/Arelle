from unittest.mock import Mock

from arelle.plugin_system.plugin_provider import PluginProvider

_MODULE_INFO = {
    "name": "test-plugin",
    "aliases": [
        "Test Plugin"
    ],
    "author": "Test Author",
    "version": "0.0.1",
    "description": "Test plugin.",
    "entryPoint": {
        "module": "m",
        "name": "n",
        "version": "v",
    },
    "license": "Apache-2",
    "classMethods": [
        "DisclosureSystem.Types",
        "DisclosureSystem.ConfigURL",
    ],
    "moduleImports": [
        "module",
    ],
    "moduleURL": "plugin/test",
    "path": "./test_plugin/__init__.py",
    "status": "enabled",
    "fileDate": "2026-03-16T16:02:29 UTC",
    "importURLs": [
        "./imported-plugin",
    ],
    "imports": [
        {
            "name": "imported-plugin",
        }
    ],
    "isImported": True,
}

def test_parse_module_info_empty():
    """
    Test that pluginConfig is correctly setup during init on fresh pass
    """
    plugin_provider = PluginProvider(Mock())
    plugin = plugin_provider._parse_module_info({})
    assert len(plugin.aliases) == 0
    assert len(plugin.author) == 0
    assert len(plugin.description) == 0
    assert len(plugin.entry_point) == 0
    assert len(plugin.file_date) == 0
    assert len(plugin.hook_names) == 0
    assert len(plugin.import_urls) == 0
    assert len(plugin.imports) == 0
    assert plugin.is_imported == False
    assert len(plugin.license) == 0
    assert len(plugin.module_imports) == 0
    assert len(plugin.module_url) == 0
    assert len(plugin.name) == 0
    assert len(plugin.path) == 0
    assert len(plugin.status) == 0
    assert len(plugin.version) == 0

def test_parse_module_info_full():
    """
    Test that pluginConfig is correctly setup during init on fresh pass
    """
    plugin_provider = PluginProvider(Mock())
    plugin = plugin_provider._parse_module_info(_MODULE_INFO)
    assert plugin.aliases == {"Test Plugin"}
    assert plugin.author == "Test Author"
    assert plugin.description == "Test plugin."
    assert isinstance(plugin.entry_point, dict)
    assert plugin.file_date == "2026-03-16T16:02:29 UTC"
    assert plugin.hook_names == {"DisclosureSystem.Types", "DisclosureSystem.ConfigURL"}
    assert plugin.import_urls == {"./imported-plugin"}
    assert len(plugin.imports) == 1
    assert plugin.imports[0].name == "imported-plugin"
    assert plugin.is_imported == True
    assert plugin.license == "Apache-2"
    assert plugin.module_imports == {"module"}
    assert plugin.module_url == "plugin/test"
    assert plugin.name == "test-plugin"
    assert plugin.path == "./test_plugin/__init__.py"
    assert plugin.status == "enabled"
    assert plugin.version == "0.0.1"
