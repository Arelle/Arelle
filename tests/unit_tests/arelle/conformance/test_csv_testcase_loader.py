"""
See COPYRIGHT.md for copyright information.
"""

from io import StringIO
from unittest.mock import Mock, patch

import pytest

from arelle.conformance.CSVTestcaseLoader import CSVTestcaseException, loadCsvTestcase


class TestCsvTestcaseLoader:
    def test_loadCsvTestcase_non_csv(self) -> None:
        filepath = "testcase.xml"
        mock_modelXbrl = Mock()

        with pytest.raises(CSVTestcaseException):
            loadCsvTestcase(modelXbrl=mock_modelXbrl, filepath=filepath)

    def test_loadCsvTestcase_io_error(self) -> None:
        filepath = "nonexistent.csv"
        mock_modelXbrl = Mock()
        mock_modelXbrl.fileSource.file.side_effect = IOError("File not found")

        with pytest.raises(CSVTestcaseException):
            loadCsvTestcase(modelXbrl=mock_modelXbrl, filepath=filepath)

    def test_loadCsvTestcase_csv_header_not_testcase(self) -> None:
        filepath = "testcase.csv"
        mock_modelXbrl = Mock()
        csv_data = "other,content\nval,val\n"
        mock_file = StringIO(csv_data)
        mock_modelXbrl.fileSource.file.return_value = [mock_file]
        with pytest.raises(CSVTestcaseException) as exc_info:
            loadCsvTestcase(mock_modelXbrl, filepath)
        expected_assertion_msg = "CSV file testcase.csv doesn't have test case header: ('input', 'errors', 'report_count', 'description'), first row ['other', 'content']"
        assert str(exc_info.value) == expected_assertion_msg

    @patch("arelle.ModelDocument.create")
    def test_loadCsvTestcase_csv_not_testcase(self, mock_model_document_create: Mock) -> None:
        filepath = "testcase.csv"
        mock_modelXbrl = Mock()
        csv_data = "input,errors,report_count,description\nnot,valid\n"
        mock_file = StringIO(csv_data)
        mock_modelXbrl.fileSource.file.return_value = [mock_file]
        with pytest.raises(CSVTestcaseException) as exc_info:
            loadCsvTestcase(mock_modelXbrl, filepath)
        expected_assertion_msg = "CSV testcase file testcase.csv row 2 doesn't match header format: Header ['input', 'errors', 'report_count', 'description'] - Row ['not', 'valid']"
        assert str(exc_info.value) == expected_assertion_msg
