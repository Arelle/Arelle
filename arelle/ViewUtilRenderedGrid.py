'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import Aspect
from arelle.ModelRenderingObject import (ModelEuAxisCoord, ModelOpenAxisNodeDefinition, ModelClosedAxisNodeDefinition,
                                         ModelRelationshipAxisDefinition, ModelSelectionAxisNode, ModelFilterAxisNode,
                                         ModelCompositionAxisNode, ModelTupleAxisNode, StructuralOrdinateContext)

def resolveAxesStructure(view, viewTblELR):
    tblAxisRelSet = view.modelXbrl.relationshipSet(XbrlConst.euTableAxis, viewTblELR)
    if len(tblAxisRelSet.modelRelationships) > 0:
        view.axisSubtreeRelSet = view.modelXbrl.relationshipSet(XbrlConst.euAxisMember, viewTblELR)
    else: # try 2011 roles
        tblAxisRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown,XbrlConst.tableAxis2011), viewTblELR)
        view.axisSubtreeRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableAxisSubtree,XbrlConst.tableAxisSubtree2011), viewTblELR)
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
        view.colHdrNonStdRoles = []
        view.colHdrDocRow = False
        view.colHdrCodeRow = False
        view.colHdrRows = 0
        view.rowHdrNonStdRoles = []
        view.rowHdrCols = 0
        view.rowHdrColWidth = [0,]
        view.rowHdrDocCol = False
        view.rowHdrCodeCol = False
        view.zAxisRows = 0
        view.aspectModel = table.aspectModel
        view.zmostOrdCntx = None
        view.modelTable = table
        
        xStrOrdCntx = yStrOrdCntx = zStrOrdCntx = None
        # must be cartesian product of top level relationships
        tblAxisRels = tblAxisRelSet.fromModelObject(table)
        facts = view.modelXbrl.factsInInstance
        # do z's first to set variables needed by x and y axes expressions
        for disposition in ("z", "x", "y"):
            for i, tblAxisRel in enumerate(tblAxisRels):
                axisObj = tblAxisRel.toModelObject
                if (tblAxisRel.axisDisposition == disposition and 
                    isinstance(axisObj, (ModelEuAxisCoord, ModelOpenAxisNodeDefinition))):
                    if disposition == "x" and xStrOrdCntx is None:
                        xStrOrdCntx = StructuralOrdinateContext(None, axisObj, view.zmostOrdCntx)
                        if isinstance(axisObj,ModelClosedAxisNodeDefinition) and axisObj.parentChildOrder is not None:
                            view.xAxisChildrenFirst.set(axisObj.parentChildOrder == "children-first")
                        analyzeHdrs(view, xStrOrdCntx, axisObj, 1, disposition, facts, i, tblAxisRels)
                        break
                    elif disposition == "y" and yStrOrdCntx is None:
                        yStrOrdCntx = StructuralOrdinateContext(None, axisObj, view.zmostOrdCntx)
                        if isinstance(axisObj,ModelClosedAxisNodeDefinition) and axisObj.parentChildOrder is not None:
                            view.yAxisChildrenFirst.set(axisObj.parentChildOrder == "children-first")
                        analyzeHdrs(view, yStrOrdCntx, axisObj, 0, disposition, facts, i, tblAxisRels)
                        break
                    elif disposition == "z" and zStrOrdCntx is None:
                        zStrOrdCntx = StructuralOrdinateContext(None, axisObj)
                        analyzeHdrs(view, zStrOrdCntx, axisObj, 1, disposition, facts, i, tblAxisRels)
                        break
        view.colHdrTopRow = view.zAxisRows + 1 # need rest if combobox used (2 if view.zAxisRows else 1)
        view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[i] for i in range(view.rowHdrCols))
        view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + len(view.colHdrNonStdRoles)
        view.dataFirstCol = 1 + view.rowHdrCols + len(view.rowHdrNonStdRoles)
        #view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + view.colHdrDocRow + view.colHdrCodeRow
        #view.dataFirstCol = 1 + view.rowHdrCols + view.rowHdrDocCol + view.rowHdrCodeCol
        #for i in range(view.dataFirstRow + view.dataRows):
        #    view.gridView.rowconfigure(i)
        #for i in range(view.dataFirstCol + view.dataCols):
        #    view.gridView.columnconfigure(i)
        view.modelTable = table
        
        return (tblAxisRelSet, xStrOrdCntx, yStrOrdCntx, zStrOrdCntx)
    
    return (None, None, None, None)

def sortkey(obj):
    if isinstance(obj, ModelObject):
        return obj.objectIndex
    return obj
                  
