'''
See COPYRIGHT.md for copyright information.
'''
from lxml import etree
from arelle import ModelDocument
from collections import defaultdict

from arelle.ModelXbrl import ModelXbrl

DIVISOR = "*DIV*"

class UtrEntry(): # use slotted class for execution efficiency
    __slots__ = ("id", "unitId", "nsUnit", "itemType", "nsItemType", "isSimple",
                 "numeratorItemType", "nsNumeratorItemType",
                 "denominatorItemType", "nsDenominatorItemType", "symbol",
                 "status")

    def __repr__(self):
        return "utrEntry({})".format(', '.join("{}={}".format(n, getattr(self,n))
                                               for n in self.__slots__))

def loadUtr(modelXbrl, statusFilters=None): # Build a dictionary of item types that are constrained by the UTR
    """
    Parses the units from modelXbrl.modelManager.disclosureStystem.utrUrl, and sets them on
    modelXbrl.modelManager.disclosureSystem.utrItemTypeEntries

    :param modelXbrl: the loaded xbrl model
    :param statusFilters: the list of statuses to keep. If unset, 'REC' status is the default filter
    :return: None
    """
    modelManager = modelXbrl.modelManager
    if statusFilters is None:
        if modelManager.disclosureSystem.utrStatusFilters:
            statusFilters = modelManager.disclosureSystem.utrStatusFilters.split()
        else:
            statusFilters = ['REC']
    modelManager.disclosureSystem.utrItemTypeEntries = utrItemTypeEntries = defaultdict(dict)
    # print('UTR LOADED FROM '+utrUrl);
    # skip status message as it hides prior activity during which this might have just obtained symbols
    # modelManager.cntlr.showStatus(_("Loading Unit Type Registry"))
    file = None
    try:
        from arelle.FileSource import openXmlFileStream
        # normalize any relative paths to config directory
        unitDupCheck = set()
        for _utrUrl in modelManager.disclosureSystem.utrUrl: # list of URLs
            if file:
                file.close()
            file = openXmlFileStream(modelManager.cntlr, _utrUrl, stripDeclaration=True)[0]
            xmldoc = etree.parse(file)
            for unitElt in xmldoc.iter(tag="{http://www.xbrl.org/2009/utr}unit"):
                u = UtrEntry()
                u.id = unitElt.get("id")
                u.unitId = unitElt.findtext("{http://www.xbrl.org/2009/utr}unitId")
                u.nsUnit = (unitElt.findtext("{http://www.xbrl.org/2009/utr}nsUnit") or None) # None if empty entry
                u.itemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}itemType")
                u.nsItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsItemType")
                u.numeratorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}numeratorItemType")
                u.nsNumeratorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsNumeratorItemType")
                u.denominatorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}denominatorItemType")
                u.nsDenominatorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsDenominatorItemType")
                u.isSimple = all(e is None for e in (u.numeratorItemType, u.nsNumeratorItemType, u.denominatorItemType, u.nsDenominatorItemType))
                u.symbol = unitElt.findtext("{http://www.xbrl.org/2009/utr}symbol")
                u.status = unitElt.findtext("{http://www.xbrl.org/2009/utr}status")
                if u.status in statusFilters:
                    # TO DO: This indexing scheme assumes that there are no name clashes in item types of the registry.
                    (utrItemTypeEntries[u.itemType])[u.id] = u
                unitDupKey = (u.unitId, u.nsUnit, u.status)
                if unitDupKey in unitDupCheck:
                    modelXbrl.error("arelleUtrLoader:entryDuplication",
                                    "Unit Type Registry entry duplication: id %(id)s unit %(unitId)s nsUnit %(nsUnit)s status %(status)s",
                                    modelObject=modelXbrl, id=u.id, unitId=u.unitId, nsUnit=u.nsUnit, status=u.status)
                unitDupCheck.add(unitDupKey)
                if u.isSimple:
                    if not u.itemType:
                        modelXbrl.error("arelleUtrLoader:simpleDefMissingField",
                                        "Unit Type Registry simple unit definition missing item type: id %(id)s unit %(unitId)s nsUnit %(nsUnit)s status %(status)s",
                                        modelObject=modelXbrl, id=u.id, unitId=u.unitId, nsUnit=u.nsUnit, status=u.status)
                    if u.numeratorItemType or u.denominatorItemType or u.nsNumeratorItemType or u.nsDenominatorItemType:
                        modelXbrl.error("arelleUtrLoader",
                                        "Unit Type Registry simple unit definition may not have complex fields: id %(id)s unit %(unitId)s nsUnit %(nsUnit)s status %(status)s",
                                        modelObject=modelXbrl, id=u.id, unitId=u.unitId, nsUnit=u.nsUnit, status=u.status)
                else:
                    if u.symbol:
                        modelXbrl.error("arelleUtrLoader:complexDefSymbol",
                                        "Unit Type Registry complex unit definition may not have symbol: id %(id)s unit %(unitId)s nsUnit %(nsUnit)s status %(status)s",
                                        modelObject=modelXbrl, id=u.id, unitId=u.unitId, nsUnit=u.nsUnit, status=u.status)
                    if not u.numeratorItemType or not u.denominatorItemType:
                        modelXbrl.error("arelleUtrLoader:complexDefMissingField",
                                        "Unit Type Registry complex unit definition must have numerator and denominator fields: id %(id)s unit %(unitId)s nsUnit %(nsUnit)s status %(status)s",
                                        modelObject=modelXbrl, id=u.id, unitId=u.unitId, nsUnit=u.nsUnit, status=u.status)
    except (EnvironmentError,
            etree.LxmlError) as err:
        modelManager.modelXbrl.error("arelleUtrLoader:error",
                                     "Unit Type Registry Import error: %(error)s",
                                     modelObject=modelXbrl, error=err)
        etree.clear_error_log()
    if file:
        file.close()

