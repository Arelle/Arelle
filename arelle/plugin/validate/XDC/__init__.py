'''
See COPYRIGHT.md for copyright information.
'''
import os
from arelle import ModelDocument, XbrlConst
from arelle.Version import authorLabel, copyrightLabel

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("XDC", "XDCplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateXDCplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "XDCplugin", False)
    if not (val.validateXDCplugin):
        return


def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateXDCplugin):
        return

    modelXbrl = val.modelXbrl
    modelDocument = modelXbrl.modelDocument

    _statusMsg = _("validating {0} filing rules").format(val.disclosureSystem.name)
    modelXbrl.profileActivity()
    modelXbrl.modelManager.showStatus(_statusMsg)

    if modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):


        parentChildRels = modelXbrl.relationshipSet(XbrlConst.parentChild)
        referenceRels = modelXbrl.relationshipSet(XbrlConst.conceptReference)

        for qn, facts in modelXbrl.factsByQname.items():
            concept = modelXbrl.qnameConcepts[qn]
            if not parentChildRels.toModelObject(concept):
                modelXbrl.error("XDC:factElementNotPresented",
                                _("Element %(concept)s is used in a fact in the instance, but is not in any presentation relationships."),
                                modelObject=facts, concept=qn)

        requiredConcepts = set(preRel.toModelObject.qname
                               for preRel in parentChildRels.modelRelationships
                               for refRel in referenceRels.fromModelObject(preRel.toModelObject)
                               if refRel.toModelObject.role == "http://www.changhong.com/XDC/role/definitionalAttribute"
                               for refPart in refRel.toModelObject.iterchildren()
                               if refPart.localName == "RequiredInDocument"
                               if refPart.textValue.strip().lower() == "true")

        missingConcepts = requiredConcepts - modelXbrl.factsByQname.keys()
        if missingConcepts:
            modelXbrl.error("XDC:missingRequiredFacts",
                            _("Required facts missing from document: %(concepts)s."),
                            modelObject=modelXbrl, concepts=", ".join(sorted(str(qn) for qn in missingConcepts)))

    modelXbrl.profileActivity(_statusMsg, minTimeToShow=0.0)
    modelXbrl.modelManager.showStatus(None)


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate XDC',
    'version': '1.0',
    'description': '''XDC Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,

    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
}
