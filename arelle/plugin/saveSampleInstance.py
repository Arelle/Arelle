'''
Save Sample Instance is an example of a plug-in to both GUI menu and command line/web service
that will use a us-gaap style presentation tree to save sample instance facts.

See COPYRIGHT.md for copyright information.

uses exrex for regular expressions (pip install exrex), note exrex is GPL 3 licensed
if exrex not installed, pattern facets don't generate valid pattern

sample cmd line args:
  --plugins saveSampleInstance.py
  -f /Users/hermf/Documents/mvsl/projects/DataAct/daims-20160331.xsd
  --save-sample-instance /Users/hermf/Documents/mvsl/projects/DataAct/sample.xbrl
  --separate-linkrole-files

If sample values of concepts are in the taxonomy, then
  --concept-sample-value
  --concept-sample-unit
specifies a search order for reference parts and/or labels as follows:
  multiple options are separated by solidus "|"
  a label option is label:role or label:role (lang)
  (only the last path segment of the label role)
  a reference option is reference:part
  (only the local name of the part)

To specify entity identifier scheme:

  --sample-entity-scheme http://foo.com/scheme
'''

import os, io, re
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle import Locale, XbrlConst, ModelXbrl, XmlUtil
from arelle.ModelValue import qname
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ValidateXbrlDimensions import loadDimensionDefaults
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import conceptLabel, conceptReference, qnXsiNil
from lxml import etree
try:
    import exrex
except ImportError:
    exrex = None

resourceParsePattern = re.compile(r"(label|reference):([\w][\w\s#+-:/]+[\w#+-/])(\s*[(]([^)]+)[)])?$")

def generateSampleInstance(dts, instanceFilename,
                           separateLinkroleFiles=None,
                           conceptSampleValue=None,
                           conceptSampleUnit=None,
                           conceptSampleScheme=None):
    if dts.fileSource.isArchive:
        return
    dts.conceptSampleValue = conceptSampleValue
    dts.conceptSampleUnit = conceptSampleUnit
    dts.conceptSampleScheme = conceptSampleScheme
    if conceptSampleUnit is not None:
        from arelle.ValidateUtr import loadUtr
        loadUtr(dts)

    # requires dimensino defaults
    loadDimensionDefaults(dts)
    # use presentation relationships for broader and narrower concepts
    arcrole = XbrlConst.parentChild
    # sort URIs by definition
    linkroleUris = []
    relationshipSet = dts.relationshipSet(arcrole)
    sampleInstance = None
    if not separateLinkroleFiles:
        dts.createInstance(instanceFilename)
    if relationshipSet:
        for linkroleUri in relationshipSet.linkRoleUris:
            modelRoleTypes = dts.roleTypes.get(linkroleUri)
            if modelRoleTypes:
                roledefinition = (modelRoleTypes[0].genLabel(strip=True) or modelRoleTypes[0].definition or linkroleUri)
            else:
                roledefinition = linkroleUri
            linkroleUris.append((roledefinition, linkroleUri))
        linkroleUris.sort()

        # for each URI in definition order
        for roledefinition, linkroleUri in linkroleUris:
            if separateLinkroleFiles:
                sampleFile = "{0[0]}_{1}{0[1]}".format(os.path.splitext(instanceFilename),
                                                       os.path.basename(linkroleUri))
                dts.createInstance(sampleFile)
            linkRelationshipSet = dts.relationshipSet(arcrole, linkroleUri)
            for rootConcept in linkRelationshipSet.rootConcepts:
                genFact(dts, rootConcept, None, arcrole, linkRelationshipSet, 1, set(),
                        {"inCube": False,
                         "dims":{}, "contexts":{},
                         "lineItems":False})
            if dts and separateLinkroleFiles:
                dts.saveInstance(overrideFilepath=sampleFile)
                dts.info("info:savedSampleInstance",
                         _("Instance file written for %(entryFile)s in file %(instanceFile)s."),
                         modelObject=dts,
                         entryFile=dts.uri, instanceFile=dts.modelDocument.basename)

    if dts:
        if not separateLinkroleFiles:
            dts.saveInstance(overrideFilepath=instanceFilename)
            dts.info("info:savedSampleInstance",
                     _("Instance file written for %(entryFile)s in file %(instanceFile)s."),
                     modelObject=dts,
                     entryFile=dts.uri, instanceFile=instanceFilename)
    elif not separateLinkroleFiles:
        dts.info("info:noSampleInstance",
                 _("Instance file not written (no presentation line items) for %(entryFile)s in file %(instanceFile)s."),
                 modelObject=dts,
                 entryFile=dts.uri, instanceFile=instanceFilename)

    del dts.conceptSampleValue, conceptSampleUnit, conceptSampleScheme

