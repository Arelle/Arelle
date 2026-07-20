from __future__ import annotations

import datetime

import pytest

from arelle.ModelValue import QName, gDay, gMonthDay, qnameFromNsmap

NSMAP = {
    None: "http://default.ns",
    "pfx": "http://pfx.ns",
    "other": "http://other.ns",
}


class TestQnameFromNsmap:
    def test_unprefixed_name(self):
        result = qnameFromNsmap(NSMAP, "localName")
        assert result == QName(None, "http://default.ns", "localName")

    def test_prefixed_name(self):
        result = qnameFromNsmap(NSMAP, "pfx:localName")
        assert result == QName("pfx", "http://pfx.ns", "localName")

    def test_xml_prefix(self):
        result = qnameFromNsmap(NSMAP, "xml:lang")
        assert result == QName("xml", "http://www.w3.org/XML/1998/namespace", "lang")

    def test_href_style(self):
        result = qnameFromNsmap(NSMAP, "http://some.ns#localName")
        assert result == QName(None, "http://some.ns", "localName")

    def test_href_no_namespace(self):
        result = qnameFromNsmap(NSMAP, "#localName")
        assert result == QName(None, "", "localName")

    def test_undefined_prefix_returns_none(self):
        result = qnameFromNsmap(NSMAP, "bad:localName")
        assert result is None

    def test_undefined_prefix_raises_custom_exception(self):
        with pytest.raises(ValueError):
            qnameFromNsmap(NSMAP, "bad:localName", prefixException=ValueError)

    def test_undefined_prefix_raises_custom_exception_instance(self):
        with pytest.raises(ValueError, match="my message"):
            qnameFromNsmap(NSMAP, "bad:localName", prefixException=ValueError("my message"))

    def test_no_default_namespace(self):
        nsmap = {"pfx": "http://pfx.ns"}
        result = qnameFromNsmap(nsmap, "localName")
        assert result == QName(None, None, "localName")

    def test_empty_nsmap(self):
        result = qnameFromNsmap({}, "localName")
        assert result == QName(None, None, "localName")

    def test_empty_nsmap_with_prefix_returns_none(self):
        result = qnameFromNsmap({}, "pfx:localName")
        assert result is None

    def test_empty_nsmap_with_prefix_raises(self):
        with pytest.raises(ValueError):
            qnameFromNsmap({}, "pfx:localName", prefixException=ValueError)


class TestGDateCombinedTimezoneOffset:
    """gMonthDay/gDay are the only g* types whose field unit (a calendar day, 24h) is
    shorter than the 28h two opposite +-14:00 offsets can combine to (XSD Datatypes
    3.2.7.3), so unlike gYear/gYearMonth/gMonth, adjacent-day values with different,
    explicit timezones can denote the *same* instant despite differing numeral fields.
    """

    def test_gMonthDay_adjacent_days_opposite_offsets_are_equal_instant(self):
        # --06-14 at -10:00 is 2000-06-14T10:00:00Z; --06-15 at +14:00 is also
        # 2000-06-14T10:00:00Z (2000-06-15T00:00:00 minus the +14:00 offset).
        a = gMonthDay(6, 14, tzinfo=datetime.timezone(datetime.timedelta(hours=-10)))
        b = gMonthDay(6, 15, tzinfo=datetime.timezone(datetime.timedelta(hours=14)))
        assert a == b
        assert not (a < b)
        assert not (a > b)
        assert a <= b and a >= b
        assert hash(a) == hash(b)

    def test_gDay_adjacent_days_opposite_offsets_are_equal_instant(self):
        a = gDay(14, tzinfo=datetime.timezone(datetime.timedelta(hours=-10)))
        b = gDay(15, tzinfo=datetime.timezone(datetime.timedelta(hours=14)))
        assert a == b
        assert not (a < b)
        assert not (a > b)
        assert hash(a) == hash(b)

    def test_gMonthDay_naive_vs_aware_never_equal_and_order_raises(self):
        naive = gMonthDay(6, 14)
        aware = gMonthDay(6, 14, tzinfo=datetime.timezone.utc)
        assert naive != aware
        assert not (naive == aware)
        with pytest.raises(TypeError):
            naive < aware

    def test_gMonthDay_large_gap_still_determinate_despite_offsets(self):
        # A gap of many days can never be closed by a <=28h combined swing.
        early = gMonthDay(1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=-14)))
        late = gMonthDay(6, 15, tzinfo=datetime.timezone(datetime.timedelta(hours=14)))
        assert early < late
        assert not (early == late)