def validateFacts(modelXbrl) -> None:
    ValidateUtr(modelXbrl).validateFacts()

def utrEntries(modelType, modelUnit):
    return ValidateUtr(modelType.modelXbrl).utrEntries(modelType, modelUnit)

def utrSymbol(modelType, unitMeasures):
    return ValidateUtr(modelType.modelXbrl).utrSymbol(unitMeasures[0], unitMeasures[1])

class ValidateUtr:
    def __init__(self, modelXbrl: ModelXbrl, messageLevel: str="ERROR", messageCode: str="utre:error-NumericFactUtrInvalid") -> None:
        self.modelXbrl = modelXbrl
        self.messageLevel = messageLevel
        self.messageCode = messageCode
        if getattr(modelXbrl.modelManager.disclosureSystem, "utrItemTypeEntries", None) is None:
            loadUtr(modelXbrl)
        self.utrItemTypeEntries = modelXbrl.modelManager.disclosureSystem.utrItemTypeEntries

    def validateFacts(self):
        modelXbrl = self.modelXbrl
        if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            modelXbrl.modelManager.cntlr.showStatus(_("Validating for Unit Type Registry").format())
            utrInvalidFacts = []
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None and concept.isNumeric:
                    unit = f.unit
                    typeMatched = False
                    if f.unitID is not None and unit is not None:  # Would have failed XBRL validation otherwise
                        unitMatched = False
                        _type = concept.type
                        while _type is not None:
                            unitMatched, typeMatched, _utrEntry = self.measuresMatch(
                                False, unit.measures[0], unit.measures[1], _type.name, _type.modelDocument.targetNamespace)
                            if typeMatched:
                                break
                            _type = _type.typeDerivedFrom
                            if isinstance(_type,list): # union type
                                _type = _type[0] # for now take first of union's types
                    if typeMatched and not unitMatched:
                        utrInvalidFacts.append(f)
            for fact in utrInvalidFacts:
                modelXbrl.log(self.messageLevel,
                              self.messageCode,
                              _("Unit %(unitID)s disallowed on fact %(element)s of type %(typeName)s"),
                              modelObject=fact, unitID=fact.unitID, element=fact.qname, typeName=fact.concept.type.name,
                              messageCodes=("utre:error-NumericFactUtrInvalid",))


    def measuresMatch(self, typeMatched, mulMeas, divMeas, typeName=None, typeNS=None, *divArgs):
        if typeNS is DIVISOR and divArgs:
            return self.measuresMatch(typeMatched, divMeas, mulMeas, *divArgs)
        if len(mulMeas) == 0 and len(divMeas) == 0 and typeName is None:
            return True, typeMatched, None
        if typeName and typeName not in self.utrItemTypeEntries: # divide element unconstrained (e.g., decimalItemType)
            if divMeas or divArgs:
                return self.measuresMatch(typeMatched, divMeas, (), *divArgs) # mul meas not constrainted
            else:
                return typeMatched, typeMatched, None
        for u in self.utrItemTypeEntries[typeName].values():
            if typeNS is None or u.nsItemType is None or typeNS == u.nsItemType:
                typeMatched = True
                if u.isSimple:
                        for i, m in enumerate(mulMeas):
                            if m.localName == u.unitId and (u.nsUnit is None or u.nsUnit == m.namespaceURI):
                                if self.measuresMatch(True, divMeas, mulMeas[:i] + mulMeas[i+1:], *divArgs)[0]:
                                    return True, True, u
                else:
                    if self.measuresMatch(True, mulMeas, divMeas, u.numeratorItemType, u.nsNumeratorItemType,
                                          u.denominatorItemType, u.nsDenominatorItemType, None, DIVISOR, *divArgs)[0]:
                        return True, True, u
        return False, typeMatched, None

    def utrEntries(self, modelType, unit):
        utrSatisfyingEntries = set()
        modelXbrl = self.modelXbrl
        _type = modelType
        while _type is not None:
            unitMatched, typeMatched, utrEntry = self.measuresMatch(
                False, unit.measures[0], unit.measures[1], _type.name, _type.modelDocument.targetNamespace)
            if typeMatched:
                if unitMatched:
                    utrSatisfyingEntries.add(utrEntry)
                break
            _type = _type.typeDerivedFrom
            if isinstance(_type,list): # union type
                _type = _type[0] # for now take first of union's types
        return utrSatisfyingEntries

    def utrSymbol(self, multMeasures, divMeasures):
        if not divMeasures:
            if not multMeasures:
                return ''
            elif len(multMeasures) == 1:
                m = multMeasures[0]
                for utrItemTypeEntry in self.utrItemTypeEntries.values():
                    for utrEntry in utrItemTypeEntry.values():
                        if utrEntry.unitId == m.localName and utrEntry.nsUnit == m.namespaceURI:
                            return utrEntry.symbol or utrEntry.unitId
                if m in self.modelXbrl.qnameConcepts: # if unit in taxonomy use label if it has any
                    return self.modelXbrl.qnameConcepts[m].label(fallbackToQname=False) or m.localName
                return m.localName # localName is last choice to use
        # otherwise generate compound symbol
        def symbols(measures, wrapMult=True):
            measuresString = " ".join(sorted(self.utrSymbol([measure], None)
                                             for measure in measures))
            if len(measures) > 1 and wrapMult:
                return "({})".format(measuresString)
            return measuresString

        if not multMeasures and divMeasures:
            return "per " + symbols(divMeasures)
        elif multMeasures:
            if divMeasures:
                return symbols(multMeasures) + " / " + symbols(divMeasures)
            else:
                return symbols(multMeasures, wrapMult=False)
        else:
            return ""
