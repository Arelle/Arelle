from arelle.plugin.validate.IRD.rules.nvad_form_type import _isHan


def test_language_tag_selects_the_length_rule() -> None:
    assert not _isHan("Acme", "en")
    assert _isHan("公司", "zh-Hant-HK")
    assert not _isHan("公司", "en")
    assert _isHan("Acme Limited", "zh")


def test_han_script_is_the_fallback_when_language_is_absent() -> None:
    assert _isHan("公司", None)
    assert not _isHan("Acme", None)
    assert _isHan("Acme 公司", "")
