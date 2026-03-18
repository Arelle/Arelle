"""
See COPYRIGHT.md for copyright information.
"""


class TCError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__()
