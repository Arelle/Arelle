'''
Created on Dec 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from lxml import etree
from arelle import (ModelDocument, ModelValue, XbrlConst, XmlUtil)

def loadUtr(modelManager): # Build a dictionary of item types that are constrained by the UTR.
    modelManager.utrDict = {} # This attribute is unbound on modelManager until this function is called.
    utrUrl = os.path.join(modelManager.cntlr.configDir, "utr.xml")
    #utrUrl = "file:/c:/home/conformance-lrr/trunk/schema/utr/utr.xml"
    modelManager.cntlr.showStatus(_("Loading Unit Type Registry"))
    try:
        xmldoc = etree.parse(utrUrl)
        for unitElt in xmldoc.iter(tag="{http://www.xbrl.org/2009/utr}unit"):
            id = unitElt.get("id")
            unitId = unitElt.findtext("{http://www.xbrl.org/2009/utr}unitId")
            nsUnit = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsUnit")
            itemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}itemType")
            nsItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsItemType")
            numeratorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}numeratorItemType")
            nsNumeratorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsNumeratorItemType")
            denominatorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}denominatorItemType")
            nsDenominatorItemType = unitElt.findtext("{http://www.xbrl.org/2009/utr}nsDenominatorItemType")
            # TO DO: This indexing scheme assumes that there are no name clashes in item types of the registry.
            if modelManager.utrDict.get(itemType) == None:
                modelManager.utrDict[itemType] = {}
            # a RegEntry is just an array.
            (modelManager.utrDict[itemType])[id] = [unitId, nsUnit # 0,1
                              , nsNumeratorItemType, numeratorItemType # 2,3
                              , nsDenominatorItemType, denominatorItemType # 4,5
                              , nsItemType # 6 often None
                              ]
    except (EnvironmentError,
            etree.LxmlError) as err:
        modelManager.cntlr.addToLog("Unit Type Registry Import error: {0}".format(err))
        etree.clear_error_log()
  
'''
def MeasureQName(node): # Return the qame of the content of the measure element
    assert node.nodeType == xml.dom.Node.ELEMENT_NODE
    assert node.localName == "measure"
    assert node.namespaceUri == XbrlConst.xbrli
    return ModelValue.qname(node, node.text)
'''

def UnitSatisfies(aRegEntry, unit, modelXbrl): # Return true if entry is satisfied by unit
    # aRegEntry is [unitId, nsUnit, nsNumeratorItemType, numeratorItemType, nsDenominatorItemType, denominatorItemType]
    if aRegEntry[1] != None: # Entry requires a measure
        if unit.measures[1] != [] or len(unit.measures[0])>1:
            return False # and only one measure
        else:
            qnameMeasure = unit.measures[0][0]
            if qnameMeasure.namespaceURI != aRegEntry[1] or qnameMeasure.localName != aRegEntry[0]: 
                #print(_("NOT EQUAL {0} {1}").format(sQName,sRequiredQName))
                return False
            else: 
                #print(_("EQUAL {0} {1}").format(sQName,sRequiredQName))
                return True # hooray       
    else: # Entry requires a Divide
        if not unit.isDivide:
            return False
        elif not MeasureSatisfies(unit.measures[0], aRegEntry[2], aRegEntry[3], modelXbrl):
            return False
        elif not MeasureSatisfies(unit.measures[1], aRegEntry[4], aRegEntry[5], modelXbrl):
            return False
        else:
            return True


def MeasureSatisfies(measures,nsItemType,itemType,modelXbrl):
    #print(_("measures={0} namespace={1} itemType={2}").format(measures,namespace,itemType))
    utrDict = modelXbrl.modelManager.utrDict
    bConstrained = False # An itemType is constrained if it appears in the registry
    bSatisfied = False   # A unit is satisfied there is one entry that matches the unit
    if len(measures) != 1: # We assume all unit registry entries have only one measure, or one measure in num or denom.
        return False
    if utrDict.get(itemType) == None:
        return True # unconstrained - this can happen when this function is called from within a Divide.
    aRegEntries = utrDict[itemType]
# TO DO: Improve matching to take account of itemType namespace
#    nsRequired = aRegEntry[6]
#    if (namespace != None) and (nsRequired != None) and (namespace != nsRequired): return False
#   Check whether this measure (a QName) is valid for itemType (possibly qualified by namespace)
    nEntries = len(aRegEntries)
    if (nEntries > 0):
        bConstrained = True
#        print(_("itemType={0} nsMeasure={2} lnMeasure={3} aRegEntries= {1}").format(itemType,aRegEntries,nsMeasure,lnMeasure))
        for a in aRegEntries:
            lnRequired = aRegEntries[a][0]
#            print(_("lnRequired={0}").format(lnRequired))
#            print(_("nsRequired={0}").format(nsRequired))
            if (lnRequired is None) or (lnRequired == measures[0].localName):
                nsRequired = aRegEntries[a][1]
                if (nsRequired is None) or (nsRequired == measures[0].namespaceURI):
                    bSatisfied = True
                    break # for                             
    bResult = ((not bConstrained) or bSatisfied)
    # print(_("bResult={0}").format(bResult))
    return bResult

'''
def xmlEltMatch(node, localName, namespaceUri):
    if node == xml.dom.Node.ELEMENT_NODE and node.localName == localName and node.namespaceURI == namespaceUri:
        return True
    else:
        return False
'''

def validate(modelXbrl):
    ValidateUtr(modelXbrl).validate()
    
class ValidateUtr:
    def __init__(self, modelXbrl):
        self.modelXbrl = modelXbrl
        
    def validate(self):
        modelXbrl = self.modelXbrl
        if not hasattr(modelXbrl.modelManager,"utrDict"): 
            loadUtr(modelXbrl.modelManager)
        modelXbrl.modelManager.cntlr.showStatus(_("Validating for Unit Type Registry").format())     
        if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
            aInvalidUnits = []
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None:
                    if concept.isNumeric:
                        unit = f.unit
                        if f.unitID != None and unit != None:  # Would have failed XBRL validation otherwise
                            bConstrained = False
                            bSatisfied = True
                            type = concept.type
                            while type != None:
                                aRegEntries = []
                                if modelXbrl.modelManager.utrDict.get(type.name) != None:
                                    aRegEntries = modelXbrl.modelManager.utrDict[type.name]
                                nEntries = len(aRegEntries)
                                if nEntries > 0:
                                    bConstrained = True
                                    type = None # No more looking for registry entries
                                    bSatisfied = False
                                    for a in aRegEntries:
                                        #modelXbrl.error(_("Checking {0} against {1} on {2}").format(f.unitID, aRegEntries[a],f.concept.name))
                                        if UnitSatisfies(aRegEntries[a], unit, modelXbrl):
                                            bSatisfied = True
                                            break # for                             
                                    break # while
                                #print(_("type={0}\ntype.qnameDerivedFrom={1}".format(type,type.qnameDerivedFrom)))
                                type = modelXbrl.qnameTypes.get(type.qnameDerivedFrom)
                                #print(_("type={0}").format(type))
                            # end while
                        # end if
                        if bConstrained and not bSatisfied:
                            aInvalidUnits.append(f)
            # end for
            for fact in aInvalidUnits:
                modelXbrl.error(_("Unit {0} disallowed on fact of type {1}").format(fact.unitID, fact.concept.type.name),"err","utr:invalid")
