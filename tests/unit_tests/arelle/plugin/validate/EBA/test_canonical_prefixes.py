from types import SimpleNamespace

from lxml import etree

from arelle.plugin.validate.EBA import canonicalPrefixes

XBRLDI_NS = "http://xbrl.org/2006/xbrldi"
XBRLI_NS = "http://www.xbrl.org/2003/instance"


def _modelXbrl(namespaceDocs):
    return SimpleNamespace(namespaceDocs=namespaceDocs)


def _schemaDoc(rootXml):
    return SimpleNamespace(xmlRootElement=etree.fromstring(rootXml))


class TestCanonicalPrefixes:
    def test_schema_without_self_binding_falls_back_to_well_known_prefix(self) -> None:
        # Mirrors xbrldi-2006.xsd, which only binds the XML Schema namespace.
        xbrldiDoc = _schemaDoc(
            f'<schema xmlns="http://www.w3.org/2001/XMLSchema" targetNamespace="{XBRLDI_NS}"/>'
        )
        modelXbrl = _modelXbrl({XBRLDI_NS: [xbrldiDoc]})
        assert canonicalPrefixes(modelXbrl, XBRLDI_NS) == {"xbrldi"}

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

    def test_unknown_namespace_without_binding_has_no_expectation(self) -> None:
        ns = "http://example.com/unknown"
        unboundDoc = _schemaDoc(
            f'<schema xmlns="http://www.w3.org/2001/XMLSchema" targetNamespace="{ns}"/>'
        )
        modelXbrl = _modelXbrl({ns: [unboundDoc]})
        assert canonicalPrefixes(modelXbrl, ns) == set()
