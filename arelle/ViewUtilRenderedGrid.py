'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XbrlConst
from tkinter import BooleanVar
from arelle.ModelRenderingObject import ModelEuAxisCoord, ModelOpenAxis, ModelPredefinedAxis

def setDefaults(view):
    view.ignoreDimValidity = BooleanVar(value=True)
    view.xAxisChildrenFirst = BooleanVar(value=True)
    view.yAxisChildrenFirst = BooleanVar(value=False)

def getTblAxes(view, viewTblELR):
    tblAxisRelSet = view.modelXbrl.relationshipSet(XbrlConst.euTableAxis, viewTblELR)
    if len(tblAxisRelSet.modelRelationships) > 0:
        view.axisSubtreeRelSet = view.modelXbrl.relationshipSet(XbrlConst.euAxisMember, viewTblELR)
    else: # try 2011 roles
        tblAxisRelSet = view.modelXbrl.relationshipSet(XbrlConst.tableAxis, viewTblELR)
        view.axisSubtreeRelSet = view.modelXbrl.relationshipSet(XbrlConst.tableAxisSubtree, viewTblELR)
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
        
        xAxisObj = yAxisObj = None
        zAxisObjs = []
        for tblAxisRel in tblAxisRelSet.fromModelObject(table):
            axisObj = tblAxisRel.toModelObject
            if isinstance(axisObj, (ModelEuAxisCoord, ModelOpenAxis)):
                axisDisposition = tblAxisRel.axisDisposition
                if axisDisposition == "x": 
                    xAxisObj = axisObj
                    if isinstance(axisObj,ModelPredefinedAxis) and xAxisObj.parentChildOrder is not None:
                        view.xAxisChildrenFirst.set(xAxisObj.parentChildOrder == "children-first")
                elif axisDisposition == "y": 
                    yAxisObj = axisObj
                    if isinstance(axisObj,ModelPredefinedAxis) and yAxisObj.parentChildOrder is not None:
                        view.yAxisChildrenFirst.set(yAxisObj.parentChildOrder == "children-first")
                elif axisDisposition == "z":
                    zAxisObjs.append(axisObj)
                analyzeHdrs(view, axisObj, 1, axisDisposition)
        view.colHdrTopRow = view.zAxisRows + 1 # need rest if combobox used (2 if view.zAxisRows else 1)
        view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[i] for i in range(view.rowHdrCols))
        view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + view.colHdrDocRow + view.colHdrCodeRow
        view.dataFirstCol = 1 + view.rowHdrCols + view.rowHdrDocCol + view.rowHdrCodeCol
        #for i in range(view.dataFirstRow + view.dataRows):
        #    view.gridView.rowconfigure(i)
        #for i in range(view.dataFirstCol + view.dataCols):
        #    view.gridView.columnconfigure(i)
        
        return (tblAxisRelSet, xAxisObj, yAxisObj, zAxisObjs)
    
    return (None, None, None, None)
                  
def analyzeHdrs(view, axisModelObj, depth, axisDisposition):
    for axisSubtreeRel in view.axisSubtreeRelSet.fromModelObject(axisModelObj):
        axisMbrModelObject = axisSubtreeRel.toModelObject
        if isinstance(axisMbrModelObject, (ModelEuAxisCoord, ModelOpenAxis)):
            if axisDisposition == "z":
                view.zAxisRows += 1 
                 
                continue # no recursion
            elif axisDisposition == "x":
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
            elif axisDisposition == "y":
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
            analyzeHdrs(view, axisMbrModelObject, depth+1, axisDisposition) #recurse

    
def inheritedPrimaryItemQname(view, axisMbrObj):
    primaryItemQname = axisMbrObj.primaryItemQname
    if primaryItemQname:
        return primaryItemQname
    for axisSubtreeRel in view.axisSubtreeRelSet.toModelObject(axisMbrObj):
        primaryItemQname = inheritedPrimaryItemQname(view, axisSubtreeRel.fromModelObject)
        if primaryItemQname:
            return primaryItemQname
    return None
        
def inheritedExplicitDims(view, axisMbrObj, dims=None, nested=False):
    if dims is None: dims = {}
    for axisSubtreeRel in view.axisSubtreeRelSet.toModelObject(axisMbrObj):
        inheritedExplicitDims(view, axisSubtreeRel.fromModelObject, dims, True)
    for dim, mem in axisMbrObj.explicitDims:
        dims[dim] = mem
    if not nested:
        return {(dim,mem) for dim,mem in dims.items() if mem != 'omit'}


