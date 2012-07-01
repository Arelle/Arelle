from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import Locale, XbrlConst
import re

def setup(val):
    val.linroleDefinitionIsDisclosure = re.compile(r"-\s+Disclosure\s+-\s",
                                                   re.IGNORECASE)

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
                    
    except Exception as err:
        val.modelXbrl.warning("US-BPG.testingException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested due to: %(err)s"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, err=err)

def final(val):
    del val.linroleDefinitionIsDisclosure
    
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
