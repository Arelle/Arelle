'''
See COPYRIGHT.md for copyright information.
'''
import os
from arelle import ModelDocument, ModelValue, XmlUtil
from arelle.ModelValue import qname
from arelle.plugin.validate.EFM.Document import checkDTSdocument
from arelle.plugin.validate.EFM.Filing import validateFiling
from arelle.Version import authorLabel, copyrightLabel

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("GFM", "GFMplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateGFMplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "GFMplugin", False)
    if not (val.validateGFMplugin):
        return

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateGFMplugin):
        return

    modelXbrl = val.modelXbrl

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)

    validateFiling(val, modelXbrl, isGFM=True)

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)

def validateXbrlDtsDocument(val, modelDocument, isFilingDocument, *args, **kwargs):
    if not (val.validateGFMplugin) or not modelDocument:
        return

    checkDTSdocument(val, modelDocument, isFilingDocument)


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate GFM',
    'version': '0.9',
    'description': '''GFM Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'Validate.XBRL.DTS.document': validateXbrlDtsDocument,
}
