"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

CSV_DOCUMENT_TYPES = frozenset(
    {
        "https://xbrl.org/2021/xbrl-csv",
        "http://www.xbrl.org/WGWD/YYYY-MM-DD/xbrl-csv",
        "http://xbrl.org/YYYY/xbrl-csv",
        "https://xbrl.org/((~status_date_uri~))/xbrl-csv",  # allows loading of XII "template" test cases without CI production
    }
)