sampleDomainValues = {
    "number": {1:"1", 2:"2", 3:"3"},
    "str": {1:"a1", 2:"b2", 3:"c3"}
    }

sampleDataValues = {
    1: {"periodStart": XmlUtil.datetimeValue("2016-01-01"),
        "periodEnd": XmlUtil.datetimeValue("2016-03-31", addOneDay=True),
        "date": "2016-03-03",
        "dateTime": "2016-03-03T12:00:00",
        "duration": "P1D",
        "gYear": "2016",
        "gMonth": "--03",
        "str": "abc"},
    2: {"periodStart": XmlUtil.datetimeValue("2016-04-01"),
        "periodEnd": XmlUtil.datetimeValue("2016-06-30", addOneDay=True),
        "date": "2016-06-04",
        "dateTime": "2016-06-04T13:00:00",
        "duration": "P1D",
        "gMonth": "--06",
        "gYear": "2016",
        "str": "def"},
    3: {"periodStart": XmlUtil.datetimeValue("2016-07-01"),
        "periodEnd": XmlUtil.datetimeValue("2016-09-30", addOneDay=True),
        "date": "2016-09-05",
        "dateTime": "2016-09-05T15:00:00",
        "duration": "P1D",
        "gMonth": "--09",
        "gYear": "2016",
        "str": "ghi"},
    }

def genSampleValue(sampVals, concept):
    modelXbrl = concept.modelDocument.modelXbrl
    if modelXbrl.conceptSampleValue is not None:
        sampleValues = concept.modelDocument.modelXbrl.conceptSampleValue.split("|")
        for v in sampleValues:
            m = resourceParsePattern.match(v)
            if m:
                _resourceType = m.group(1)
                _resourceRole = "/" + m.group(2) # last path seg of role
                _referencePart = m.group(2)
                _resourceLang = m.group(4) # lang or part
                if _resourceType == "label":
                    for lblRel in modelXbrl.relationshipSet(XbrlConst.conceptLabel).fromModelObject(concept):
                        if lblRel.toModelObject.role.endswith(_resourceRole) and (
                            not _resourceLang or lblRel.toModelObject.xmlLang == _resourceLang):
                            return lblRel.toModelObject.textValue
                elif _resourceType == "reference":
                    for refRel in modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(concept):
                        for refPart in refRel.toModelObject.iterchildren():
                            if refPart.localName == _referencePart:
                                value = refPart.stringValue
                                # fix up values
                                if concept.baseXsdType == "date" and len(value) == 8 and value.isnumeric():
                                    value = value[0:4] + "-" + value[4:6] + "-" + value[6:]
                                # allow dates to be missing the "-"
                                return value
    if concept.isNumeric:
        try: # try to get an enumeration
            facets = concept.type.facets
            if facets and "enumeration" in facets:
                value = sorted(facets["enumeration"])[0]
            elif "minInclusive" in facets:
                value = facets["minInclusive"]
            else:
                value = 123
        except (AttributeError, IndexError, TypeError): # no enumeration value
            value = 123
    elif concept.baseXsdType == "date":
        value = sampVals["date"]
    elif concept.baseXsdType in ("dateTime", "XBRLI_DATEUNION"):
        value = sampVals["dateTime"]
    elif concept.baseXsdType == "duration":
        value = sampVals["duration"]
    elif concept.baseXsdType == "gYear":
        value = sampVals["gYear"]
    elif concept.baseXsdType == "gMonth":
        value = sampVals["gMonth"]
    elif concept.baseXsdType == "boolean":
        value = "true"
    else:
        try: # try to get an enumeration
            facets = concept.type.facets
            if facets and "enumeration" in facets:
                value = sorted(facets["enumeration"])[0]
            elif "pattern" in facets and exrex is not None:
                value = exrex.getone(facets["pattern"].pattern) # pattern facet is a compiled pattern
            elif "length" in facets:
                l = facets["length"]
                value = (sampVals["str"] * int((l+2)/3))[0:l]
            elif "maxLength" in facets:
                value = (sampVals["str"] * 100)[0:facets["maxLength"]]
            else:
                value = sampVals["str"]
        except (AttributeError, IndexError, TypeError): # no enumeration value
            value = sampVals["str"]
    return value

