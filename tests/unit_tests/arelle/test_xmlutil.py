from unittest.mock import Mock, patch

from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.XmlUtil import (
    escapedNode,
)
from arelle.XhtmlValidate import (
    htmlEltUriAttrs,
    resolveHtmlUri,
)


@patch('arelle.XmlUtil.htmlEltUriAttrs', new=htmlEltUriAttrs)
@patch('arelle.XmlUtil.resolveHtmlUri', new=resolveHtmlUri)
def test_opaque_uris_not_path_normed():
    uri = 'data:image/png;base64,iVBORw0K//a'
    elt_attrs = {'src': uri}
    elt = Mock(
        spec=ModelObject,

        localName='img',
        namespaceURI='http://www.w3.org/1999/xhtml',
        modelDocument=Mock(htmlBase=None),
        prefix=None,

        get=elt_attrs.get,
        items=elt_attrs.items,
    )
    elt.qname = qname(elt)
    node = escapedNode(elt, start=True, empty=True, ixEscape=True, ixResolveUris=True)
    assert node == f'<img src="{uri}">'
