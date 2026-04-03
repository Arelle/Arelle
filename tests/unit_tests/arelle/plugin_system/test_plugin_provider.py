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
    plugin_handle = plugin_provider._parse_module_info({})
    assert len(plugin_handle.aliases) == 0
    assert len(plugin_handle.author) == 0
    assert len(plugin_handle.description) == 0
    assert len(plugin_handle.entry_point) == 0
    assert len(plugin_handle.file_date) == 0
    assert len(plugin_handle.hook_names) == 0
    assert len(plugin_handle.import_urls) == 0
    assert len(plugin_handle.imports) == 0
    assert plugin_handle.is_imported == False
    assert len(plugin_handle.license) == 0
    assert len(plugin_handle.module_imports) == 0
    assert len(plugin_handle.module_url) == 0
    assert len(plugin_handle.name) == 0
    assert len(plugin_handle.path) == 0
    assert len(plugin_handle.status) == 0
    assert len(plugin_handle.version) == 0

def test_parse_module_info_full():
    """
    Test that pluginConfig is correctly setup during init on fresh pass
    """
    plugin_provider = PluginProvider(Mock())
    plugin_handle = plugin_provider._parse_module_info(_MODULE_INFO)
    assert plugin_handle.aliases == {"Test Plugin"}
    assert plugin_handle.author == "Test Author"
    assert plugin_handle.description == "Test plugin."
    assert isinstance(plugin_handle.entry_point, dict)
    assert plugin_handle.file_date == "2026-03-16T16:02:29 UTC"
    assert plugin_handle.hook_names == {"DisclosureSystem.Types", "DisclosureSystem.ConfigURL"}
    assert plugin_handle.import_urls == {"./imported-plugin"}
    assert len(plugin_handle.imports) == 1
    assert plugin_handle.imports[0].name == "imported-plugin"
    assert plugin_handle.is_imported == True
    assert plugin_handle.license == "Apache-2"
    assert plugin_handle.module_imports == {"module"}
    assert plugin_handle.module_url == "plugin/test"
    assert plugin_handle.name == "test-plugin"
    assert plugin_handle.path == "./test_plugin/__init__.py"
    assert plugin_handle.status == "enabled"
    assert plugin_handle.version == "0.0.1"
