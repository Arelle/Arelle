"""
See COPYRIGHT.md for copyright information.
"""

from io import StringIO
from unittest.mock import Mock, patch

import pytest

from arelle.testengine.loader.CsvTestcaseLoader import CsvTestcaseLoader


class TestCsvTestcaseLoader:
    def test_is_loadable_csv(self) -> None:
        loader = CsvTestcaseLoader()
        assert loader.is_loadable(Mock(index_file="testcase.CSV"))

    def test_is_loadable_non_csv(self) -> None:
        loader = CsvTestcaseLoader()
        assert not loader.is_loadable(Mock(index_file="testcase.xml"))

    def test_load_nonexistent(self) -> None:
        loader = CsvTestcaseLoader()
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load(Mock(index_file="nonexistent.csv"))

    @patch('arelle.testengine.loader.CsvTestcaseLoader.CsvTestcaseLoader._open')
    def test_load_unsupported_header(self, _open) -> None:
        loader = CsvTestcaseLoader()
        mock_file = StringIO("input,errors,other,content\nval,val,val,val\n")
        _open.return_value = mock_file
        result = loader.load(Mock(index_file="testcase.csv"))
        expected_error = "CSV file testcase.csv has unsupported header(s): ['content', 'other']"
        assert len(result.load_errors) == 1
        assert result.load_errors[0].endswith(expected_error)

    @patch('arelle.testengine.loader.CsvTestcaseLoader.CsvTestcaseLoader._open')
    def test_load_missing_required_header(self, _open) -> None:
        loader = CsvTestcaseLoader()
        mock_file = StringIO("input\nval\n")
        _open.return_value = mock_file
        result = loader.load(Mock(index_file="testcase.csv"))
        expected_error = "CSV file testcase.csv is missing required header(s): ['errors']"
        assert len(result.load_errors) == 1
        assert result.load_errors[0].endswith(expected_error)

    @patch('arelle.testengine.loader.CsvTestcaseLoader.CsvTestcaseLoader._open')
    def test_load(self, _open) -> None:
        loader = CsvTestcaseLoader()
        mock_file = StringIO("input,errors\ninput.zip,error1\n")
        _open.return_value = mock_file
        result = loader.load(Mock(index_file="testcase.csv"))
        assert len(result.load_errors) == 0
        assert len(result.testcase_variations) == 1
        assert result.testcase_variations[0].full_id == 'testcase.csv:input'
        assert result.testcase_variations[0].read_first_uris == ['input.zip']
        assert len(result.testcase_variations[0].testcase_constraint_set.constraints) == 1
        assert result.testcase_variations[0].testcase_constraint_set.constraints[0].pattern == 'error1'