def analyzeHdrs(view, ordCntx, axisNodeObject, depth, axisDisposition, facts, i=None, tblAxisRels=None):
    if ordCntx and isinstance(axisNodeObject, (ModelEuAxisCoord, ModelOpenAxisNodeDefinition)):
        #cartesianProductNestedArgs = (view, depth, axisDisposition, facts, tblAxisRels, i)
        ordCardinality, ordDepth = axisNodeObject.cardinalityAndDepth(ordCntx)
        nestedDepth = depth + ordDepth
        # HF test
        cartesianProductNestedArgs = (view, nestedDepth, axisDisposition, facts, tblAxisRels, i)
        if axisDisposition == "z":
            if depth == 1: # choices (combo boxes) don't add to z row count
                view.zAxisRows += 1 
        elif axisDisposition == "x":
            if ordDepth:
                if not axisNodeObject.isAbstract:
                    view.dataCols += ordCardinality
                if nestedDepth > view.colHdrRows: view.colHdrRows = nestedDepth 
                '''
                if not view.colHdrDocRow:
                    if axisNodeObject.header(role="http://www.xbrl.org/2008/role/documentation",
                                                   lang=view.lang): 
                        view.colHdrDocRow = True
                if not view.colHdrCodeRow:
                    if axisNodeObject.header(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                        view.colHdrCodeRow = True
                '''
            hdrNonStdRoles = view.colHdrNonStdRoles
        elif axisDisposition == "y":
            if ordDepth:
                if not axisNodeObject.isAbstract:
                    view.dataRows += ordCardinality
                if nestedDepth > view.rowHdrCols: 
                    view.rowHdrCols = nestedDepth
                    for j in range(1 + ordDepth):
                        view.rowHdrColWidth.append(16)  # min width for 'tail' of nonAbstract coordinate
                if axisNodeObject.isAbstract:
                    label = ordCntx.header(lang=view.lang)
                    if label:
                        widestWordLen = max(len(w) * 7 for w in label.split())
                        if widestWordLen > view.rowHdrColWidth[depth]:
                            view.rowHdrColWidth[depth] = widestWordLen
                ''' 
                if not view.rowHdrDocCol:
                    if axisNodeObject.header(role="http://www.xbrl.org/2008/role/documentation",
                                         lang=view.lang): 
                        view.rowHdrDocCol = True
                if not view.rowHdrCodeCol:
                    if axisNodeObject.header(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                        view.rowHdrCodeCol = True
                '''
            hdrNonStdRoles = view.rowHdrNonStdRoles
        if axisDisposition in ("x", "y"):
            hdrNonStdPosition = -1  # where a match last occured
            for rel in view.modelXbrl.relationshipSet(XbrlConst.elementLabel).fromModelObject(axisNodeObject):
                if rel.toModelObject is not None and rel.toModelObject.role != XbrlConst.genStandardLabel:
                    labelLang = rel.toModelObject.xmlLang
                    labelRole = rel.toModelObject.role
                    if (labelLang == view.lang or labelLang.startswith(view.lang) or view.lang.startswith(labelLang)
                        or ("code" in labelRole)):
                        labelRole = rel.toModelObject.role
                        if labelRole in hdrNonStdRoles:
                            hdrNonStdPosition = hdrNonStdRoles.index(labelRole)
                        else:
                            hdrNonStdRoles.insert(hdrNonStdPosition + 1, labelRole)
        hasSubtreeRels = False
        for axisSubtreeRel in view.axisSubtreeRelSet.fromModelObject(axisNodeObject):
            hasSubtreeRels = True
            subtreeObj = axisSubtreeRel.toModelObject
            if (isinstance(axisNodeObject, ModelCompositionAxisNode) and
                isinstance(subtreeObj, ModelRelationshipAxisDefinition)): # append list products to composititionAxes subObjCntxs
                subOrdCntx = ordCntx
            else:
                subOrdCntx = StructuralOrdinateContext(ordCntx, subtreeObj) # others are nested ordCntx
                if axisDisposition != "z":
                    ordCntx.subOrdinateContexts.append(subOrdCntx)
            if axisDisposition != "z":
                analyzeHdrs(view, subOrdCntx, subtreeObj, depth+ordDepth, axisDisposition, facts) #recurse
                analyzeCartesianProductHdrs(subOrdCntx, *cartesianProductNestedArgs)
            else:
                subOrdCntx.indent = depth - 1
                ordCntx.choiceOrdinateContexts.append(subOrdCntx)
                analyzeHdrs(view, ordCntx, subtreeObj, depth + 1, axisDisposition, facts) #recurse
        if not hasattr(ordCntx, "indent"): # probably also for multiple open axes
            if isinstance(axisNodeObject, ModelRelationshipAxisDefinition):
                selfOrdContexts = {} if axisNodeObject.axis.endswith('-or-self') else None
                for rel in axisNodeObject.relationships(ordCntx):
                    if not isinstance(rel, list):
                        relSubOrdCntx = addRelationship(axisNodeObject, rel, ordCntx, cartesianProductNestedArgs, selfOrdContexts)
                    else:
                        addRelationships(axisNodeObject, rel, relSubOrdCntx, cartesianProductNestedArgs)
                    
            elif isinstance(axisNodeObject, ModelSelectionAxisNode):
                varQn = axisNodeObject.variableQname
                if varQn:
                    selections = sorted(ordCntx.evaluate(axisNodeObject, axisNodeObject.evaluate) or [], 
                                        key=lambda obj:sortkey(obj))
                    if isinstance(selections, (list,set,tuple)) and len(selections) > 1:
                        for selection in selections: # nested choices from selection list
                            subOrdCntx = StructuralOrdinateContext(ordCntx, axisNodeObject, contextItemFact=selection)
                            subOrdCntx.variables[varQn] = selection
                            subOrdCntx.indent = 0
                            if axisDisposition == "z":
                                ordCntx.choiceOrdinateContexts.append(subOrdCntx)
                                subOrdCntx.zSelection = True
                            else:
                                ordCntx.subOrdinateContexts.append(subOrdCntx)
                                analyzeHdrs(view, subOrdCntx, axisNodeObject, depth, axisDisposition, facts) #recurse
                    else:
                        ordCntx.variables[varQn] = selections
            elif isinstance(axisNodeObject, ModelFilterAxisNode):
                ordCntx.abstract = True # spanning ordinate acts as a subtitle
                filteredFactsPartitions = ordCntx.evaluate(axisNodeObject, 
                                                           axisNodeObject.filteredFactsPartitions, 
                                                           evalArgs=(facts,))
                for factsPartition in filteredFactsPartitions:
                    subOrdCntx = StructuralOrdinateContext(ordCntx, axisNodeObject, contextItemFact=factsPartition[0])
                    subOrdCntx.indent = 0
                    ordCntx.subOrdinateContexts.append(subOrdCntx)
                    analyzeHdrs(view, subOrdCntx, axisNodeObject, depth, axisDisposition, factsPartition) #recurse
                # sort by header (which is likely to be typed dim value, for example)
                ordCntx.subOrdinateContexts.sort(key=lambda subOrdCntx: subOrdCntx.header(lang=view.lang))
                
                # TBD if there is no abstract 'sub header' for these subOrdCntxs, move them in place of parent ordCntx 
            elif isinstance(axisNodeObject, ModelTupleAxisNode):
                ordCntx.abstract = True # spanning ordinate acts as a subtitle
                matchingTupleFacts = ordCntx.evaluate(axisNodeObject, 
                                                      axisNodeObject.filteredFacts, 
                                                      evalArgs=(facts,))
                for tupleFact in matchingTupleFacts:
                    subOrdCntx = StructuralOrdinateContext(ordCntx, axisNodeObject, contextItemFact=tupleFact)
                    subOrdCntx.indent = 0
                    ordCntx.subOrdinateContexts.append(subOrdCntx)
                    analyzeHdrs(view, subOrdCntx, axisNodeObject, depth, axisDisposition, [tupleFact]) #recurse
                # sort by header (which is likely to be typed dim value, for example)
                if any(sOC.header(lang=view.lang) for sOC in ordCntx.subOrdinateContexts):
                    ordCntx.subOrdinateContexts.sort(key=lambda subOrdCntx: subOrdCntx.header(lang=view.lang))

            if axisDisposition == "z":
                if ordCntx.choiceOrdinateContexts:
                    choiceOrdinateIndex = view.zOrdinateChoices.get(axisNodeObject, 0)
                    if choiceOrdinateIndex < len(ordCntx.choiceOrdinateContexts):
                        ordCntx.choiceOrdinateIndex = choiceOrdinateIndex
                    else:
                        ordCntx.choiceOrdinateIndex = 0
                view.zmostOrdCntx = ordCntx
                    
            if not hasSubtreeRels or axisDisposition == "z":
                analyzeCartesianProductHdrs(ordCntx, *cartesianProductNestedArgs)
                    
            if not ordCntx.subOrdinateContexts: # childless root ordinate, make a child to iterate in producing table
                subOrdContext = StructuralOrdinateContext(ordCntx, axisNodeObject)

