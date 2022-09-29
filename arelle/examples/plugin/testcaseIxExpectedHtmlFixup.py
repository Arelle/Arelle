'''
This plug-in removes xmlns="http://www.w3.org/1999/xhtml" from
escaped html in text content of expected instance facts for inline XBRL text facts

It also provides an error code when a testcase variation does not load any iXBRL document.

See COPYRIGHT.md for copyright information.
'''
import regex as re
from arelle.ModelDocument import Type
from arelle.Version import authorLabel, copyrightLabel
from arelle.XhtmlValidate import htmlEltUriAttrs, resolveHtmlUri

def variationInstanceLoaded(testcaseInstance, variationInstance, extraErrors, inputDTSes, *args, **kwargs):
    # test case variations which have xhtml documents which are not inline blissfully load as unrecognized plain xml
    # provide an error code that no iXBRL document was loaded so test case script can honor variation's expectation that this is an error
    for inputDTS in inputDTSes.values():
        for ixds in inputDTS:
            if ixds.modelDocument.type not in (Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET):
                extraErrors.append( "NotAnIxbrlDocument" )

def expectedInstanceLoaded(expectedInstance, outputInstanceToCompare):
    for f in expectedInstance.facts:
        if not f.isNumeric and f.text and "http://www.w3.org/1999/xhtml" in f.text:
            f.text = re.sub(r"""(<[^>]+)\s+xmlns=["']http://www.w3.org/1999/xhtml["']""",r"\1", f.text)

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
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'TestcaseVariation.Validated': variationInstanceLoaded,
    'TestcaseVariation.ExpectedInstance.Loaded': expectedInstanceLoaded,
}
