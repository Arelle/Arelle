"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations


class TCError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
