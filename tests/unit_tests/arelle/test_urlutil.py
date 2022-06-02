import pytest

from arelle.UrlUtil import isValidUriReference

URIS = [
    'ftp://ftp.is.co.za/rfc/rfc1808.txt',
    'http://www.ietf.org/rfc/rfc2396.txt',
    'ldap://[2001:db8::7]/c=GB?objectClass?one',
    'mailto:John.Doe@example.com',
    'news:comp.infosystems.www.servers.unix',
    'tel:+1-816-555-1212',
    'telnet://192.0.2.16:80/',
    'urn:oasis:names:specification:docbook:dtd:xml:4.1.2',
]

URI_REFERENCES = [
    'g',
    './g',
    'g/',
    '/g',
    '//g',
    '?y',
    'g?y',
    '#s',
    'g#s',
    'g?y#s',
    ';x',
    'g;x',
    'g;x?y#s',
    '',
    '.',
    './',
    '..',
    '../',
    '../g',
    '../..',
    '../../',
    '../../g',
]


@pytest.mark.parametrize('uri', URIS)
def test_uris(uri):
    assert isValidUriReference(uri)


@pytest.mark.parametrize('uri_reference', URI_REFERENCES)
def test_uri_references(uri_reference):
    assert isValidUriReference(uri_reference)
