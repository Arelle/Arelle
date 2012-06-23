'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XbrlConst
from tkinter import BooleanVar
from arelle.ModelFormulaObject import Aspect
from arelle.ModelRenderingObject import (ModelEuAxisCoord, ModelOpenAxis, ModelPredefinedAxis,
                                         ModelRelationshipAxis,
                                         OrdinateContext)

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
        view.rowHdrColWidth = [0,]
        view.rowHdrDocCol = False
        view.rowHdrCodeCol = False
        view.zAxisRows = 0
        view.aspectModel = table.aspectModel
        
        xOrdCntx = yOrdCntx = None
        zAxisObjs = []
        # must be cartesian product of top level relationships
        doX = doY = True
        tblAxisRels = tblAxisRelSet.fromModelObject(table)
        for i, tblAxisRel in enumerate(tblAxisRels):
            axisObj = tblAxisRel.toModelObject
            if isinstance(axisObj, (ModelEuAxisCoord, ModelOpenAxis)):
                axisDisposition = tblAxisRel.axisDisposition
                if axisDisposition == "x" and doX:
                    doX = False 
                    ordCntx = xOrdCntx = OrdinateContext(None, axisObj)
                    if isinstance(axisObj,ModelPredefinedAxis) and axisObj.parentChildOrder is not None:
                        view.xAxisChildrenFirst.set(axisObj.parentChildOrder == "children-first")
                elif axisDisposition == "y" and doY:
                    doY = False 
                    ordCntx = yOrdCntx = OrdinateContext(None, axisObj)
                    if isinstance(axisObj,ModelPredefinedAxis) and axisObj.parentChildOrder is not None:
                        view.yAxisChildrenFirst.set(axisObj.parentChildOrder == "children-first")
                elif axisDisposition == "z":
                    ordCntx = OrdinateContext(None, axisObj)
                    zAxisObjs.append(axisObj)
                else:
                    ordCntx = None
                analyzeHdrs(view, ordCntx, axisObj, 1, axisDisposition, i, tblAxisRels)
        view.colHdrTopRow = view.zAxisRows + 1 # need rest if combobox used (2 if view.zAxisRows else 1)
        view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[i] for i in range(view.rowHdrCols))
        view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + view.colHdrDocRow + view.colHdrCodeRow
        view.dataFirstCol = 1 + view.rowHdrCols + view.rowHdrDocCol + view.rowHdrCodeCol
        #for i in range(view.dataFirstRow + view.dataRows):
        #    view.gridView.rowconfigure(i)
        #for i in range(view.dataFirstCol + view.dataCols):
        #    view.gridView.columnconfigure(i)
        
        return (tblAxisRelSet, xOrdCntx, yOrdCntx, zAxisObjs)
    
    return (None, None, None, None)
                  
