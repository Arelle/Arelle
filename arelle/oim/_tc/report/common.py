"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from arelle.oim._tc.common import TCError

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


class TCReportValidationError(TCError):
    """A table constraints violation in an xBRL-CSV report, located by table and where
    applicable by CSV row (the header row is line 1) and column."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        table_id: str,
        url: str,
        severity: str = SEVERITY_ERROR,
        row: int | None = None,
        column: str | None = None,
    ) -> None:
        self.message = message
        self.severity = severity
        self.table_id = table_id
        self.url = url
        self.row = row
        self.column = column
        super().__init__(code)

    def __str__(self) -> str:
        location = f"table '{self.table_id}'"
        if self.row is not None:
            location += f" row {self.row}"
        if self.column is not None:
            location += f" column '{self.column}'"
        return f"{location}: {self.message}, url: {self.url}"
