from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import Locale, ModelXbrl, XbrlConst
from arelle.FileSource import openFileSource
import os, io, re, json
from collections import defaultdict

ugtNamespace = "http://fasb.org/us-gaap/2012-01-31"

def setup(val):
    val.linroleDefinitionIsDisclosure = re.compile(r"-\s+Disclosure\s+-\s",
                                                   re.IGNORECASE)
    val.linkroleDefinitionStatementSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*", # no restriction to type of statement
                                                      re.IGNORECASE)
    cntlr = val.modelXbrl.modelManager.cntlr
    # load deprecated concepts for 2012 us-gaap
    if ugtNamespace in val.modelXbrl.namespaceDocs:
        usgaapDoc = val.modelXbrl.namespaceDocs[ugtNamespace][0]
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
                  # "http://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-doc-2012-01-31.xml",
                  # load from zip (especially after caching) is incredibly faster
                  openFileSource("http://xbrl.fasb.org/us-gaap/2012/us-gaap-2012-01-31.zip/us-gaap-2012-01-31/elts/us-gaap-doc-2012-01-31.xml", cntlr), 
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
        ugtCalcsJsonFile = usgaapDoc.filepathdir + os.sep + "ugt-calculations.json"
        try:
            with io.open(ugtCalcsJsonFile, 'rt', encoding='utf-8') as f:
                val.usgaapCalculations = json.load(f)
        except Exception:
            val.modelXbrl.modelManager.addToLog(_("loading us-gaap calculations in cache"))
            val.usgaapCalculations = {}
            # load without SEC/EFM validation (doc file would not be acceptable)
            priorValidateDisclosureSystem = val.modelXbrl.modelManager.validateDisclosureSystem
            val.modelXbrl.modelManager.validateDisclosureSystem = False
            calculationsInstance = ModelXbrl.load(val.modelXbrl.modelManager, 
                  # "http://xbrl.fasb.org/us-gaap/2012/entire/us-gaap-entryPoint-std-2012-01-31.xsd",
                  # load from zip (especially after caching) is incredibly faster
                  openFileSource("http://xbrl.fasb.org/us-gaap/2012/us-gaap-2012-01-31.zip/us-gaap-2012-01-31/entire/us-gaap-entryPoint-std-2012-01-31.xsd", cntlr), 
                  _("built us-gaap calculations cache"))
            val.modelXbrl.modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
            if calculationsInstance is None:
                val.modelXbrl.error("arelle:notLoaded",
                    _("US-GAAP calculations not loaded: %(file)s"),
                    modelXbrl=val, file="http://xbrl.fasb.org/us-gaap/2012/entire/us-gaap-entryPoint-std-2012-01-31.xsd")
            else:   # load calculations
                for ELR in calculationsInstance.relationshipSet(XbrlConst.summationItem).linkRoleUris:
                    elrRelSet = calculationsInstance.relationshipSet(XbrlConst.summationItem, ELR)
                    definition = ""
                    for roleType in calculationsInstance.roleTypes.get(ELR,()):
                        definition = roleType.definition
                        break
                    isStatementSheet = bool(val.linkroleDefinitionStatementSheet.match(definition))
                    elrUgtCalcs = {"#roots": [c.name for c in elrRelSet.rootConcepts],
                                   "#definition": definition,
                                   "#isStatementSheet": isStatementSheet}
                    for relFrom, rels in elrRelSet.fromModelObjects().items():
                        elrUgtCalcs[relFrom.name] = [rel.toModelObject.name for rel in rels]
                    val.usgaapCalculations[ELR] = elrUgtCalcs
                with io.open(ugtCalcsJsonFile, 'wt', encoding='utf-8') as f:
                    jsonStr = _STR_UNICODE(json.dumps(val.usgaapCalculations, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                    f.write(jsonStr)  # 2.7 gets unicode this way
                calculationsInstance.close()
                del calculationsInstance # dereference closed modelXbrl
    val.deprecatedFactConcepts = defaultdict(list)
    val.deprecatedDimensions = defaultdict(list)
    val.deprecatedMembers = defaultdict(list)

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
                if _ISFINITE(vf):
                    dec = _INT(fact.decimals)
                    vround = round(vf, dec)
                    if vf != vround: 
                        val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG.2.4.1",
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
                    val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG.2.5.1",
                        _("Disclosure %(fact)s in context %(contextID)s value %(value)s is a fraction"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, value=fact.value)
                    
        # deprecated concept
        if concept.qname.namespaceURI == "http://fasb.org/us-gaap/2012-01-31":
            if concept.name in val.usgaapDeprecations:
                val.deprecatedFactConcepts[concept].append(fact)
        elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
            val.deprecatedFactConcepts[concept].append(fact)
        if fact.isItem and fact.context is not None:
            for dimConcept, modelDim in fact.context.segDimValues.items():
                if dimConcept.qname.namespaceURI == "http://fasb.org/us-gaap/2012-01-31":
                    if dimConcept.name in val.usgaapDeprecations:
                        val.deprecatedDimensions[dimConcept].append(fact)
                elif dimConcept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
                    val.deprecatedDimensions[dimConcept].append(fact)
                if modelDim.isExplicit:
                    member = modelDim.member
                    if member is not None:
                        if member.qname.namespaceURI == "http://fasb.org/us-gaap/2012-01-31":
                            if member.name in val.usgaapDeprecations:
                                val.deprecatedMembers[member].append(fact)
                        elif member.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
                            val.deprecatedMembers[member].append(fact)
    except Exception as err:
        val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG.testingException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested due to: %(err)s"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, err=err)

def final(val, conceptsUsed):
    for depType, depItems in (("Concept", val.deprecatedFactConcepts),
                              ("Dimension", val.deprecatedDimensions),
                              ("Member", val.deprecatedMembers)):
        for concept, facts in depItems.items():
            if concept.qname.namespaceURI == "http://fasb.org/us-gaap/2012-01-31":
                if concept.name in val.usgaapDeprecations:
                    deprecation = val.usgaapDeprecations[concept.name]
                    val.modelXbrl.log('WARNING-SEMANTIC', "FASB:deprecated{0}".format(depType),
                        _("%(deprecation)s of fact(s) %(fact)s (e.g., in context %(contextID)s value %(value)s) was deprecated on %(date)s: %(documentation)s"),
                        modelObject=facts, fact=facts[0].qname, contextID=facts[0].contextID, value=facts[0].value,
                        deprecation=depType, 
                        date=deprecation[0], documentation=deprecation[1])
            elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
                val.modelXbrl.log('WARNING-SEMANTIC', "FASB:deprecated{0}".format(depType),
                    _("%(deprecation)s of facts %(fact)s in context %(contextID)s value %(value)s was deprecated on %(date)s"),
                    modelObject=facts, fact=facts[0].qname, contextID=facts[0].contextID, value=facts[0].value,
                    deprecation=depType, 
                    date=concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"))
        
    del val.deprecatedFactConcepts
    del val.deprecatedDimensions
    del val.deprecatedMembers

    if hasattr(val, 'usaapCalculations'):
        # check for usgaap calculations missing from extension
        ugtTotalConceptNames = set(totalConceptName 
                                   for ugtRels in val.usgaapCalculations.values()
                                   for totalConceptName in ugtRels.keys())
        issues = []
        for totalConcept in conceptsUsed:
            # is it ugt concept on a filing face sheet statement
            if (totalConcept.qname.namespaceURI == ugtNamespace and
                totalConcept.qname.localName in ugtTotalConceptNames and
                any(val.linkroleDefinitionStatementSheet.match(roleType.definition)
                   for rel in val.modelXbrl.relationshipSet(XbrlConst.parentChild).toModelObject(totalConcept)
                   for roleType in val.modelXbrl.roleTypes.get(rel.linkrole,()))):
                # is it a total in usgaap-calculations on a statement
                for ugtELR, ugtRels in val.usgaapCalculations.items():
                    if ugtRels["#isStatementSheet"] and totalConcept.name in ugtRels:
                        # find compatible filed concepts on ugt summation items
                        for itemName in ugtRels[totalConcept.name]:
                            itemQname = qname(ugtNamespace,itemName)
                            itemConcept = val.modelXbrl.qnameConcepts.get(itemQname)
                            if itemConcept is not None and itemConcept in conceptsUsed:
                                # and item concept appears on a same face statement with total concept
                                filingELR = None
                                for rel in val.modelXbrl.relationshipSet(XbrlConst.parentChild).toModelObject(itemConcept):
                                    for roleType in val.modelXbrl.roleTypes.get(rel.linkrole,()):
                                        if (val.linkroleDefinitionStatementSheet.match(roleType.definition) and
                                            val.modelXbrl.relationshipSet(XbrlConst.parentChild,rel.linkrole)
                                            .isRelated(totalConcept,'sibling-or-descendant',itemConcept)):
                                            filingELR = rel.linkrole
                                            break
                                    if filingELR:
                                        break
                                if filingELR:
                                    # are there any compatible facts for this sum?
                                    for totalFact in val.modelXbrl.factsByQname[totalConcept.qname]:
                                        for itemFact in val.modelXbrl.factsByQname[itemQname]:
                                            if (totalFact.context is not None and totalFact.context.isEqualTo(itemFact.context) and
                                                totalFact.unit is not None and totalFact.unit.isEqualTo(itemFact.unit)):
                                                foundFiledItemCalc = False
                                                # is there a summation in the filing
                                                for rel in val.modelXbrl.relationshipSet(XbrlConst.summationItem).fromModelObject(totalConcept):
                                                    if rel.toModelObject is itemConcept:
                                                        foundFiledItemCalc = True
                                                if not foundFiledItemCalc:
                                                    issues.append((filingELR,
                                                                   ugtELR,
                                                                   itemName,
                                                                   totalFact,
                                                                   itemFact))
                if issues:
                    filingELRs = set()
                    ugtELRs = set()
                    itemIssuesELRs = defaultdict(set)
                    contextIDs = set()
                    for issue in issues:
                        filingELR, ugtELR, itemName, totalFact, itemFact = issue
                        filingELRs.add(filingELR)
                        ugtELRs.add(ugtELR)
                        contextIDs.add(totalFact.contextID)
                        contextIDs.add(itemFact.contextID)
                        itemIssuesELRs[itemName].add((filingELR, ugtELR))
    
                    msg = [_("Financial statement calculation missing relationships from total concept to item concepts that are in us-gaap taxonomy.  "),
                           _("\n\nTotal concept: \n%(conceptSum)s.  ")]                   
                    args = {"conceptSum": totalConcept.qname}
                    if len(filingELRs) == 1:
                        msg.append(_("\n\nfiling schedule link role: \n%(filingLinkrole)s. "))
                        args["filingLinkrole"] = filingELR
                    if len(ugtELRs) == 1:
                        msg.append(_("\n\nus-gaap calc link role: \n%(usgaapLinkrole)s. "))
                        args["usgaapLinkrole"] = ugtELR
                    if len(filingELRs) == 1 and len(ugtELRs) == 1:
                        msg.append(_("\n\nSummation items missing: \n"))
                    for i, itemName in enumerate(sorted(itemIssuesELRs.keys())):
                        for j, itemIssueELRs in enumerate(sorted(itemIssuesELRs[itemName])):
                            filingELR, ugtELR = itemIssueELRs
                            if j == 0:
                                argName = "missingConcept_{0}".format(i)
                                if len(filingELRs) == 1 and len(ugtELRs) == 1:
                                    msg.append(_("\n%({0})s.  ").format(argName))
                                else:
                                    msg.append(_("\n\nSummation item: %({0})s.  ").format(argName))
                                args[argName] = itemFact.qname
                            if len(filingELRs) > 1:
                                argName = "filingLinkrole_{0}_{1}".format(i,j)
                                msg.append(_("\n   filing schedule: %({0})s. ").format(argName))
                                args[argName] = filingELR
                            if len(ugtELRs) > 1:
                                argName = "usgaapLinkrole_{0}_{1}".format(i,j)
                                msg.append(_("\n   us-gaap linkrole: %({0})s. ").format(argName))
                                args[argName] = ugtELR
                        msg.append(_("\n\nCorresponding facts in contexts: \n%(contextIDs)s\n"))
                        args["contextIDs"] = ", ".join(sorted(contextIDs))
                    val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG:missingCalculation",
                        ''.join(msg),
                        **args)
                    issues = []
                       

    del val.linroleDefinitionIsDisclosure
    del val.linkroleDefinitionStatementSheet
    if hasattr(val, 'usgaapDeprecations'):
        del val.usgaapDeprecations
    if hasattr(val, 'usaapCalculations'):
        del val.usgaapCalculations
    
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
