from mock import patch

from arelle import Cntlr


@patch('io.open')
@patch('arelle.Cntlr.Cntlr.setUiLanguage')
@patch('arelle.ModelManager.ModelManager.setLocale')
def test_cntlr_cache_enabled(_, mock_codes, mock_open):
    mock_codes.return_value = ['en-US', 'en_US', 'en']
    cntlr = Cntlr.Cntlr(uiLang=None)
    assert mock_open.call_count == 1
    cntlr.saveConfig()
    assert mock_open.call_count == 2

@patch('io.open')
@patch('arelle.Cntlr.Cntlr.setUiLanguage')
@patch('arelle.ModelManager.ModelManager.setLocale')
def test_cntlr_cache_disabled(_, mock_codes, mock_open):
    mock_codes.return_value = ['en-US', 'en_US', 'en']
    cntlr = Cntlr.Cntlr(uiLang=None, disable_persistent_config=True)
    assert mock_open.call_count == 0
    cntlr.saveConfig()
    assert mock_open.call_count == 0
