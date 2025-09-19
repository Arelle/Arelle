import random
import string
import time

import pytest

from arelle.LeiUtil import (
    LEI_INVALID_CHECKSUM,
    LEI_INVALID_LEXICAL,
    LEI_VALID,
    checkLei,
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
    (
        "029200720E3M3A4D6D01",
        LEI_VALID,
        "UNITY BANK PLC # first entry of _validLeiDespiteChecksumFailPattern",
    ),
    (
        "029200720E3M3A4D6D00",
        LEI_INVALID_CHECKSUM,
        "Looks like UNITY BANK PLC except for last digit",
    ),
]


@pytest.mark.parametrize("arg,expected,description", LEI_TESTS)
def test_checkLei(arg, expected, description):
    result = checkLei(arg)
    assert result is expected, (
        f"Got {result.name}, wanted {expected.name}; description {description}"
    )


def test_performance_checkLei():
    NANOSECONDS_IN_MILLISECOND = 1_000_000
    MIN_TIME = 50 * NANOSECONDS_IN_MILLISECOND
    MAX_TIME = 1_000 * NANOSECONDS_IN_MILLISECOND
    NUM_LEIS = 100_000

    num_letter_population = string.ascii_uppercase + string.digits
    random_leis = [
        "".join(
            random.choices(num_letter_population, k=random.randint(17, 19))
            + random.choices(string.digits, k=2)
        )
        for _ in range(NUM_LEIS)
    ]
    # Mix in valid LEIs
    leis = [
        lei
        for lei, valid, _ in LEI_TESTS
        for _ in range(NUM_LEIS)
        if valid == LEI_VALID
    ] + random_leis
    random.shuffle(leis)
    leis = leis[:NUM_LEIS]

    start = time.perf_counter_ns()
    for lei in leis:
        checkLei(lei)
    taken = time.perf_counter_ns() - start

    assert MIN_TIME < taken < MAX_TIME, (
        f"Processed {len(leis):,} LEIs in {(taken/NANOSECONDS_IN_MILLISECOND):,.0f} milliseconds. Rate = {int(10**9 / (taken / len(leis))):,} per second."
    )