def genSampleUtrUnitId(concept):
    modelXbrl = concept.modelDocument.modelXbrl
    if modelXbrl.conceptSampleUnit is not None:
        sampleUnits = concept.modelDocument.modelXbrl.conceptSampleUnit.split("|")
        for u in sampleUnits:
            m = resourceParsePattern.match(u)
            if m:
                _resourceType = m.group(1)
                _resourceRole = "/" + m.group(2) # last path seg of role
                _referencePart = m.group(2)
                _resourceLang = m.group(4) # lang or part
                if _resourceType == "label":
                    for lblRel in modelXbrl.relationshipSet(XbrlConst.conceptLabel).fromModelObject(concept):
                        if lblRel.toModelObject.role.endswith(_resourceRole) and (
                            not _resourceLang or lblRel.toModelObject.xmlLang == _resourceLang):
                            return lblRel.toModelObject.textValue
                elif _resourceType == "reference":
                    for refRel in modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(concept):
                        for refPart in refRel.toModelObject.iterchildren():
                            if refPart.localName == _referencePart:
                                value = refPart.stringValue
                                # fix up values
                                if concept.baseXsdType == "date" and len(value) == 8 and value.isnumeric():
                                    value = value[0:4] + "-" + value[4:6] + "-" + value[6:]
                                # allow dates to be missing the "-"
                                return value

def factConceptTypedDims(factConcept, relationshipSet):
    # find cube
    def tables(concept):
        for rel in relationshipSet.toModelObject(concept):
            parent = rel.fromModelObject
            if parent.isHypercubeItem:
                return [parent]
            parentTable = tables(parent)
            if parentTable:
                return parentTable
        return []
    return [(rel.toModelObject, rel.toModelObject.typedDomainElement)
            for _table in tables(factConcept)
            for rel in relationshipSet.fromModelObject(_table)
            if rel.toModelObject.isTypedDimension]

