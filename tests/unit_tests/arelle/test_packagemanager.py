from unittest.mock import Mock

from arelle import PackageManager


def test_package_manager_init_first_pass():
    """
    Test that packagesConfig is correctly setup during init on fresh pass
    """
    cntlr = Mock()
    PackageManager.init(cntlr, loadPackagesConfig=False)
    assert len(PackageManager.packagesConfig) == 2
    assert 'packages' in PackageManager.packagesConfig
    assert isinstance(PackageManager.packagesConfig.get('packages'), list)
    assert len(PackageManager.packagesConfig.get('packages')) == 0
    assert 'remappings' in PackageManager.packagesConfig
    assert isinstance(PackageManager.packagesConfig.get('remappings'), dict)
    assert len(PackageManager.packagesConfig.get('remappings')) == 0
    assert PackageManager._cntlr == cntlr


def test_package_manager_init_config_already_exists():
    """
    Test that packagesConfig is correctly setup during init on a second pass
    """
    cntlr = Mock()
    PackageManager.init(cntlr, loadPackagesConfig=False)
    PackageManager.close()
    PackageManager.init(cntlr, loadPackagesConfig=False)
    assert len(PackageManager.packagesConfig) == 2
    assert 'packages' in PackageManager.packagesConfig
    assert isinstance(PackageManager.packagesConfig.get('packages'), list)
    assert len(PackageManager.packagesConfig.get('packages')) == 0
    assert 'remappings' in PackageManager.packagesConfig
    assert isinstance(PackageManager.packagesConfig.get('remappings'), dict)
    assert len(PackageManager.packagesConfig.get('remappings')) == 0
    assert PackageManager._cntlr == cntlr


def test_package_manager_close():
    """
    Test that packagesConfig and packagesMappings are cleared when close is called
    """
    cntlr = Mock()
    PackageManager.init(cntlr, loadPackagesConfig=False)
    assert len(PackageManager.packagesMappings) == 0
    PackageManager.packagesMappings['mapping'] = 'package'
    PackageManager.close()
    assert len(PackageManager.packagesConfig) == 0
    assert len(PackageManager.packagesMappings) == 0
    assert PackageManager._cntlr == cntlr


def test_package_manager_reset():
    """
    Test that packagesConfig and packagesMappings are cleared when reset is called
    """
    cntlr = Mock()
    PackageManager.init(cntlr, loadPackagesConfig=False)
    assert len(PackageManager.packagesMappings) == 0
    PackageManager.packagesMappings['mapping'] = 'package'
    PackageManager.reset()
    assert len(PackageManager.packagesConfig) == 0
    assert len(PackageManager.packagesMappings) == 0
    assert PackageManager._cntlr == cntlr