def analyzeCartesianProductHdrs(subOrdCntx, view, depth, axisDisposition, facts, tblAxisRels, i):
    if i is not None: # recurse table relationships for cartesian product
        for j, tblRel in enumerate(tblAxisRels[i+1:]):
            tblObj = tblRel.toModelObject
            if isinstance(tblObj, (ModelEuAxisCoord, ModelOpenAxisNodeDefinition)) and axisDisposition == tblRel.axisDisposition:
                #if tblObj.cardinalityAndDepth(subOrdCntx)[1] or axisDisposition == "z":
                if axisDisposition == "z":
                    subOrdTblCntx = StructuralOrdinateContext(subOrdCntx, tblObj)
                    subOrdCntx.subOrdinateContexts.append(subOrdTblCntx)
                else: # non-ordinate composition
                    subOrdTblCntx = subOrdCntx
                # predefined axes need facts sub-filtered
                if isinstance(subOrdCntx.axisNodeObject, ModelClosedAxisNodeDefinition):
                    matchingFacts = subOrdCntx.evaluate(subOrdCntx.axisNodeObject, 
                                                        subOrdCntx.axisNodeObject.filteredFacts, 
                                                        evalArgs=(facts,))
                else:
                    matchingFacts = facts
                    
                analyzeHdrs(view, subOrdTblCntx, tblObj, 
                            depth + (0 if axisDisposition == 'z' else 1), 
                            axisDisposition, matchingFacts, j + i + 1, tblAxisRels) #cartesian product
                break
                
