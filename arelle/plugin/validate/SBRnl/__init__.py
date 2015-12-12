'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict
from .CustomLoader import checkForBOMs
from .Document import checkDTSdocument
from .Filing import validateFiling


def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system type name, variable name), ...)
    return (("SBR.NL", "SBRNLplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateSBRNLplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "SBRNLplugin", False)
    if not val.validateSBRNLplugin:
        return

    val.prefixNamespace = {}
    val.namespacePrefix = {}
    val.idObjects = {}


def validateXbrlFinally(val):
    if not val.validateSBRNLplugin:
        return

    modelXbrl = val.modelXbrl

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    validateFiling(val, modelXbrl)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    
def validateFinally(val, *args, **kwargs):
    if not val.validateSBRNLplugin:
        return
    
    del val.prefixNamespace, val.namespacePrefix, val.idObjects
    
def validateXbrlDtsDocument(val, modelDocument, isFilingDocument, *args, **kwargs):
    if not val.validateSBRNLplugin:
        return

    checkDTSdocument(val, modelDocument, isFilingDocument)
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate SBR NL',
    'version': '1.0',
    'description': '''SBR NL Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'Validate.XBRL.DTS.document': validateXbrlDtsDocument,
    'Validate.Finally': validateFinally,
    'ModelDocument.CustomLoader': checkForBOMs
}
