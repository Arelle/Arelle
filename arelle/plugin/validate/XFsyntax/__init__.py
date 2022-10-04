'''
XBRL Formula language syntax checker using ebnf parser

for execution of xf formula, please instead use plug-in formulaLoader.py

requires xf.py from XII conformance-formula/tf/syntax

See COPYRIGHT.md for copyright information.
'''

import os
from arelle.Version import authorLabel, copyrightLabel


# interfaces for Arelle plugin operation
def isXfLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    return os.path.splitext(mappedUri)[1] == ".xf"

def xfLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if os.path.splitext(filepath)[1] != ".xf":
        return None # not an XBRL formula syntax file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading XBRL Formula file: {0}").format(os.path.basename(filepath)))

    try:
        import tatsu.exceptions
    except ImportError:
        modelXbrl.error("xf:missingTatsu",
                        "Python library module Tatsu must be installed.")
    from .xf import XFParser
    with open(filepath, "r") as f:
        xf = f.read()
        parser = XFParser()
        try:
            ast = parser.parse(xf, rule_name='module')
        except tatsu.exceptions.FailedParse as err:
            modelXbrl.error("xf:syntax",
                            "Unrecoverable error: %(error)s",
                            modelObject=modelXbrl, error=err)

    # create dummy modelDocument for successful plugin execution by ModelDopcument
    from arelle.ModelDocument import Type, create as createModelDocument
    doc = createModelDocument(modelXbrl, Type.LINKBASE, filepath, documentEncoding="utf-8", initialXml='''
<!--  Dummy linkbase -->
<link:linkbase
   xmlns:link="http://www.xbrl.org/2003/linkbase"
   xsi:schemaLocation="http://www.xbrl.org/2003/linkbase http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd"
/>
''')
    return doc

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate XF Syntax',
    'version': '1.0',
    'description': '''XBRL Formula XF Syntax Validation only, not execution of formulae.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isXfLoadable,
    'ModelDocument.PullLoader': xfLoader,
}
