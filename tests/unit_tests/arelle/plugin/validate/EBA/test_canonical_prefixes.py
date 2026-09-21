from types import SimpleNamespace

from lxml import etree

from arelle.plugin.validate.EBA import canonicalPrefixes

XBRLI_NS = "http://www.xbrl.org/2003/instance"


def _modelXbrl(namespaceDocs):
    return SimpleNamespace(namespaceDocs=namespaceDocs)


def _schemaDoc(rootXml):
    return SimpleNamespace(xmlRootElement=etree.fromstring(rootXml))


class TestCanonicalPrefixes:
    def test_schema_binding_its_own_namespace_wins(self) -> None:
        xbrliDoc = _schemaDoc(
            f'<schema xmlns="http://www.w3.org/2001/XMLSchema" xmlns:custom="{XBRLI_NS}" targetNamespace="{XBRLI_NS}"/>'
        )
        modelXbrl = _modelXbrl({XBRLI_NS: [xbrliDoc]})
        assert canonicalPrefixes(modelXbrl, XBRLI_NS) == {"custom"}

    def test_unloaded_well_known_namespace_uses_table(self) -> None:
        assert canonicalPrefixes(_modelXbrl({}), XBRLI_NS) == {"xbrli"}

    def test_unknown_namespace_has_no_expectation(self) -> None:
        assert canonicalPrefixes(_modelXbrl({}), "http://example.com/unknown") == set()
