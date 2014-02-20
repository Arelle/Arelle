'''
Created on Dec 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from lxml import etree
from arelle import ModelDocument
from collections import defaultdict

class UtrEntry(): # use slotted class for execution efficiency
    __slots__ = ("id", "unitId", "nsUnit", "itemType", "nsItemType", "isSimple",
                 "numeratorItemType", "nsNumeratorItemType", 
                 "denominatorItemType", "nsDenominatorItemType", "symbol")

    def __repr__(self):
        return "utrEntry({})".format(', '.join("{}={}".format(n, getattr(self,n))
                                               for n in self.__slots__))

def loadUtr(modelManager): # Build a dictionary of item types that are constrained by the UTR
    utrItemTypeEntries = defaultdict(dict)
    # print('UTR LOADED FROM '+utrUrl);
    modelManager.cntlr.showStatus(_("Loading Unit Type Registry"))
    file = None
    try:
        from arelle.FileSource import openXmlFileStream
        # normalize any relative paths to config directory
        file = openXmlFileStream(modelManager.cntlr, modelManager.disclosureSystem.utrUrl, stripDeclaration=True)[0]
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
            u.isSimple = u.numeratorItemType is None and u.denominatorItemType is None
            u.symbol = unitElt.findtext("{http://www.xbrl.org/2009/utr}symbol")
            # TO DO: This indexing scheme assumes that there are no name clashes in item types of the registry.
            (utrItemTypeEntries[u.itemType])[u.id] = u
        modelManager.disclosureSystem.utrItemTypeEntries = utrItemTypeEntries  
    except (EnvironmentError,
            etree.LxmlError) as err:
        modelManager.cntlr.addToLog("Unit Type Registry Import error: {0}".format(err))
        etree.clear_error_log()
    if file:
        file.close()
  
'''
def MeasureQName(node): # Return the qname of the content of the measure element
    assert node.nodeType == xml.dom.Node.ELEMENT_NODE
    assert node.localName == "measure"
    assert node.namespaceUri == XbrlConst.xbrli
    return ModelValue.qname(node, node.text)
'''



'''
def xmlEltMatch(node, localName, namespaceUri):
    if node == xml.dom.Node.ELEMENT_NODE and node.localName == localName and node.namespaceURI == namespaceUri:
        return True
    else:
        return False
