"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from decimal import MAX_PREC, Context

# Never rounds, so decimal arithmetic keeps every digit of a value.
EXACT_CONTEXT = Context(prec=MAX_PREC)


class TCError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
