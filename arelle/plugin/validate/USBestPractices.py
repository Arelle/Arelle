'''
See COPYRIGHT.md for copyright information.
'''

# changed from reporting locs to reporting relationships: HF 2020-06-23

from arelle import PluginManager
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelValue import qname
from arelle.Version import copyrightLabel
from arelle.XmlValidate import UNVALIDATED, VALID
from arelle import Locale, ModelXbrl, XbrlConst
from arelle.FileSource import openFileSource, openFileStream, saveFile
import os, io, re, json, time
from math import isfinite
from collections import defaultdict

# ((year, ugtNamespace, ugtDocLB, ugtEntryPoint) ...)
ugtDocs = ({"year": 2012,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2012-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2012/us-gaap-2012-01-31.zip/us-gaap-2012-01-31/elts/us-gaap-doc-2012-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2012/us-gaap-2012-01-31.zip/us-gaap-2012-01-31/entire/us-gaap-entryPoint-std-2012-01-31.xsd",
            },
           {"year": 2013,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2013-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2013/us-gaap-2013-01-31.zip/us-gaap-2013-01-31/elts/us-gaap-doc-2013-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2013/us-gaap-2013-01-31.zip/us-gaap-2013-01-31/entire/us-gaap-entryPoint-std-2013-01-31.xsd",
            },
           {"year": 2014,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2014-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2014/us-gaap-2014-01-31.zip/us-gaap-2014-01-31/elts/us-gaap-doc-2014-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2014/us-gaap-2014-01-31.zip/us-gaap-2014-01-31/entire/us-gaap-entryPoint-std-2014-01-31.xsd",
            },
           {"year": 2015,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2015-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2015/us-gaap-2015-01-31.zip/us-gaap-2015-01-31/elts/us-gaap-doc-2015-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2015/us-gaap-2015-01-31.zip/us-gaap-2015-01-31/entire/us-gaap-entryPoint-std-2015-01-31.xsd",
            },
           {"year": 2016,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2016-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2016/us-gaap-2016-01-31.zip/us-gaap-2016-01-31/elts/us-gaap-doc-2016-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2016/us-gaap-2016-01-31.zip/us-gaap-2016-01-31/entire/us-gaap-entryPoint-std-2016-01-31.xsd",
            },
           {"year": 2017,
            "namespace": "http://fasb.org/us-gaap/2017-01-31",
            "name": "us-gaap",
            "docLB": "http://xbrl.fasb.org/us-gaap/2017/us-gaap-2017-01-31.zip/us-gaap-2017-01-31/elts/us-gaap-doc-2017-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2017/us-gaap-2017-01-31.zip/us-gaap-2017-01-31/entire/us-gaap-entryPoint-std-2017-01-31.xsd",
            },
           {"year": 2018,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2018-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2018/us-gaap-2018-01-31.zip/us-gaap-2018-01-31/elts/us-gaap-doc-2018-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2018/us-gaap-2018-01-31.zip/us-gaap-2018-01-31/entire/us-gaap-entryPoint-std-2018-01-31.xsd",
            },
           {"year": 2018,
            "name": "srt",
            "namespace": "http://fasb.org/srt/2018-01-31",
            "docLB": "http://xbrl.fasb.org/srt/2018/srt-2018-01-31.zip/srt-2018-01-31/elts/srt-doc-2018-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/srt/2018/srt-2018-01-31.zip/srt-2018-01-31/entire/srt-entryPoint-std-2018-01-31.xsd",
            },
           {"year": 2019,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2019-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2019/us-gaap-2019-01-31.zip/us-gaap-2019-01-31/elts/us-gaap-doc-2019-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2019/us-gaap-2019-01-31.zip/us-gaap-2019-01-31/entire/us-gaap-entryPoint-std-2019-01-31.xsd",
            },
           {"year": 2019,
            "name": "srt",
            "namespace": "http://fasb.org/srt/2019-01-31",
            "docLB": "http://xbrl.fasb.org/srt/2019/srt-2019-01-31.zip/srt-2019-01-31/elts/srt-doc-2019-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/srt/2019/srt-2019-01-31.zip/srt-2019-01-31/entire/srt-entryPoint-std-2019-01-31.xsd",
            },
           {"year": 2020,
            "name": "us-gaap",
            "namespace": "http://fasb.org/us-gaap/2020-01-31",
            "docLB": "http://xbrl.fasb.org/us-gaap/2020/us-gaap-2020-01-31.zip/us-gaap-2020-01-31/elts/us-gaap-doc-2020-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/us-gaap/2020/us-gaap-2020-01-31.zip/us-gaap-2020-01-31/entire/us-gaap-entryPoint-std-2020-01-31.xsd",
            },
           {"year": 2020,
            "name": "srt",
            "namespace": "http://fasb.org/srt/2020-01-31",
            "docLB": "http://xbrl.fasb.org/srt/2020/srt-2020-01-31.zip/srt-2020-01-31/elts/srt-doc-2020-01-31.xml",
            "entryXsd": "http://xbrl.fasb.org/srt/2020/srt-2020-01-31.zip/srt-2020-01-31/entire/srt-entryPoint-std-2020-01-31.xsd",
            },
           )

