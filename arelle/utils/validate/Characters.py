"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import regex


def findProhibitedCharacters(
    text: str | None,
    pattern: regex.Pattern[str],
) -> set[str]:
    """
    Find all characters in text that match the prohibited-character pattern.

    A prohibited-character pattern typically matches characters NOT in an allowed set.

    :param text: Text to scan (None or empty returns empty set)
    :param pattern: Compiled regex that matches prohibited characters
    :return: Set of matched prohibited characters
    """
    if not text:
        return set()
    return set(pattern.findall(text))