'''

def validateFacts(modelXbrl):
    ValidateUtr(modelXbrl).validateFacts()
    
def utrEntries(modelType, modelUnit):
    return ValidateUtr(modelType.modelXbrl).utrEntries(modelType, modelUnit)
    
class ValidateUtr:
    def __init__(self, modelXbrl):
        self.modelXbrl = modelXbrl
        
    def validateFacts(self):
        modelXbrl = self.modelXbrl
        if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            if not hasattr(modelXbrl.modelManager.disclosureSystem, "utrItemTypeEntries"): 
                loadUtr(modelXbrl.modelManager)
            self.utrItemTypeEntries = modelXbrl.modelManager.disclosureSystem.utrItemTypeEntries
            modelXbrl.modelManager.cntlr.showStatus(_("Validating for Unit Type Registry").format())     
            utrInvalidFacts = []
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None and concept.isNumeric:
                    unit = f.unit
                    bConstrained = False
                    if f.unitID is not None and unit is not None:  # Would have failed XBRL validation otherwise
                        bSatisfied = True
                        utrMatchingEntries = []
                        _type = concept.type
                        while _type is not None:
                            if _type.name in self.utrItemTypeEntries:
                                for utrEntry in self.utrItemTypeEntries[_type.name].values():
                                    if utrEntry.itemType is None or utrEntry.itemType == _type.name:
                                        if utrEntry.nsItemType is None or utrEntry.nsItemType == _type.modelDocument.targetNamespace:
                                            utrMatchingEntries.append(utrEntry)                                                
                            if utrMatchingEntries:
                                bConstrained = True
                                _type = None # No more looking for registry entries
                                bSatisfied = any(self.unitSatisfies(utrEntry, unit)
                                                 for utrEntry in utrMatchingEntries)
                                break # while
                            #print(_("type={0}\ntype.qnameDerivedFrom={1}".format(_type,_type.qnameDerivedFrom)))
                            _type = _type.typeDerivedFrom
                            if isinstance(_type,list): # union type
                                _type = _type[0] # for now take first of union's types
                            #print(_("type={0}").format(_type))
                        # end while
                    # end if
                    if bConstrained and not bSatisfied:
                        utrInvalidFacts.append(f)
            # end for
            for fact in utrInvalidFacts:
                modelXbrl.error("utre:error-NumericFactUtrInvalid",
                                _("Unit %(unitID)s disallowed on fact %(element)s of type %(typeName)s"),
                                modelObject=fact, unitID=fact.unitID, element=fact.qname, typeName=fact.concept.type.name)

    def unitSatisfies(self, utrEntry, unit): # Return true if entry is satisfied by unit
        if utrEntry.isSimple: # Entry requires a measure
            if len(unit.measures[1]) > 0 or len(unit.measures[0]) > 1:
                return False # and only one measure
            else:
                try:
                    qnameMeasure = unit.measures[0][0]
                    if (utrEntry.nsUnit is not None and 
                        qnameMeasure.namespaceURI != utrEntry.nsUnit): 
                        #print(_("NOT EQUAL {0} {1}").format(sQName,sRequiredQName))
                        return False
                    elif (qnameMeasure.localName != utrEntry.unitId):
                        return False
                    else: 
                        #print(_("EQUAL {0} {1}").format(sQName,sRequiredQName))
                        return True # hooray       
                except IndexError:
                    return False  # no measure, so it can't possibly be equal
        else: # Entry requires a Divide
            if not unit.isDivide:
                return False
            elif not self.measureSatisfies(unit.measures[0], 
                                           utrEntry.nsNumeratorItemType, 
                                           utrEntry.numeratorItemType):
                return False
            elif not self.measureSatisfies(unit.measures[1], 
                                           utrEntry.nsDenominatorItemType, 
                                           utrEntry.denominatorItemType):
                return False
            else:
                return True
    
    
    def measureSatisfies(self, measures, nsItemType, itemType):
        #print(_("measures={0} namespace={1} itemType={2}").format(measures,namespace,itemType))
        bConstrained = False # An itemType is constrained if it appears in the registry (qname match)
        bSatisfied = False   # A unit is satisfied there is one entry that matches the unit
        if len(measures) != 1: # A unit registry entry has only one measure, or one measure in num or denom.
            return False
        measureLocalName = measures[0].localName
        measureNamespaceURI = measures[0].namespaceURI
        if itemType is None or not itemType or itemType not in self.utrItemTypeEntries:
            return True # unconstrained - this can happen when this function is called from within a Divide.
        utrEntries = self.utrItemTypeEntries[itemType]
        if utrEntries:
    #        print(_("itemType={0} nsMeasure={2} lnMeasure={3} aRegEntries= {1}").format(itemType,aRegEntries,nsMeasure,lnMeasure))
            for utrEntry in utrEntries.values():
                if (nsItemType is None or 
                    utrEntry.nsItemType is None or 
                    nsItemType == utrEntry.nsItemType):
                    bConstrained = True
                    #print(_("unitId={0}").format(unitId))
                    #print(_("nsUnit={0}").format(nsUnit))
                    if (utrEntry.unitId is None) or (utrEntry.unitId == measureLocalName):
                        if (utrEntry.nsUnit is None) or (utrEntry.nsUnit == measureNamespaceURI):
                            bSatisfied = True
                            break # for                             
        bResult = ((not bConstrained) or bSatisfied)
        # print(_("bResult={0}").format(bResult))
        return bResult

    def utrEntries(self, modelType, unit):
        utrSatisfyingEntries = set()
        modelXbrl = self.modelXbrl
        if not hasattr(modelXbrl.modelManager.disclosureSystem, "utrItemTypeEntries"): 
            loadUtr(modelXbrl.modelManager)
        self.utrItemTypeEntries = modelXbrl.modelManager.disclosureSystem.utrItemTypeEntries
        _type = modelType
        while _type is not None:
            if _type.name in self.utrItemTypeEntries:
                utrMatchingEntries = [utrEntry
                                      for utrEntry in self.utrItemTypeEntries[_type.name].values()
                                      if utrEntry.itemType is None or utrEntry.itemType == _type.name
                                      if utrEntry.nsItemType is None or utrEntry.nsItemType == _type.modelDocument.targetNamespace]
                if utrMatchingEntries:
                    for utrEntry in utrMatchingEntries:
                        if self.unitSatisfies(utrEntry, unit):
                            utrSatisfyingEntries.add(utrEntry)
            _type = _type.typeDerivedFrom
            if isinstance(_type,list): # union type
                _type = _type[0] # for now take first of union's types
        return utrSatisfyingEntries