def setup(val, *args, **kwargs):
    if not val.validateLoggingSemantic:  # all checks herein are SEMANTIC
        return

    val.linroleDefinitionIsDisclosure = re.compile(r"-\s+Disclosure\s+-\s",
                                                   re.IGNORECASE)
    val.linkroleDefinitionStatementSheet = re.compile(r"[^-]+-\s+Statement\s+-\s+.*", # no restriction to type of statement
                                                      re.IGNORECASE)
    val.ugtNamespace = None
    cntlr = val.modelXbrl.modelManager.cntlr
    # load deprecated concepts for filed year of us-gaap
    for ugt in ugtDocs:
        ugtNamespace = ugt["namespace"]
        if ugtNamespace in val.modelXbrl.namespaceDocs and len(val.modelXbrl.namespaceDocs[ugtNamespace]) > 0:
            val.ugtNamespace = ugtNamespace
            usgaapDoc = val.modelXbrl.namespaceDocs[ugtNamespace][0]
            deprecationsJsonFile = usgaapDoc.filepathdir + os.sep + "deprecated-concepts.json"
            file = None
            try:
                file = openFileStream(cntlr, deprecationsJsonFile, 'rt', encoding='utf-8')
                val.usgaapDeprecations = json.load(file)
                file.close()
            except Exception:
                if file:
                    file.close()
                val.modelXbrl.modelManager.addToLog(_("loading {} {} deprecated concepts into cache").format(ugt["name"], ugt["year"]))
                startedAt = time.time()
                ugtDocLB = ugt["docLB"]
                val.usgaapDeprecations = {}
                # load without SEC/EFM validation (doc file would not be acceptable)
                priorValidateDisclosureSystem = val.modelXbrl.modelManager.validateDisclosureSystem
                val.modelXbrl.modelManager.validateDisclosureSystem = False
                deprecationsInstance = ModelXbrl.load(val.modelXbrl.modelManager,
                      # "http://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-doc-2012-01-31.xml",
                      # load from zip (especially after caching) is incredibly faster
                      openFileSource(ugtDocLB, cntlr),
                      _("built deprecations table in cache"))
                val.modelXbrl.modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
                if deprecationsInstance is None:
                    val.modelXbrl.error("arelle:notLoaded",
                        _("%(name)s documentation not loaded: %(file)s"),
                        modelXbrl=val, file=os.path.basename(ugtDocLB), name=ugt["name"])
                else:
                    # load deprecations
                    for labelRel in deprecationsInstance.relationshipSet(XbrlConst.conceptLabel).modelRelationships:
                        modelDocumentation = labelRel.toModelObject
                        conceptName = labelRel.fromModelObject.name
                        if modelDocumentation.role == 'http://www.xbrl.org/2009/role/deprecatedLabel':
                            val.usgaapDeprecations[conceptName] = (val.usgaapDeprecations.get(conceptName, ('',''))[0], modelDocumentation.text)
                        elif modelDocumentation.role == 'http://www.xbrl.org/2009/role/deprecatedDateLabel':
                            val.usgaapDeprecations[conceptName] = (modelDocumentation.text, val.usgaapDeprecations.get(conceptName, ('',''))[1])
                    jsonStr = str(json.dumps(val.usgaapDeprecations, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                    saveFile(cntlr, deprecationsJsonFile, jsonStr)  # 2.7 gets unicode this way
                    deprecationsInstance.close()
                    del deprecationsInstance # dereference closed modelXbrl
                val.modelXbrl.profileStat(_("build us-gaap deprecated concepts cache"), time.time() - startedAt)
            ugtCalcsJsonFile = usgaapDoc.filepathdir + os.sep + "ugt-calculations.json"
            ugtDefaultDimensionsJsonFile = usgaapDoc.filepathdir + os.sep + "ugt-default-dimensions.json"
            file = None
            try:
                file = openFileStream(cntlr, ugtCalcsJsonFile, 'rt', encoding='utf-8')
                val.usgaapCalculations = json.load(file)
                file.close()
                file = openFileStream(cntlr, ugtDefaultDimensionsJsonFile, 'rt', encoding='utf-8')
                val.usgaapDefaultDimensions = json.load(file)
                file.close()
            except Exception:
                if file:
                    file.close()
                val.modelXbrl.modelManager.addToLog(_("loading {} {} calculations and default dimensions into cache").format(ugt["name"], ugt["year"]))
                startedAt = time.time()
                ugtEntryXsd = ugt["entryXsd"]
                val.usgaapCalculations = {}
                val.usgaapDefaultDimensions = {}
                # load without SEC/EFM validation (doc file would not be acceptable)
                priorValidateDisclosureSystem = val.modelXbrl.modelManager.validateDisclosureSystem
                val.modelXbrl.modelManager.validateDisclosureSystem = False
                calculationsInstance = ModelXbrl.load(val.modelXbrl.modelManager,
                      # "http://xbrl.fasb.org/us-gaap/2012/entire/us-gaap-entryPoint-std-2012-01-31.xsd",
                      # load from zip (especially after caching) is incredibly faster
                      openFileSource(ugtEntryXsd, cntlr),
                      _("built us-gaap calculations cache"))
                val.modelXbrl.modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
                if calculationsInstance is None:
                    val.modelXbrl.error("arelle:notLoaded",
                        _("US-GAAP calculations not loaded: %(file)s"),
                        modelXbrl=val, file=os.path.basename(ugtEntryXsd))
                else:
                    # load calculations
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
                    jsonStr = str(json.dumps(val.usgaapCalculations, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                    saveFile(cntlr, ugtCalcsJsonFile, jsonStr)  # 2.7 gets unicode this way
                    # load default dimensions
                    for defaultDimRel in calculationsInstance.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
                        if isinstance(defaultDimRel.fromModelObject, ModelConcept) and isinstance(defaultDimRel.toModelObject, ModelConcept):
                            val.usgaapDefaultDimensions[defaultDimRel.fromModelObject.name] = defaultDimRel.toModelObject.name
                    jsonStr = str(json.dumps(val.usgaapDefaultDimensions, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
                    saveFile(cntlr, ugtDefaultDimensionsJsonFile, jsonStr)  # 2.7 gets unicode this way
                    calculationsInstance.close()
                    del calculationsInstance # dereference closed modelXbrl
                val.modelXbrl.profileStat(_("build us-gaap calculations and default dimensions cache"), time.time() - startedAt)
            break
    val.deprecatedFactConcepts = defaultdict(list)
    val.deprecatedDimensions = defaultdict(list)
    val.deprecatedMembers = defaultdict(list)

def factCheck(val, fact, *args, **kwargs):
    concept = fact.concept
    context = fact.context
    if concept is None or context is None or not val.validateLoggingSemantic:
        return # not checkable

    try:
        if fact.isNumeric:
            # 2.3.3 additional unit tests beyond UTR spec
            unit = fact.unit
            if unit is not None and concept.type is not None and val.validateUTR:
                typeName = concept.type.name
                if typeName == "perUnitItemType" and any(m.namespaceURI == XbrlConst.iso4217 or
                                                         m in (XbrlConst.qnXbrliPure, XbrlConst.qnXbrliShares)
                                                         for m in unit.measures[1]):
                    val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG.2.3.3.perUnitItemType",
                        _("PureItemType fact %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s has disallowed unit denominator %(denominator)s"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                        value=fact.effectiveValue, denominator=", ".join((str(m) for m in unit.measures[1])))

            if not fact.isNil and getattr(fact, "xValue", None) is not None:

                # 2.4.1 decimal disagreement
                if fact.decimals and fact.decimals != "INF":
                    vf = float(fact.value)
                    if isfinite(vf):
                        dec = int(fact.decimals)
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
        if concept.qname.namespaceURI == val.ugtNamespace:
            if concept.name in val.usgaapDeprecations:
                val.deprecatedFactConcepts[concept].append(fact)
        elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
            val.deprecatedFactConcepts[concept].append(fact)
        if fact.isItem and fact.context is not None:
            for dimConcept, modelDim in fact.context.segDimValues.items():
                if dimConcept.qname.namespaceURI == val.ugtNamespace:
                    if dimConcept.name in val.usgaapDeprecations:
                        val.deprecatedDimensions[dimConcept].append(fact)
                elif dimConcept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
                    val.deprecatedDimensions[dimConcept].append(fact)
                if modelDim.isExplicit:
                    member = modelDim.member
                    if member is not None:
                        if member.qname.namespaceURI == val.ugtNamespace:
                            if member.name in val.usgaapDeprecations:
                                val.deprecatedMembers[member].append(fact)
                        elif member.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
                            val.deprecatedMembers[member].append(fact)
    except Exception as err:
        val.modelXbrl.log('WARNING-SEMANTIC', "US-BPG.testingException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested due to: %(err)s"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, err=err)

def final(val, conceptsUsed, *args, **kwargs):
    if not val.validateLoggingSemantic:  # all checks herein are SEMANTIC
        return
    ugtNamespace = val.ugtNamespace
    standardTaxonomiesDict = val.disclosureSystem.standardTaxonomiesDict
    startedAt = time.time()
    for depType, depItems in (("Concept", val.deprecatedFactConcepts),
                              ("Dimension", val.deprecatedDimensions),
                              ("Member", val.deprecatedMembers)):
        for concept, facts in depItems.items():
            if concept.qname.namespaceURI == ugtNamespace:
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

    # check for unused extension concepts
    dimensionDefaults = set()
    def defaultParentCheck(mem, ELR=None):
        for rel in val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).toModelObject(mem):
            memParent = rel.fromModelObject
            isCycle = memParent in dimensionDefaults
            dimensionDefaults.add(memParent)
            if not isCycle:
                defaultParentCheck(memParent, rel.linkrole)
    for defaultMemConcept in val.modelXbrl.dimensionDefaultConcepts.values():
        dimensionDefaults.add(defaultMemConcept)
        # also add any domain or intermediate parents of dimension default in any ELR as they likely will be unused
        defaultParentCheck(defaultMemConcept)
    extensionConceptsUnused = [concept
                               for qn, concept in val.modelXbrl.qnameConcepts.items()
                               if concept.isItem and
                               qn.namespaceURI not in standardTaxonomiesDict
                               if concept not in conceptsUsed and
                                  # don't report dimension that has a default member
                                  concept not in val.modelXbrl.dimensionDefaultConcepts and
                                  # don't report default members
                                  concept not in dimensionDefaults and
                                  (concept.isDimensionItem or
                                   (concept.type is not None and concept.type.isDomainItemType) or
                                   # this or branch only pertains to fact concepts
                                   not concept.isAbstract)
                               ]
    if extensionConceptsUnused:
        for concept in sorted(extensionConceptsUnused, key=lambda c: str(c.qname)):
            val.modelXbrl.log('INFO-SEMANTIC', "US-BPG.1.7.1.unusedExtensionConcept",
                _("Company extension concept is unused: %(concept)s"),
                modelObject=concept, concept=concept.qname)

    # check for unused concept relationships of standard taxonomy elements
    standardRelationships = val.modelXbrl.relationshipSet((XbrlConst.parentChild, XbrlConst.summationItem, XbrlConst.dimensionDomain, XbrlConst.domainMember, XbrlConst.dimensionDefault))
    standardConceptsUnused = defaultdict(set) # dict by concept of relationship where unused
    standardConceptsDeprecated = defaultdict(set)
    for rel in standardRelationships.modelRelationships:
        for concept in (rel.fromModelObject, rel.toModelObject):
            if (isinstance(concept, ModelConcept) and concept.qname is not None and
                concept.qname.namespaceURI in standardTaxonomiesDict and
                concept not in conceptsUsed):
                if (not concept.isAbstract or
                    concept.isDimensionItem or
                    (concept.type is not None and concept.type.isDomainItemType)):
                    standardConceptsUnused[concept].add(rel)
                elif ((concept.qname.namespaceURI == ugtNamespace and
                       concept.name in val.usgaapDeprecations) or
                      concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate")):
                    # catches abstract deprecated concepts in linkbases
                    standardConceptsDeprecated[concept].add(rel)
    for concept, rels in standardConceptsUnused.items():
        if concept.qname.namespaceURI == ugtNamespace and concept.name in val.usgaapDeprecations:
            deprecation = val.usgaapDeprecations[concept.name]
            val.modelXbrl.log('INFO-SEMANTIC', "FASB:deprecatedConcept",
                _("Unused concept %(concept)s has extension relationships and was deprecated on %(date)s: %(documentation)s"),
                modelObject=rels, concept=concept.qname,
                date=deprecation[0], documentation=deprecation[1])
        elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
            val.modelXbrl.log('INFO-SEMANTIC', "FASB:deprecatedConcept",
                _("Unused concept %(concept)s has extension relationships was deprecated on %(date)s"),
                modelObject=rels, concept=concept.qname,
                date=concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"))
        elif (concept not in val.modelXbrl.dimensionDefaultConcepts and # don't report dimension that has a default member
              concept not in dimensionDefaults and # don't report default members
              (concept.isDimensionItem or
              (concept.type is not None and concept.type.isDomainItemType) or
              # this or branch only pertains to fact concepts
              not concept.isAbstract)):
            val.modelXbrl.log('INFO-SEMANTIC', "US-BPG.1.7.1.unusedStandardConceptInExtensionRelationship",
                _("Company extension relationships of unused standard concept: %(concept)s"),
                modelObject=rels, concept=concept.qname)
    for concept, rels in standardConceptsDeprecated.items():
        if concept.qname.namespaceURI == ugtNamespace and concept.name in val.usgaapDeprecations:
            deprecation = val.usgaapDeprecations[concept.name]
            val.modelXbrl.log('INFO-SEMANTIC', "FASB:deprecatedConcept",
                _("Concept %(concept)s has extension relationships and was deprecated on %(date)s: %(documentation)s"),
                modelObject=rels, concept=concept.qname,
                date=deprecation[0], documentation=deprecation[1])
        elif concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"):
            val.modelXbrl.log('INFO-SEMANTIC', "FASB:deprecatedConcept",
                _("Concept %(concept)s has extension relationships was deprecated on %(date)s"),
                modelObject=rels, concept=concept.qname,
                date=concept.get("{http://fasb.org/us-gaap/attributes}deprecatedDate"))
    val.modelXbrl.profileStat(_("validate US-BGP unused concepts"), time.time() - startedAt)

    del standardRelationships, extensionConceptsUnused, standardConceptsUnused, standardConceptsDeprecated, dimensionDefaults
    del val.deprecatedFactConcepts
    del val.deprecatedDimensions
    del val.deprecatedMembers

    if hasattr(val, 'usgaapCalculations'):
        """
        The UGT calcuations are loaded and cached from the US-GAAP.

        UGT calculation link roles are presumed to (and do) reflect the statement sheets they
        correspond to, and therefore each set of UGT summation-item arc-sets are cached and
        identified as to whether a statement sheet or other.

        A concept that has facts in the instance and is a total concept with summation-item
        arc-sets in UGT is examined if it appears on any submission face statement
        parent-child link role.  (No examination is made if the concept is only on
        non-face statements of the submission, even if on some UGT face statement.)

        Each UGT link role that has facts reported with a total concept has its
        summation-item arc-sets examained to see if any compatible pair of UGT total
        and item facts in the instance document do not have any submission calculation
        sibling or descendant relationship.  (Compatible here only means context and unit
        equivalence.)  Addition of descendancy in the submission was needed to avoid
        excessive false positives.  Each such issue is reported by filing parent-child
        link role, UGT calculation link role, contributing item, and total item.  The
        report of these items is sorted by contributing item.
        """
        startedAt = time.time()
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
        val.modelXbrl.profileStat(_("validate US-BGP missing calcs"), time.time() - startedAt)


    if hasattr(val, 'usgaapDefaultDimensions'):
        """
        The UGT default dimensions are loaded and cached from US-GAAP.

        Question E.16 (Updated 02/05/2013):

        Filers SHOULD also avoid creating new domains or changing default member elements for pre-defined dimensions.
        """
        for defaultDimRel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:
            if (isinstance(defaultDimRel.fromModelObject, ModelConcept) and isinstance(defaultDimRel.toModelObject, ModelConcept) and
                defaultDimRel.fromModelObject.qname.namespaceURI == ugtNamespace and
                defaultDimRel.fromModelObject.name in val.usgaapDefaultDimensions and
                (defaultDimRel.toModelObject.qname.namespaceURI not in standardTaxonomiesDict or
                 defaultDimRel.toModelObject.name != val.usgaapDefaultDimensions[defaultDimRel.fromModelObject.name])):
                if defaultDimRel.toModelObject.qname.namespaceURI not in standardTaxonomiesDict:
                    msgObjects = (defaultDimRel, defaultDimRel.toModelObject)
                else:
                    msgObjects = defaultDimRel
                val.modelXbrl.log('WARNING-SEMANTIC', "secStaffObservation.E.16.defaultDimension",
                    _("UGT-defined dimension %(dimension)s has extension defined default %(extensionDefault)s, predefined default is %(predefinedDefault)s"),
                    modelObject=msgObjects,
                    dimension=defaultDimRel.fromModelObject.qname,
                    extensionDefault=defaultDimRel.toModelObject.qname,
                    predefinedDefault=defaultDimRel.fromModelObject.qname.prefix + ":" + val.usgaapDefaultDimensions[defaultDimRel.fromModelObject.name])

        val.modelXbrl.profileStat(_("validate SEC staff observation E.16 dimensions"), time.time() - startedAt)

    del val.linroleDefinitionIsDisclosure
    del val.linkroleDefinitionStatementSheet
    del val.ugtNamespace
    if hasattr(val, 'usgaapDeprecations'):
        del val.usgaapDeprecations
    if hasattr(val, 'usgaapDefaultDimensions'):
        del val.usgaapDefaultDimensions
    if hasattr(val, 'usgaapCalculations'):
        del val.usgaapCalculations

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate XBRL-US Best Practice Guidance',
    'version': '0.9',
    'description': '''XBRL-US Best Practice Guidance Validation.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final
}
