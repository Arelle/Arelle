'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XbrlConst
from tkinter import BooleanVar


def setDefaults(view):
    view.ignoreDimValidity = BooleanVar(value=True)
    view.xAxisChildrenFirst = BooleanVar(value=True)
    view.yAxisChildrenFirst = BooleanVar(value=False)

def getTblAxes(view, viewTblELR):
    tblAxisRelSet = view.modelXbrl.relationshipSet(XbrlConst.euTableAxis, viewTblELR)
    if len(tblAxisRelSet.modelRelationships) > 0:
        view.axisMbrRelSet = view.modelXbrl.relationshipSet(XbrlConst.euAxisMember, viewTblELR)
    else: # try 2011 roles
        tblAxisRelSet = view.modelXbrl.relationshipSet(XbrlConst.tableAxis, viewTblELR)
        view.axisMbrRelSet = view.modelXbrl.relationshipSet(XbrlConst.explicitAxisMember, viewTblELR)
    if tblAxisRelSet is None or len(tblAxisRelSet.modelRelationships) == 0:
        view.modelXbrl.modelManager.addToLog(_("no table relationships for {0}").format(view.arcrole))
        return (None, None, None, None)
    
    # table name
    modelRoleTypes = view.modelXbrl.roleTypes.get(viewTblELR)
    if modelRoleTypes is not None and len(modelRoleTypes) > 0:
        view.roledefinition = modelRoleTypes[0].definition
        if view.roledefinition is None or view.roledefinition == "":
            view.roledefinition = os.path.basename(viewTblELR)       
    for table in tblAxisRelSet.rootConcepts:            
        view.dataCols = 0
        view.dataRows = 0
        view.colHdrDocRow = False
        view.colHdrCodeRow = False
        view.colHdrRows = 0
        view.rowHdrCols = 0
        view.dataRows = 0
        view.rowHdrColWidth = [0,]
        view.rowHdrDocCol = False
        view.rowHdrCodeCol = False
        view.zAxisRows = 0
        
        xAxisObj = yAxisObj = zAxisObj = None
        for tblAxisRel in tblAxisRelSet.fromModelObject(table):
            axisType = tblAxisRel.tableAxis
            axisObj = tblAxisRel.toModelObject
            if axisType == "xAxis": xAxisObj = axisObj
            elif axisType == "yAxis": yAxisObj = axisObj
            elif axisType == "zAxis": zAxisObj = axisObj
            analyzeHdrs(view, axisObj, 1, axisType)
        view.colHdrTopRow = view.zAxisRows + 1 # need rest if combobox used (2 if view.zAxisRows else 1)
        view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[i] for i in range(view.rowHdrCols))
        view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + view.colHdrDocRow + view.colHdrCodeRow
        view.dataFirstCol = 1 + view.rowHdrCols + view.rowHdrDocCol + view.rowHdrCodeCol
        #for i in range(view.dataFirstRow + view.dataRows):
        #    view.gridView.rowconfigure(i)
        #for i in range(view.dataFirstCol + view.dataCols):
        #    view.gridView.columnconfigure(i)
        
        return (tblAxisRelSet, xAxisObj, yAxisObj, zAxisObj)
    
    return (None, None, None, None)
                  
