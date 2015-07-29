'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
from .Document import checkDTSdocument
from .Filing import validateFiling
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict


def dislosureSystemTypes(disclosureSystem):
    # return ((disclosure system name, variable name), ...)
    return (("EFM", "EFMplugin"),)

def disclosureSystemConfigURL(disclosureSystem):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None):
    val.validateEFMplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EFMplugin", False)
    if not (val.validateEFMplugin):
        return

    val.paramExhibitType = None # e.g., EX-101, EX-201
    val.paramFilerIdentifier = None
    val.paramFilerIdentifiers = None
    val.paramFilerNames = None
    val.paramSubmissionType = None
    if parameters:
        # parameter-provided CIKs and registrant names
        p = parameters.get(ModelValue.qname("CIK",noPrefixIsNoNamespace=True))
        if p and len(p) == 2 and p[1] not in ("null", "None"):
            val.paramFilerIdentifier = p[1]
        p = parameters.get(ModelValue.qname("cikList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramFilerIdentifiers = p[1].split(",")
        p = parameters.get(ModelValue.qname("cikNameList",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramFilerNames = p[1].split("|Edgar|")
            if val.paramFilerIdentifiers and len(val.paramFilerIdentifiers) != len(val.paramFilerNames):
                val.modelXbrl.error(("EFM.6.05.24.parameters", "GFM.3.02.02"),
                    _("parameters for cikList and cikNameList different list entry counts: %(cikList)s, %(cikNameList)s"),
                    modelXbrl=val.modelXbrl, cikList=val.paramFilerIdentifiers, cikNameList=val.paramFilerNames)
        p = parameters.get(ModelValue.qname("submissionType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramSubmissionType = p[1]
        p = parameters.get(ModelValue.qname("exhibitType",noPrefixIsNoNamespace=True))
        if p and len(p) == 2:
            val.paramExhibitType = p[1]

    if val.paramExhibitType == "EX-2.01": # only applicable for edgar production and parameterized testcases
        val.EFM60303 = "EFM.6.23.01"
    else:
        val.EFM60303 = "EFM.6.03.03"
                
    
    if any((concept.qname.namespaceURI in val.disclosureSystem.standardTaxonomiesDict) 
           for concept in val.modelXbrl.nameConcepts.get("UTR",())):
        val.validateUTR = True

def validateXbrlFinally(val):
    if not (val.validateEFMplugin):
        return

    modelXbrl = val.modelXbrl

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)
    
    validateFiling(val, modelXbrl, isEFM=True)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)
    
def validateXbrlDtsDocument(val, modelDocument, isFilingDocument):
    if not (val.validateEFMplugin):
        return

    checkDTSdocument(val, modelDocument, isFilingDocument)
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EFM',
    'version': '0.9',
    'description': '''EFM Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2013-15 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'Validate.XBRL.DTS.document': validateXbrlDtsDocument,
}
