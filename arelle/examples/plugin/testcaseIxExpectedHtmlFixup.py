'''
This plug-in removes xmlns="http://www.w3.org/1999/xhtml" from 
escaped html in text content of expected instance facts for inline XBRL text facts

(c) Copyright 2019 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re
from arelle.XhtmlValidate import htmlEltUriAttrs, resolveHtmlUri

def expectedInstanceLoaded(expectedInstance, outputInstanceToCompare):
    for f in expectedInstance.facts:
        if not f.isNumeric and f.text and "http://www.w3.org/1999/xhtml" in f.text:
            f.text = re.sub("(<[^>]+)\s+xmlns=[\"']http://www.w3.org/1999/xhtml[\"']",r"\1", f.text)
            
    # fixup relative urls in fact footnotes
    for elt in expectedInstance.modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/1999/xhtml}*"):
        for n in htmlEltUriAttrs.get(elt.localName, ()):
            v = elt.get(n)
            if v:
                v = resolveHtmlUri(elt, n, v).replace(" ", "%20")
                elt.set(n, v)
                
__pluginInfo__ = {
    'name': 'Testcase fixup escaped html xmlns',
    'version': '0.9',
    'description': "This plug-in removes xxx.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2019 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'TestcaseVariation.ExpectedInstance.Loaded': expectedInstanceLoaded,
}
