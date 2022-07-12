from mock import Mock
import sys
from arelle import PluginManager
from arelle.Cntlr import Cntlr

def test_plugin_manager_init_first_pass():
    """
    Test that pluginConfig is correctly setup during init on fresh pass
    """
    cntlr = Mock(pluginDir='some_dir')
    PluginManager.init(cntlr, loadPluginConfig=False)
    assert len(PluginManager.pluginConfig) == 2
    assert 'modules' in PluginManager.pluginConfig
    assert isinstance(PluginManager.pluginConfig.get('modules'), dict)
    assert len(PluginManager.pluginConfig.get('modules')) == 0
    assert 'classes' in PluginManager.pluginConfig
    assert isinstance(PluginManager.pluginConfig.get('classes'), dict)
    assert len(PluginManager.pluginConfig.get('classes')) == 0
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    assert PluginManager._cntlr == cntlr


def test_plugin_manager_init_config_already_exists():
    """
    Test that pluginConfig is correctly setup during init on a second pass
    """
    cntlr = Mock(pluginDir='some_dir')
    PluginManager.init(cntlr, loadPluginConfig=False)
    PluginManager.close()
    PluginManager.init(cntlr, loadPluginConfig=False)
    assert len(PluginManager.pluginConfig) == 2
    assert 'modules' in PluginManager.pluginConfig
    assert isinstance(PluginManager.pluginConfig.get('modules'), dict)
    assert len(PluginManager.pluginConfig.get('modules')) == 0
    assert 'classes' in PluginManager.pluginConfig
    assert isinstance(PluginManager.pluginConfig.get('classes'), dict)
    assert len(PluginManager.pluginConfig.get('classes')) == 0
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    assert PluginManager._cntlr == cntlr


def test_plugin_manager_close():
    """
    Test that pluginConfig, modulePluginInfos and pluginMethodsForClasses are cleared when close is called
    """
    cntlr = Mock(pluginDir='some_dir')
    PluginManager.init(cntlr, loadPluginConfig=False)
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    PluginManager.modulePluginInfos['module'] = 'plugin_info'
    PluginManager.pluginMethodsForClasses['class'] = 'plugin_method'
    PluginManager.close()
    assert len(PluginManager.pluginConfig) == 0
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    assert PluginManager._cntlr == cntlr


def test_plugin_manager_reset():
    """
    Test that modulePluginInfos and pluginMethodsForClasses are cleared when close is called, pluginConfig remains unchanged
    """
    cntlr = Mock(pluginDir='some_dir')
    PluginManager.init(cntlr, loadPluginConfig=False)
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    PluginManager.modulePluginInfos['module'] = 'plugin_info'
    PluginManager.pluginMethodsForClasses['class'] = 'plugin_method'
    PluginManager.reset()
    assert len(PluginManager.pluginConfig) == 2
    assert len(PluginManager.modulePluginInfos) == 0
    assert len(PluginManager.pluginMethodsForClasses) == 0
    assert PluginManager._cntlr == cntlr

def test_function_loadModule():
    """Test helper function loadModule."""

    class Controller(Cntlr):  # type: ignore
        """Controller."""

        pluginDir = "tests/unit_tests/arelle"

        def __init__(self) -> None:
            """Init controller with logging."""
            super().__init__(logFileName="logToPrint")

    cntlr = Controller()
    PluginManager.init(cntlr, loadPluginConfig=False)

    PluginManager.loadModule(
        moduleInfo={
            "name": "Mock name",
            "moduleURL": "functionsMath",
        }
    )

    all_modules_list = [m.__name__ for m in sys.modules.values() if m]
    assert "functionsMath" in all_modules_list

    assert True
