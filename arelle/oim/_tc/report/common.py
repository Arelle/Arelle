"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from arelle.oim._tc.common import TCError

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


class TCReportValidationError(TCError):
    """A table constraints violation in an xBRL-CSV report, located by table or
    template and where applicable by CSV row (the header row is line 1), column or
    parameter."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        table_id: str | None = None,
        url: str | None = None,
        template_id: str | None = None,
        severity: str = SEVERITY_ERROR,
        row: int | None = None,
        column: str | None = None,
        parameter: str | None = None,
    ) -> None:
        self.message = message
        self.severity = severity
        self.template_id = template_id
        self.table_id = table_id
        self.url = url
        self.row = row
        self.column = column
        self.parameter = parameter
        super().__init__(code)

    def __str__(self) -> str:
        location = ""
        if self.template_id is not None:
            location += f"template '{self.template_id}'"
        if self.table_id is not None:
            location += f"table '{self.table_id}'"
        if self.row is not None:
            location += f" row {self.row}"
        if self.column is not None:
            location += f" column '{self.column}'"
        if self.parameter is not None:
            location += f" parameter '{self.parameter}'"
        if self.url is not None:
            return f"{location}: {self.message}, url: {self.url}"
        return f"{location}: {self.message}"
