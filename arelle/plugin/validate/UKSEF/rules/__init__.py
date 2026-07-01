"""
See COPYRIGHT.md for copyright information.

Shared helper functions for UKSEF validation rules.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText

_: TypeGetText


def get_ukfrs_ix_references(modelXbrl: ModelXbrl) -> list[Any]:
    """Returns ix:references elements where target="UKFRS".

    :param modelXbrl: The model XBRL instance.
    :return: List of ix:references elements with target="UKFRS".
    """
    results = []
    for doc in modelXbrl.urlDocs.values():
        if doc.xmlRootElement is None:
            continue
        for elem in doc.xmlRootElement.iter():
            if elem.localName == "references" and elem.get("target") == "UKFRS":
                results.append(elem)
    return results


def get_default_ix_references(modelXbrl: ModelXbrl) -> list[Any]:
    """Returns ix:references elements with no target attribute.

    :param modelXbrl: The model XBRL instance.
    :return: List of ix:references elements with no target.
    """
    results = []
    for doc in modelXbrl.urlDocs.values():
        if doc.xmlRootElement is None:
            continue
        for elem in doc.xmlRootElement.iter():
            if elem.localName == "references" and elem.get("target") is None:
                results.append(elem)
    return results


def get_inline_elements_by_target(modelXbrl: ModelXbrl) -> dict[str | None, list[Any]]:
    """Returns inline XBRL elements grouped by their target attribute value.

    :param modelXbrl: The model XBRL instance.
    :return: Dictionary keyed by target value (None for default target).
    """
    result: dict[str | None, list[Any]] = defaultdict(list)
    for doc in modelXbrl.urlDocs.values():
        if doc.xmlRootElement is None:
            continue
        for elem in doc.xmlRootElement.iter():
            if elem.localName in ("references", "resources"):
                target = elem.get("target")
                result[target].append(elem)
    return dict(result)


def is_uksef_filing(modelXbrl: ModelXbrl) -> bool:
    """Determine if this is a UKSEF filing.

    A filing is considered a UKSEF filing if any ix:references element
    has target="UKFRS".

    :param modelXbrl: The model XBRL instance.
    :return: True if any ix:references has target="UKFRS".
    """
    return len(get_ukfrs_ix_references(modelXbrl)) > 0
