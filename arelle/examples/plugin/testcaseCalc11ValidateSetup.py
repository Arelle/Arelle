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
from arelle.ValidateXbrlCalcs import ValidateCalcsMode as CalcsMode

def testcaseVariationLoaded(testInstance, testcaseInstance, modelTestcaseVariation):
    for result in modelTestcaseVariation.iter("{*}result"):
        for n, v in result.attrib.items():
            if n.endswith("mode"):
                if v == "round-to-nearest":
                    testInstance.modelManager.validateCalcs = CalcsMode.ROUND_TO_NEAREST
                elif v == "truncate":
                    testInstance.modelManager.validateCalcs = CalcsMode.TRUNCATION

__pluginInfo__ = {
    'name': 'Testcase obtain expected calc 11 mode from variation/result@mode',
    'version': '0.9',
    'description': "This plug-in removes xxx.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2019 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'TestcaseVariation.Xbrl.Loaded': testcaseVariationLoaded,
}
