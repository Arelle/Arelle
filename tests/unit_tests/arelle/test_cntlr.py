from unittest.mock import patch

import pytest

from arelle import Cntlr, Version


@pytest.fixture(autouse=True)
def resolve_version_before_mocks() -> None:
    # Finding the version may run git, whose pipes would be opened through the mocked io.open.
    assert Version.__version__


@patch("os.makedirs")
@patch("io.open")
@patch("os.path.exists")
@patch("arelle.Cntlr.Cntlr.setUiLanguage")
@patch("arelle.ModelManager.ModelManager.setLocale")
def test_cntlr_cache_enabled(_, mock_codes, mock_exists, mock_open, mock_makedirs):
    mock_codes.return_value = ["en-US", "en_US", "en"]
    mock_exists.return_value = True
    cntlr = Cntlr.Cntlr(uiLang=None)
    assert mock_makedirs.call_count == 1
    assert mock_open.call_count == 3
    cntlr.saveConfig()
    assert mock_open.call_count == 4

@patch("os.makedirs")
@patch("io.open")
@patch("os.path.exists")
@patch("arelle.Cntlr.Cntlr.setUiLanguage")
@patch("arelle.ModelManager.ModelManager.setLocale")
def test_cntlr_cache_disabled(_, mock_codes, mock_exists, mock_open, mock_makedirs):
    mock_codes.return_value = ["en-US", "en_US", "en"]
    mock_exists.return_value = True
    cntlr = Cntlr.Cntlr(uiLang=None, disable_persistent_config=True)
    assert mock_makedirs.call_count == 0
    assert mock_open.call_count == 1
    cntlr.saveConfig()
    assert mock_open.call_count == 1