def addRelationship(relAxisObj, rel, ordCntx, cartesianProductNestedArgs, selfOrdContexts=None):
    variableQname = relAxisObj.variableQname
    conceptQname = relAxisObj.conceptQname
    coveredAspect = relAxisObj.coveredAspect(ordCntx)
    if not coveredAspect:
        return None
    if selfOrdContexts is not None:
        fromConceptQname = rel.fromModelObject.qname
        # is there an ordinate for this root object?
        if fromConceptQname in selfOrdContexts:
            subOrdCntx = selfOrdContexts[fromConceptQname]
        else:
            subOrdCntx = StructuralOrdinateContext(ordCntx, relAxisObj)
            ordCntx.subOrdinateContexts.append(subOrdCntx)
            selfOrdContexts[fromConceptQname] = subOrdCntx
            if variableQname:
                subOrdCntx.variables[variableQname] = []
            if conceptQname:
                subOrdCntx.variables[conceptQname] = fromConceptQname
            subOrdCntx.aspects[coveredAspect] = fromConceptQname
        relSubOrdCntx = StructuralOrdinateContext(subOrdCntx, relAxisObj)
        subOrdCntx.subOrdinateContexts.append(relSubOrdCntx)
    else:
        relSubOrdCntx = StructuralOrdinateContext(ordCntx, relAxisObj)
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
    subOrdCntx = None # holder for nested relationships
    for rel in rels:
        if not isinstance(rel, list):
            # first entry can be parent of nested list relationships
            subOrdCntx = addRelationship(relAxisObj, rel, ordCntx, cartesianProductNestedArgs)
        elif subOrdCntx is None:
            subOrdCntx = StructuralOrdinateContext(ordCntx, relAxisObj)
            ordCntx.subOrdinateContexts.append(subOrdCntx)
            addRelationships(relAxisObj, rel, subOrdCntx, cartesianProductNestedArgs)
        else:
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

emptySet = set()
def inheritedAspectValue(view, aspect, xAspects, yAspects, zAspects, xOrdCntx, yOrdCntx):
    ords = xAspects.get(aspect, emptySet) | yAspects.get(aspect, emptySet) | zAspects.get(aspect, emptySet)
    ordCntx = None
    if len(ords) == 1:
        ordCntx = ords.pop()
    elif len(ords) > 1:
        if aspect == Aspect.LOCATION:
            hasClash = False
            for _ordCntx in ords:
                if not _ordCntx.axisNodeObject.aspectValueDependsOnVars(aspect):
                    if ordCntx:
                        hasClash = True
                    else:
                        ordCntx = _ordCntx 
        else:
            hasClash = True
            
        if hasClash:
            from arelle.ModelFormulaObject import aspectStr
            view.modelXbrl.error("xbrlte:axisAspectClash",
                _("Aspect %(aspect)s covered by multiple axes."),
                modelObject=view.modelTable, aspect=aspectStr(aspect))
    if ordCntx:
        axisNodeObject = ordCntx.axisNodeObject
        if axisNodeObject.aspectValueDependsOnVars(aspect):
            return xOrdCntx.evaluate(axisNodeObject, 
                                     axisNodeObject.aspectValue, 
                                     otherOrdinate=yOrdCntx,
                                     evalArgs=(aspect,))
        return ordCntx.aspectValue(aspect)
    return None 


