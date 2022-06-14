import pytest
from arelle.ModelValue import QName
from itertools import product

prefixes = ['pre', 1, '', None]
ns_uris = ['http://valid.com', 'invalid', '', 1,  None]
local_names = ['Cash', 1, '', None]

general_test_data = list(product(*[prefixes, ns_uris, local_names]))


@pytest.mark.parametrize('prefix, ns_uri, local_name', general_test_data)
class TestQnameGeneralUsage:
    def test_create(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name) is not None, 'create'

    def test_prefix(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name).prefix == prefix, 'prefix'

    def test_namespace_uri(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name).namespaceURI == ns_uri, 'namespace uri'

    def test_local_name(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name).localName == local_name, 'local_name'

    def test_expanded_name(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name).expandedName == "{}#{}".format(ns_uri or '', local_name), 'expanded name'

    def test_clark_notation(self, prefix, ns_uri, local_name):
        qname_clark = QName(prefix, ns_uri, local_name).clarkNotation
        assertion = '{{{}}}{}'.format(ns_uri, local_name) if ns_uri else local_name
        assert qname_clark == assertion, 'clark name'

    def test_qname_value_hash(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name).qnameValueHash == hash((ns_uri, local_name)), 'qname value hash'

    def test_repr(self, prefix, ns_uri, local_name):
        qname_string = QName(prefix, ns_uri, local_name).__repr__()
        assertion = '{}:{}'.format(prefix, local_name) if prefix else local_name
        if qname_string is None:
            assert qname_string is assertion, 'str'
        else:
            assert qname_string == assertion, 'str'

    def test_str(self, prefix, ns_uri, local_name):
        qname_string = QName(prefix, ns_uri, local_name).__str__()
        assertion = '{}:{}'.format(prefix, local_name) if prefix else local_name
        if qname_string is None:
            assert qname_string is assertion, 'str'
        else:
            assert qname_string == assertion, 'str'

    def test_eq(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name) == QName(prefix, ns_uri, local_name), 'qname eq'

    def test_ne(self, prefix, ns_uri, local_name):
        assert QName(prefix, ns_uri, local_name) != QName('non_matching_prefix', 'http://nonmatchingnamespaceuri', 'NonMatchingLocalName'), 'qname ne'


comparison_test_data = [
    (None, 'AnyString'),  # ns_uri sorts first
    ('a', 'AnyString'),  # ns_uri sorts first
    ('http://ns.com', None),  # ns_uri eq so None local_name sorts first
    ('http://ns.com', 'A'),  # ns_uri eq so local_name sorts first
]


@pytest.mark.parametrize('ns_uri, local_name', comparison_test_data)
class TestQnameComparisons:
    def test_lt(self, ns_uri, local_name):
        assert QName(None, ns_uri, local_name) < QName(None, 'http://ns.com', 'B'), 'qname lt'

    def test_gt(self, ns_uri, local_name):
        assert QName(None, 'http://ns.com', 'B') > QName(None, ns_uri, local_name), 'qname gt'


comparison_equal_test_data = comparison_test_data + [
    ('http://ns.com', 'B'),  # ns_uri eq and local_name eq
]


@pytest.mark.parametrize('ns_uri, local_name', comparison_equal_test_data)
class TestQnameComparisonEqual:
    def test_le(self, ns_uri, local_name):
        assert QName(None, ns_uri, local_name) <= QName(None, 'http://ns.com', 'B'), 'qname le'

    def test_ge(self, ns_uri, local_name):
        assert QName(None, 'http://ns.com', 'B') >= QName(None, ns_uri, local_name), 'qname ge'


bad_comparison_test_data = [
    'Random Object',
    None,
    True,
    1
]

@pytest.mark.parametrize('random_object', bad_comparison_test_data)
class TestQnameBadComparisons:
    def test_lt_bad_comparison(self, random_object):
        with pytest.raises(TypeError):
            qname = QName(None, None, None)
            qname < random_object

    def test_le_bad_comparison(self, random_object):
        with pytest.raises(TypeError):
            qname = QName(None, None, None)
            qname <= random_object

    def test_gt_bad_comparison(self, random_object):
        with pytest.raises(TypeError) as ex_info:
            qname = QName(None, None, None)
            qname > random_object

    def test_ge_bad_comparison(self, random_object):
        with pytest.raises(TypeError):
            qname = QName(None, None, None)
            qname >= random_object


def test_ne_bad_comparison():
    assert QName('pre', 'http://namespace.com', 'Cash') != 'Random Object', 'qname ne'


@pytest.mark.parametrize('local_name', [
    'Cash',
    1,
    True
])
def test_bool_true(local_name):
    assert QName(None, None, local_name), 'qname bool'


@pytest.mark.parametrize('local_name', [
    '',
    0,
    False
])
def test_bool_false(local_name):
    assert not QName('pre', 'http://namespace.com', local_name), 'qname bool'
