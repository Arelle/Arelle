from arelle.plugin.validate.IRD.rules.nvad_special_flags import PRACTISING_CERT_PATTERN


def test_practising_certificate_accepts_letters_and_digits_up_to_six() -> None:
    assert PRACTISING_CERT_PATTERN.fullmatch("AB12")
    assert PRACTISING_CERT_PATTERN.fullmatch("123456")
    assert PRACTISING_CERT_PATTERN.fullmatch("A")


def test_practising_certificate_rejects_empty_long_and_spaced_values() -> None:
    assert PRACTISING_CERT_PATTERN.fullmatch("") is None
    assert PRACTISING_CERT_PATTERN.fullmatch("1234567") is None
    assert PRACTISING_CERT_PATTERN.fullmatch("AB 12") is None
