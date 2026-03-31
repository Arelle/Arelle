from __future__ import annotations

from arelle.oim._model import OimReport


class TestOimReportNamespaces:
    def test_returns_namespaces_from_document_info(self) -> None:
        report = OimReport(
            oim_object={
                "documentInfo": {
                    "namespaces": {
                        "iso4217": "http://www.xbrl.org/2003/iso4217",
                        "xbrl": "https://xbrl.org/2021",
                    },
                },
            }
        )
        assert report.namespaces == {
            "iso4217": "http://www.xbrl.org/2003/iso4217",
            "xbrl": "https://xbrl.org/2021",
        }

    def test_returns_empty_dict_when_no_document_info(self) -> None:
        report = OimReport(oim_object={})
        assert report.namespaces == {}

    def test_returns_empty_dict_when_no_namespaces(self) -> None:
        report = OimReport(oim_object={"documentInfo": {}})
        assert report.namespaces == {}

    def test_filters_non_string_namespace_values(self) -> None:
        report = OimReport(
            oim_object={
                "documentInfo": {
                    "namespaces": {
                        "valid": "http://example.com",
                        "invalid_list": ["not", "a", "string"],
                        "invalid_int": 42,
                        "invalid_none": None,
                        "invalid_dict": {"nested": "value"},
                    },
                },
            }
        )
        assert report.namespaces == {"valid": "http://example.com"}

    def test_filters_non_string_prefix_keys(self) -> None:
        report = OimReport(
            oim_object={
                "documentInfo": {
                    "namespaces": {
                        "valid": "http://example.com",
                        123: "http://bad-key.com",
                    },
                },
            }
        )
        assert report.namespaces == {"valid": "http://example.com"}

    def test_returns_empty_dict_when_namespaces_empty(self) -> None:
        report = OimReport(
            oim_object={
                "documentInfo": {"namespaces": {}},
            }
        )
        assert report.namespaces == {}
