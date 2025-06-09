import pytest
from arelle.LeiUtil import (
    checkLei,
    LEI_INVALID_CHECKSUM,
    LEI_VALID,
    LEI_INVALID_LEXICAL,
    LEI_RESULTS,
)

LEI_TESTS = [
    ("001GPB6A9XPE8XJICC14", LEI_VALID, "Fidelity Advisor Series I"),
    ("004L5FPTUREIWK9T2N63", LEI_VALID, "Hutchin Hill Capital, LP"),
    ("00EHHQ2ZHDCFXJCPCL46", LEI_VALID, "Vanguard Russell 1000 Growth Index Trust"),
    ("00GBW0Z2GYIER7DHDS71", LEI_VALID, "Aristeia Capital, L.L.C."),
    ("1S619D6B3ZQIH6MS6B47", LEI_VALID, "Barclays Vie SA"),
    ("21380014JAZAUFJRHC43", LEI_VALID, "BRE/OPERA HOLDINGS"),
    ("21380016W7GAG26FIJ74", LEI_VALID, "SOCIETE FRANCAISE ET SUISSE"),
    ("21380058ERUIT9H53T71", LEI_VALID, "TOTAN ICAP CO., LTD"),
    ("213800A9GT65GAES2V60", LEI_VALID, "BARCLAYS SECURITIES JAPAN LIMITED"),
    ("213800DELL1MWFDHVN53", LEI_VALID, "PIRELLI JAPAN"),
    ("213800A9GT65GAES2V60", LEI_VALID, "BARCLAYS SECURITIES JAPAN LIMITED"),
    ("214800A9GT65GAES2V60", LEI_INVALID_CHECKSUM, "Error 1"),
    ("213800A9GT65GAE%2V60", LEI_INVALID_LEXICAL, "Error 2"),
    ("213800A9GT65GAES2V62", LEI_INVALID_CHECKSUM, "Error 3"),
    ("1234", LEI_INVALID_LEXICAL, "Error 4"),
    ("\n5299003M8JKHEFX58Y02", LEI_INVALID_LEXICAL, "Error 5"),
    ("029200720E3M3A4D6D01", LEI_VALID, "UNITY BANK PLC # first entry of _validLeiDespiteChecksumFailPattern"),
    ("029200720E3M3A4D6D00", LEI_INVALID_CHECKSUM, "Looks like UNITY BANK PLC except for last digit"),
]


@pytest.mark.parametrize("arg,expected,description", LEI_TESTS)
def test_tokenize(arg, expected, description):
    result = checkLei(arg)
    assert result == expected, (
        f"Got {LEI_RESULTS[result]!r}, wanted {LEI_RESULTS[expected]!r}; description {description}"
    )