def analyzeHdrs(view, ordCntx, axisObject, depth, axisDisposition, i=None, tblAxisRels=None):
    if ordCntx and isinstance(axisObject, (ModelEuAxisCoord, ModelOpenAxis)):
        if axisDisposition == "z":
            view.zAxisRows += 1 
        else:
            cartesianProductNestedArgs = (view, depth, axisDisposition, tblAxisRels, i)
            ordCardinality, ordDepth = axisObject.cardinalityAndDepth
            nestedDepth = depth + ordDepth
            if axisDisposition == "x":
                if ordDepth:
                    if not axisObject.isAbstract:
                        view.dataCols += ordCardinality
                    if nestedDepth > view.colHdrRows: view.colHdrRows = nestedDepth 
                    if not view.colHdrDocRow:
                        if axisObject.header(role="http://www.xbrl.org/2008/role/documentation",
                                                       lang=view.lang): 
                            view.colHdrDocRow = True
                    if not view.colHdrCodeRow:
                        if axisObject.header(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                            view.colHdrCodeRow = True
            elif axisDisposition == "y":
                if ordDepth:
                    if not axisObject.isAbstract:
                        view.dataRows += ordCardinality
                    if nestedDepth > view.rowHdrCols: 
                        view.rowHdrCols = nestedDepth
                        for j in range(1 + ordDepth):
                            view.rowHdrColWidth.append(16)  # min width for 'tail' of nonAbstract coordinate
                    if axisObject.isAbstract:
                        label = ordCntx.header(lang=view.lang)
                        if label:
                            widestWordLen = max(len(w) * 7 for w in label.split())
                            if widestWordLen > view.rowHdrColWidth[depth]:
                                view.rowHdrColWidth[nestedDepth] = widestWordLen 
                    if not view.rowHdrDocCol:
                        if axisObject.header(role="http://www.xbrl.org/2008/role/documentation",
                                                       lang=view.lang): 
                            view.rowHdrDocCol = True
                    if not view.rowHdrCodeCol:
                        if axisObject.header(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                            ordCntx.rowHdrCodeCol = True
            if isinstance(axisObject, ModelRelationshipAxis):
                selfOrdContexts = {} if axisObject.axis.endswith('-or-self') else None
                for rel in axisObject.relationships(view.modelXbrl.rendrCntx):
                    if not isinstance(rel, list):
                        relSubOrdCntx = addRelationship(axisObject, rel, ordCntx, cartesianProductNestedArgs, selfOrdContexts)
                    else:
                        addRelationships(axisObject, rel, relSubOrdCntx, cartesianProductNestedArgs)
                    
            for axisSubtreeRel in view.axisSubtreeRelSet.fromModelObject(axisObject):
                subtreeObj = axisSubtreeRel.toModelObject
                subOrdCntx = OrdinateContext(ordCntx, subtreeObj)
                ordCntx.subOrdinateContexts.append(subOrdCntx)
                analyzeHdrs(view, subOrdCntx, subtreeObj, depth+ordDepth, axisDisposition) #recurse
                analyzeCartesianProductHdrs(subOrdCntx, *cartesianProductNestedArgs)
                        
            if depth == 1 and not ordCntx.subOrdinateContexts: # childless root ordinate, make a child to iterate in producing table
                subOrdContext = OrdinateContext(ordCntx, axisObject)

def analyzeCartesianProductHdrs(subOrdCntx, view, depth, axisDisposition, tblAxisRels, i):
    if i is not None: # recurse table relationships for cartesian product
        for j, tblRel in enumerate(tblAxisRels[i+1:]):
            tblObj = tblRel.toModelObject
            if isinstance(tblObj, (ModelEuAxisCoord, ModelOpenAxis)) and axisDisposition == tblRel.axisDisposition:
                if tblObj.cardinalityAndDepth[1]:
                    subOrdTblCntx = OrdinateContext(subOrdCntx, tblObj)
                    subOrdCntx.subOrdinateContexts.append(subOrdTblCntx)
                else: # non-ordinate composition
                    subOrdTblCntx = subOrdCntx
                analyzeHdrs(view, subOrdTblCntx, tblObj, depth + 1, axisDisposition, j + i + 1, tblAxisRels) #cartesian product
                break
                
def addRelationship(relAxisObj, rel, ordCntx, cartesianProductNestedArgs, selfOrdContexts=None):
    variableQname = relAxisObj.variableQname
    conceptQname = relAxisObj.conceptQname
    coveredAspect = relAxisObj.coveredAspect()
    if not coveredAspect:
        return None
    if selfOrdContexts is not None:
        fromConceptQname = rel.fromModelObject.qname
        # is there an ordinate for this root object?
        if fromConceptQname in selfOrdContexts:
            subOrdCntx = selfOrdContexts[fromConceptQname]
        else:
            subOrdCntx = OrdinateContext(ordCntx, relAxisObj)
            ordCntx.subOrdinateContexts.append(subOrdCntx)
            selfOrdContexts[fromConceptQname] = subOrdCntx
            if variableQname:
                subOrdCntx.variables[variableQname] = []
            if conceptQname:
                subOrdCntx.variables[conceptQname] = fromConceptQname
            subOrdCntx.aspects[coveredAspect] = fromConceptQname
        relSubOrdCntx = OrdinateContext(subOrdCntx, relAxisObj)
        subOrdCntx.subOrdinateContexts.append(relSubOrdCntx)
    else:
        relSubOrdCntx = OrdinateContext(ordCntx, relAxisObj)
        ordCntx.subOrdinateContexts.append(relSubOrdCntx)
    if variableQname:
        relSubOrdCntx.variables[variableQname] = rel
    toConceptQname = rel.toModelObject.qname
    if conceptQname:
        relSubOrdCntx.variables[conceptQname] = toConceptQname
    relSubOrdCntx.aspects[coveredAspect] = toConceptQname
    analyzeCartesianProductHdrs(relSubOrdCntx, *cartesianProductNestedArgs)
    return relSubOrdCntx

def addRelationships(relAxisObj, rels, ordCntx, cartesianProductNestedArgs):
    for rel in rels:
        if not isinstance(rel, list):
            addRelationship(relAxisObj, rel, ordCntx, cartesianProductNestedArgs)
        else:
            subOrdCntx = OrdinateContext(ordCntx, relAxisObj)
            ordCntx.subOrdinateContexts.append(subOrdCntx)
            addRelationships(relAxisObj, rel, subOrdCntx, cartesianProductNestedArgs)
    
def inheritedPrimaryItemQname(view, ordCntx):
    if ordCntx is None:
        return None
    return (ordCntx.primaryItemQname or inheritedPrimaryItemQname(view, ordCntx.parentOrdinateContext))
        
def inheritedExplicitDims(view, ordCntx, dims=None, nested=False):
    if dims is None: dims = {}
    if ordCntx.parentOrdinateContext:
        inheritedExplicitDims(view, ordCntx.parentOrdinateContext, dims, True)
    for dim, mem in ordCntx.explicitDims:
        dims[dim] = mem
    if not nested:
        return {(dim,mem) for dim,mem in dims.items() if mem != 'omit'}


