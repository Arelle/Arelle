from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import Locale, ModelXbrl, XbrlConst
import os, io, re, json

def setup(val):
    val.linroleDefinitionIsDisclosure = re.compile(r"-\s+Disclosure\s+-\s",
                                                   re.IGNORECASE)
    
    # load deprecated concepts for 2012 us-gaap
    if "http://fasb.org/us-gaap/2012-01-31" in val.modelXbrl.namespaceDocs:
        usgaapDoc = val.modelXbrl.namespaceDocs["http://fasb.org/us-gaap/2012-01-31"][0]
        deprecationsJsonFile = usgaapDoc.filepathdir + os.sep + "deprecated-concepts.json"
        try:
            with io.open(deprecationsJsonFile, 'rt', encoding='utf-8') as f:
                val.usgaapDeprecations = json.load(f)
        except Exception:
            val.modelXbrl.modelManager.addToLog(_("loading us-gaap deprecated concepts in cache"))
            val.usgaapDeprecations = {}
            # load without SEC/EFM validation (doc file would not be acceptable)
            priorValidateDisclosureSystem = val.modelXbrl.modelManager.validateDisclosureSystem
            val.modelXbrl.modelManager.validateDisclosureSystem = False
            deprecationsInstance = ModelXbrl.load(val.modelXbrl.modelManager, 
                  "http://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-doc-2012-01-31.xml", 
                  _("built deprecations table in cache"))
            val.modelXbrl.modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
            if deprecationsInstance is None:
                val.modelXbrl.error("arelle:notLoaded",
                    _("US-GAAP documentation not loaded: %(file)s"),
                    modelXbrl=val, file="us-gaap-doc-2012-01-31.xml")
            else:   # load deprecations
                for labelRel in deprecationsInstance.relationshipSet(XbrlConst.conceptLabel).modelRelationships:
                    modelDocumentation = labelRel.toModelObject
                    conceptName = labelRel.fromModelObject.name
                    if modelDocumentation.role == 'http://www.xbrl.org/2009/role/deprecatedLabel':
                        val.usgaapDeprecations[conceptName] = (val.usgaapDeprecations.get(conceptName, ('',''))[0], modelDocumentation.text)
                    elif modelDocumentation.role == 'http://www.xbrl.org/2009/role/deprecatedDateLabel':
                        val.usgaapDeprecations[conceptName] = (modelDocumentation.text, val.usgaapDeprecations.get(conceptName, ('',''))[1])
            with io.open(deprecationsJsonFile, 'wt', encoding='utf-8') as f:
                jsonStr = _STR_UNICODE(json.dumps(val.usgaapDeprecations, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                f.write(jsonStr)  # 2.7 gets unicode this way
            deprecationsInstance.close()
            del deprecationsInstance # dereference closed modelXbrl

def factCheck(val, fact):
    concept = fact.concept
    context = fact.context
    if concept is None or context is None:
        return # not checkable
    
    try:
        if fact.isNumeric and not fact.isNil and fact.xValue is not None:
            # 2.4.1 decimal disagreement
            if fact.decimals and fact.decimals != "INF":
                vf = float(fact.value)
                dec = _INT(fact.decimals)
                vround = round(vf, dec)
                if vf != vround: 
                    val.modelXbrl.warning("US-BPG.2.4.1",
                        _("Decimal disagreement %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s has insignificant value %(insignificantValue)s"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                        value=fact.effectiveValue, insignificantValue=Locale.format(val.modelXbrl.locale, "%.*f", 
                                                                                    (dec + 2 if dec > 0 else 0, vf - vround), 
                                                                                    True))
            # 2.5.1 fractions disallowed on a disclosure
            if fact.isFraction:
                if any(val.linroleDefinitionIsDisclosure.match(roleType.definition)
                       for rel in val.modelXbrl.relationshipSet(XbrlConst.parentChild).toModelObject(concept)
                       for roleType in val.modelXbrl.roleTypes.get(rel.linkrole,())):
                    val.modelXbrl.warning("US-BPG.2.5.1",
                        _("Disclosure %(fact)s in context %(contextID)s value %(value)s is a fraction"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, value=fact.value)
                    
        # deprecated concept
        if concept.qname.namespaceURI == "http://fasb.org/us-gaap/2012-01-31":
            if concept.name in val.usgaapDeprecations:
                deprecation = val.usgaapDeprecations[concept.name]
                val.modelXbrl.warning("FASB:deprecatedConcept",
                    _("Concept of fact %(fact)s in context %(contextID)s value %(value)s was deprecated on %(date)s: %(documentation)s"),
                    modelObject=fact, fact=fact.qname, contextID=fact.contextID, value=fact.value, 
                    date=deprecation[0], documentation=deprecation[1])
        elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
            val.modelXbrl.warning("FASB:deprecatedConcept",
                _("Concept of fact %(fact)s in context %(contextID)s value %(value)s was deprecated on %(date)s"),
                modelObject=fact, fact=fact.qname, contextID=fact.contextID, value=fact.value, 
                date=concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"))
                    
    except Exception as err:
        val.modelXbrl.warning("US-BPG.testingException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested due to: %(err)s"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, err=err)

def final(val):
    del val.linroleDefinitionIsDisclosure
    if hasattr(val, 'usgaapDeprecations'):
        del val.usgaapDeprecations
    
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate XBRL-US Best Practice Guidance',
    'version': '0.9',
    'description': '''XBRL-US Best Practice Guidance Validation.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final,
}