def genFact(dts, concept, preferredLabel, arcrole, relationshipSet, level, visited, elrInfo):
    try:
        if concept is not None:
            if concept.isHypercubeItem:
                elrInfo["inCube"] = level
                elrInfo["dims"] = {}
                elrInfo["lineItems"] =False
                elrInfo["contexts"] = {}
            elif concept.isDimensionItem:
                elrInfo["currentDim"] = concept
                if concept.isTypedDimension:
                    elrInfo["dims"][concept.qname] = (concept, concept.typedDomainElement)
                    elrInfo["domainIter"] = 1
                    if concept.typedDomainElement.isNumeric:
                        elrInfo["domainType"] = "numeric"
                    else:
                        elrInfo["domainType"] = "str" # may need to add more types such as dates
            elif concept.name.endswith("Member") or concept.name.endswith("_member"): # don't generate entries for default dim (Domain) (for now)
                dimConcept = elrInfo["currentDim"]
                if dimConcept.qname not in elrInfo["dims"]:
                    elrInfo["dims"][dimConcept.qname] = (dimConcept, concept)
            else:
                if concept.name.endswith("LineItems") or concept.name.endswith("_line_items"):
                    elrInfo["lineItems"] = True
                elif ((not elrInfo["inCube"] or # before any hypercube
                       elrInfo["lineItems"]) # in Cube and within Line Items
                      and not concept.isAbstract): # or within line items
                    contextKey = concept.periodType
                    nilTypedDims = []
                    if not elrInfo["inCube"]: # out-of-cube concepts, check for typed dim in (subsequently-encountered) cube
                        nilTypedDims = factConceptTypedDims(concept, relationshipSet)
                        if nilTypedDims:
                            contextKey += "," + ",".join(sorted([d[0].name for d in nilTypedDims]))
                    # generate a fact
                    sampVals = sampleDataValues[elrInfo.get("domainIter",1)] # use first entry if no domain iter
                    if contextKey not in elrInfo["contexts"]:
                        qnameDims = {}
                        for _dimConcept, _domConcept in elrInfo["dims"].values():
                            if _dimConcept.isExplicitDimension:
                                _memVal = _domConcept.qname
                            else:
                                if _domConcept.type is not None and not _domConcept.isNumeric:
                                    _memEltVal = genSampleValue(sampVals, _domConcept)
                                else:
                                    _memEltVal = sampleDomainValues[elrInfo["domainType"]][elrInfo["domainIter"]]
                                _memVal = XmlUtil.addChild(dts.modelDocument.xmlRootElement,
                                                         _domConcept.qname,
                                                         text=_memEltVal,
                                                         appendChild=False)
                            _dimObj = DimValuePrototype(dts, None, _dimConcept.qname, _memVal, "segment")
                            qnameDims[_dimConcept.qname] = _dimObj
                        for _dimConcept, _domConcept in nilTypedDims:
                            _memVal = XmlUtil.addChild(dts.modelDocument.xmlRootElement,
                                                     _domConcept.qname, attributes=((qnXsiNil,"true"),),
                                                     appendChild=False)
                            _dimObj = DimValuePrototype(dts, None, _dimConcept.qname, _memVal, "segment")
                            qnameDims[_dimConcept.qname] = _dimObj
                        elrInfo["contexts"][contextKey] = dts.createContext(
                                    dts.conceptSampleScheme or "http://www.treasury.gov",
                                    "entityId",
                                    concept.periodType,
                                    sampVals["periodStart"] if concept.periodType == "duration"
                                    else None,
                                    sampVals["periodEnd"],
                                    concept.qname, qnameDims, [], [])
                    cntx = elrInfo["contexts"][contextKey]
                    cntxId = cntx.id
                    if concept.isNumeric:
                        if concept.isMonetary:
                            unitMeasure = qname(XbrlConst.iso4217, "USD")
                            unitMeasure.prefix = "iso4217" # want to save with a recommended prefix
                            decimals = 2
                        elif concept.isShares:
                            unitMeasure = XbrlConst.qnXbrliShares
                            decimals = 0
                        else:
                            unitMeasure = XbrlConst.qnXbrliPure
                            decimals = 0
                        # check if utr unitId is specified
                        utrUnitId = genSampleUtrUnitId(concept)
                        if utrUnitId is not None:
                            _utrEntries = dts.modelManager.disclosureSystem.utrItemTypeEntries[concept.type.name]
                            if _utrEntries:
                                for _utrEntry in _utrEntries.values():
                                    if _utrEntry.unitId == utrUnitId and _utrEntry.isSimple:
                                        unitMeasure = qname(_utrEntry.nsUnit, _utrEntry.unitId)
                                        break
                        prevUnit = dts.matchUnit([unitMeasure], [])
                        if prevUnit is not None:
                            unitId = prevUnit.id
                        else:
                            newUnit = dts.createUnit([unitMeasure], [])
                            unitId = newUnit.id
                    value = genSampleValue(sampVals, concept)
                    attrs = [("contextRef", cntxId)]
                    if concept.isNumeric:
                        attrs.append(("unitRef", unitId))
                        attrs.append(("decimals", decimals))
                        value = Locale.atof(dts.locale, str(value), str.strip)
                    newFact = dts.createFact(concept.qname, attributes=attrs, text=value)
            if concept not in visited:
                visited.add(concept)
                rels = relationshipSet.fromModelObject(concept)
                lenRels = len(rels)
                iRel = 0
                iFirstLineItem = None
                while iRel <= lenRels:
                    if iRel == lenRels: # check if cube needs re-iterating
                        if iFirstLineItem is None or elrInfo.get("domainIter",0) >= 2:
                            break
                        reIterateCube = True # cube can re-iterate
                    else:
                        modelRel = rels[iRel]
                        toConcept = modelRel.toModelObject
                        reIterateCube = (toConcept.isHypercubeItem and # finished prior line items and hitting next table
                                         iFirstLineItem is not None and
                                         elrInfo["lineItems"] and 1 <= elrInfo.get("domainIter",0) < 2)
                    if reIterateCube: # repeat typed dim container
                        iRel = iFirstLineItem
                        elrInfo["domainIter"] += 1
                        elrInfo["contexts"] = {} # want new contexts for next iteration
                    isFirstLineItem = not elrInfo["lineItems"]
                    genFact(dts, toConcept, modelRel.preferredLabel, arcrole, relationshipSet, level+1, visited, elrInfo)
                    if isFirstLineItem and elrInfo["lineItems"] and elrInfo.get("domainIter",0) > 0:
                        iFirstLineItem = iRel
                    iRel += 1
                visited.remove(concept)
    except AttributeError as ex: #  bad relationship
        print ("[exception] {}".format(ex))
        return

def saveSampleInstanceMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save Sample Instance",
                     underline=0,
                     command=lambda: saveSampleInstanceMenuCommand(cntlr) )

def saveSampleInstanceMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return

        # get file name into which to save log file while in foreground thread
    instanceFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save Sample Instance"),
            initialdir=cntlr.config.setdefault("sampleInstanceFileDir","."),
            filetypes=[(_("Sample instance .xbrl"), "*.xbrl")],
            defaultextension=".xbrl")
    if not instanceFile:
        return False
    import os
    cntlr.config["sampleInstanceFileDir"] = os.path.dirname(instanceFile)
    cntlr.saveConfig()

    try:
        generateSampleInstance(cntlr.modelManager.modelXbrl, instanceFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("Sample instance generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveSampleInstanceCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-sample-instance",
                      action="store",
                      dest="sampleInstanceFile",
                      help=_("Save sample instance."))
    parser.add_option("--separate-linkrole-files",
                      action="store_true",
                      dest="separateLinkroleFiles",
                      help=_("Separate each linkrole into its own file."))
    parser.add_option("--concept-sample-value",
                      action="store",
                      dest="conceptSampleValue",
                      help=_("Sample values relationships per concept."))
    parser.add_option("--concept-sample-unit",
                      action="store",
                      dest="conceptSampleUnit",
                      help=_("Sample value's unit (UTR unitId)."))
    parser.add_option("--sample-entity-scheme",
                      action="store",
                      dest="conceptSampleScheme",
                      help=_("Sample entity identifier scheme."))

def saveSampleInstanceCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "sampleInstanceFile", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        generateSampleInstance(cntlr.modelManager.modelXbrl,
                               options.sampleInstanceFile,
                               separateLinkroleFiles=getattr(options, "separateLinkroleFiles", None),
                               conceptSampleValue=getattr(options, "conceptSampleValue", None),
                               conceptSampleUnit=getattr(options, "conceptSampleUnit", None),
                               conceptSampleScheme=getattr(options, "conceptSampleScheme", None))


__pluginInfo__ = {
    'name': 'Save Sample Instance',
    'version': '0.9',
    'description': "This plug-in saves a sample instance from a us-gaap style DTS. "
                   "It uses an ELR's LineItems to control output facts.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveSampleInstanceMenuEntender,
    'CntlrCmdLine.Options': saveSampleInstanceCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveSampleInstanceCommandLineXbrlRun,
}
