from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arelle.testengine.Testcase import Testcase


def swap_id(testcase: Testcase, id_swaps: dict[tuple[str, tuple[str, ...]], str]) -> Testcase:
    key = (testcase.full_id, tuple(testcase.read_first_uris))
    if key in id_swaps:
        testcase = replace(testcase, full_id=id_swaps[key])
        del id_swaps[key]
        return testcase
    return testcase


def swap_read_first_uri(testcase: Testcase, read_first_uri_swaps: dict[tuple[str, tuple[str, ...]], tuple[str, ...]]) -> Testcase:
    key = (testcase.full_id, tuple(testcase.read_first_uris))
    if key in read_first_uri_swaps:
        testcase = replace(testcase, read_first_uris=list(read_first_uri_swaps[key]))
        del read_first_uri_swaps[key]
        return testcase
    return testcase