def analyzeHdrs(view, axisModelObj, depth, axisType):
    for axisMbrRel in view.axisMbrRelSet.fromModelObject(axisModelObj):
        axisMbrModelObject = axisMbrRel.toModelObject
        if axisType == "zAxis":
            view.zAxisRows += 1 
             
            continue # no recursion
        elif axisType == "xAxis":
            if axisMbrModelObject.abstract == "false":
                view.dataCols += 1
            if depth > view.colHdrRows: view.colHdrRows = depth 
            if not view.colHdrDocRow:
                if axisMbrModelObject.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                               lang=view.lang): 
                    view.colHdrDocRow = True
            if not view.colHdrCodeRow:
                if axisMbrModelObject.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                    view.colHdrCodeRow = True
        elif axisType == "yAxis":
            if axisMbrModelObject.abstract == "false":
                view.dataRows += 1
            if depth > view.rowHdrCols: 
                view.rowHdrCols = depth
                view.rowHdrColWidth.append(16)  # min width for 'tail' of nonAbstract coordinate
            if axisMbrModelObject.abstract == "true":
                label = axisMbrModelObject.genLabel(lang=view.lang)
                if label:
                    widestWordLen = max(len(w) * 7 for w in label.split())
                    if widestWordLen > view.rowHdrColWidth[depth]:
                        view.rowHdrColWidth[depth] = widestWordLen 
            if not view.rowHdrDocCol:
                if axisMbrModelObject.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                               lang=view.lang): 
                    view.rowHdrDocCol = True
            if not view.rowHdrCodeCol:
                if axisMbrModelObject.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                    view.rowHdrCodeCol = True
        analyzeHdrs(view, axisMbrModelObject, depth+1, axisType) #recurse

    
def inheritedPrimaryItemQname(view, axisMbrObj):
    primaryItemQname = axisMbrObj.primaryItemQname
    if primaryItemQname:
        return primaryItemQname
    for axisMbrRel in view.axisMbrRelSet.toModelObject(axisMbrObj):
        primaryItemQname = inheritedPrimaryItemQname(view, axisMbrRel.fromModelObject)
        if primaryItemQname:
            return primaryItemQname
    return None
        
def inheritedExplicitDims(view, axisMbrObj, dims=None):
    if dims is None: dims = {}
    for axisMbrRel in view.axisMbrRelSet.toModelObject(axisMbrObj):
        inheritedExplicitDims(view, axisMbrRel.fromModelObject, dims=dims)
    for dim, mem in axisMbrObj.explicitDims:
        dims[dim] = mem
    return dims.items()

def dimContextElement(view, dimConcept):
    try:
        return view.dimsContextElement[dimConcept]
    except KeyError:
        if view.hcDimRelSet:
            for dimHcRel in view.hcDimRelSet.toModelObject(dimConcept):
                if dimHcRel.fromModelObject is not None:
                    for hcRel in view.hcDimRelSet.toModelObject(dimHcRel.fromModelObject):
                        contextElement = hcRel.contextElement
                        view.dimsContextElement[dimConcept] = contextElement
                        return contextElement
        return None
        

class FactPrototype():      # behaves like a fact for dimensional validity testing
    def __init__(self, v, qname, dims):
        self.qname = qname
        self.concept = v.modelXbrl.qnameConcepts.get(qname)
        self.context = ContextPrototype(v, dims)
        self.dims = dims # dim items
        self.dimKeys = set(dim[0] for dim in dims)

class ContextPrototype():  # behaves like a context
    def __init__(self, v, dims):
        self.segDimVals = {}
        self.scenDimVals = {}
        for dimQname,mem in dims:
            if v.modelXbrl.qnameDimensionDefaults.get(dimQname) != mem: # not a default
                try:
                    dimConcept = v.modelXbrl.qnameConcepts[dimQname]
                    dimValPrototype = DimValuePrototype(v, dimConcept, dimQname, mem)
                    if dimContextElement(v, dimConcept) == "segment":
                        self.segDimVals[dimConcept] = dimValPrototype
                    else:
                        self.scenDimVals[dimConcept] = dimValPrototype
                except KeyError:
                    pass
        
    def dimValues(self, contextElement):
        return self.segDimVals if contextElement == "segment" else self.scenDimVals
    
    def nonDimValues(self, contextElement):
        return []
    
class DimValuePrototype():
    def __init__(self, v, dimConcept, dimQname, mem):
        from arelle.ModelValue import QName
        self.dimension = dimConcept
        self.dimensionQname = dimQname
        if isinstance(mem,QName):
            self.isExplicit = True
            self.isTyped = False
            self.memberQname = mem
            self.member = v.modelXbrl.qnameConcepts[mem]

        else:
            self.isExplicit = False
            self.isTyped = True
            self.typedMember = mem
