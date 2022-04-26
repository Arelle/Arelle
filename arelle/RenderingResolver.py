'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os, io, sys, json
from collections import defaultdict
from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import QName
from arelle.ModelFormulaObject import Aspect
from arelle.ModelRenderingObject import (DefnMdlTable, DefnMdlBreakdown,
                                         DefnMdlDefinitionNode, DefnMdlClosedDefinitionNode, ModelRuleDefinitionNode,
                                         DefnMdlRelationshipDefinitionNode, DefnMdlAspectNode,
                                         DefnMdlConceptRelationshipNode, DefnMdlDimensionRelationshipNode,
                                         StrctMdlTableSet, StrctMdlTable, StrctMdlBreakdown, StrctMdlNode, 
                                         LayoutMdlTableSet, LayoutMdlTable, LayoutMdlAxis, LayoutMdlGroup, LayoutMdlHeader,                                          OPEN_ASPECT_ENTRY_SURROGATE)
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.XPathContext import XPathException

RENDER_UNITS_PER_CHAR = 16 # nominal screen units per char for wrapLength computation and adjustment

class ResolutionException(Exception):
    def __init__(self, code, message, **kwargs):
        self.kwargs = kwargs
        self.code = code
        self.message = message
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception {1}').format(self.code, self.message % self.kwargs)

def resolveAxesStructure(view, viewTblELR):
    if isinstance(viewTblELR, DefnMdlTable):
        # called with a defnMdlTable instead of an ELR
        
        # find an ELR for this table object
        defnMdlTable = viewTblELR
        strMdlTable = StrMdlTable(defnMdlTable)
        for rel in view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD)).fromModelObject(table):
            # find relationships in table's linkrole
            view.axisSubtreeRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD), rel.linkrole)
            return resolveTableAxesStructure(view, strMdlTable,
                                             view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD), rel.linkrole))
        # no relationships from table found
        return None
    
    # called with an ELR or list of ELRs
    tblBrkdnRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD), viewTblELR)
    view.axisSubtreeRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD), viewTblELR)
    if tblBrkdnRelSet is None or len(tblBrkdnRelSet.modelRelationships) == 0:
        view.modelXbrl.modelManager.addToLog(_("no table relationships for {0}").format(viewTblELR))
        return None
    
    # table name
    modelRoleTypes = view.modelXbrl.roleTypes.get(viewTblELR)
    if modelRoleTypes is not None and len(modelRoleTypes) > 0:
        view.roledefinition = modelRoleTypes[0].definition
        if view.roledefinition is None or view.roledefinition == "":
            view.roledefinition = os.path.basename(viewTblELR)    
    try:
        for defnMdlTable in tblBrkdnRelSet.rootConcepts:
            strMdlTable = StrMdlTable(defnMdlTable)
            return resolveTableAxesStructure(view, strMdlTable, tblBrkdnRelSet)
    except ResolutionException as ex:
        view.modelXbrl.error(ex.code, ex.message, exc_info=True, **ex.kwargs);        
    
    return None

def resolveTableAxesStructure(view, strMdlTable, tblBrkdnRelSet):
    defnMdlTable = strMdlTable.defnMdlNode
    view.dataCols = 0
    view.dataRows = 0
    view.dataFirstCol = 0
    view.dataFirstRow = 0
    view.colHdrNonStdRoles = []
    view.colHdrDocRow = False
    view.colHdrCodeRow = False
    view.colHdrRows = 0
    view.rowHdrNonStdRoles = []
    view.rowHdrCols = 0
    view.rowHdrColWidth = [0,]
    view.rowNonAbstractHdrSpanMin = [0,]
    view.rowHdrDocCol = False
    view.rowHdrCodeCol = False
    view.zAxisRows = 0
    zmostOrdCntx = None
    view.defnMdlTable = table
    view.aspectEntryObjectId = 0
    view.rendrCntx = table.renderingXPathContext
    
    # must be cartesian product of top level relationships
    tblBrkdnRels = tblBrkdnRelSet.fromModelObject(defnMdlTable)
    facts = view.modelXbrl.factsInInstance
    if facts:
        facts = defnMdlTable.filteredFacts(view.rendrCntx, view.modelXbrl.factsInInstance) # apply table filters
    for tblBrkdnRel in tblBrkdnRels:
        defnMdlBreakdown = tblBrkdnRel.toModelObject
        strMdlTable.defnMdlBreakdowns[defnMdlBreakdown.axis].append(defnMdlBreakdown)
    
    # do z's first to set variables needed by x and y axes expressions
    for axis in ("z", "x", "y"):
        dispositionHasNoBreakdown = True
        for i, tblBrkdnRel in enumerate(tblBrkdnRels):
            defnMdlBreakdown = tblBrkdnRel.toModelObject
            if tblBrkdnRel.axis == axis:
                strMdlBreakdown = StrctMdlBreakdown(strMdlTable, axis, defnMdlBreakdown, zmostOrdCntx, rendrCntx=view.rendrCntx)
                dispositionHasNoBreakdown = False
                expandDefinition(view, strMdlBreakdown, depth, None, 1, tblBrkdnRels)
                if axis == "x":
                    view.dataCols += strMdlBreakdown.leafNodeCount
                elif axis == "y":
                    view.dataRows += strMdlBreakdown.leafNodeCount
        if dispositionHasNoBreakdown: # no breakdown nodes for axis
            strMdlBreakdown = StrctMdlBreakdown(strMdlTable, axis, None, zmostOrdCntx, rendrCntx=view.rendrCntx)
            if axis in ("x", "y"):
                strMdlBreakdown.hasOpenNode = True
            expandDefinition(view, strMdlBreakdown, depth, None, 1, tblBrkdnRels)
            if axis == "x":
                view.dataCols += strMdlBreakdown.leafNodeCount
            elif axis == "y":
                view.dataRows += strMdlBreakdown.leafNodeCount
                
    # uncomment below for debugging Definition and Structural Models
    def jsonDefaultEncoder(obj):
        if isinstance(obj, StructuralNode):
            return {'1StructNode': str(obj),
                    '2Depth': obj.structuralDepth,
                    '2Group': obj.breakdownNode.genLabel() if obj.breakdownNode is not None else None,
                    '2isRollUp': obj.isRollUp,
                    '3Label': (obj.header() or obj.definitionNode.xlinkLabel).replace(OPEN_ASPECT_ENTRY_SURROGATE,"{OPEN_ASPECT_ENTRY_SURROGATE}")  if obj.definitionNode is not None else None,
                    '4Definition': "root" if not obj.parentStructuralNode else str(obj.definitionNode),
                    '5Breakdown': str(obj.breakdownNode),
                    '6ChildRollupNode': obj.rollUpStructuralNode.definitionNode.id if obj.rollUpStructuralNode is not None and obj.rollUpStructuralNode.definitionNode is not None else None,
                    '7ChildNodes': obj.childStructuralNodes,
                    '8zChoiceNodes':[z.definitionNode.id for z in obj.choiceStructuralNodes if z.definitionNode is not None] if obj.choiceStructuralNodes else None}
        raise TypeError("Type {} is not supported for json output".format(type(obj).__name__))
               
    with io.open(r"/Users/hermf/temp/test.json", 'wt') as fh:
        json.dump({"x":xTopStructuralNode, "y":yTopStructuralNode, "z":zTopStructuralNode}, 
                  fh,
                  sort_keys=True,
                  ensure_ascii=False, 
                  indent=2, 
                  default=jsonDefaultEncoder)
   
    view.colHdrTopRow = view.zAxisRows + 1 # need rest if combobox used (2 if view.zAxisRows else 1)
    for i in range(view.rowHdrCols):
        if view.rowNonAbstractHdrSpanMin[i]:
            lastRowMinWidth = view.rowNonAbstractHdrSpanMin[i] - sum(view.rowHdrColWidth[i] for j in range(i, view.rowHdrCols - 1))
            if lastRowMinWidth > view.rowHdrColWidth[view.rowHdrCols - 1]:
                view.rowHdrColWidth[view.rowHdrCols - 1] = lastRowMinWidth 
    #view.rowHdrColWidth = (60,60,60,60,60,60,60,60,60,60,60,60,60,60)
    # use as wraplength for all row hdr name columns 200 + fixed indent and abstract mins (not incl last name col)
    view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[:view.rowHdrCols + 1])
    if view.colHdrRows == 0:
        view.colHdrRows = 1 # always reserve aa col header row even if no labels for col headers
    view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + len(view.colHdrNonStdRoles)
    view.dataFirstCol = 1 + view.rowHdrCols + len(view.rowHdrNonStdRoles)
    #view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + view.colHdrDocRow + view.colHdrCodeRow
    #view.dataFirstCol = 1 + view.rowHdrCols + view.rowHdrDocCol + view.rowHdrCodeCol
    #for i in range(view.dataFirstRow + view.dataRows):
    #    view.gridView.rowconfigure(i)
    #for i in range(view.dataFirstCol + view.dataCols):
    #    view.gridView.columnconfigure(i)
    
    # organize hdrNonStdRoles so code (if any) is after documentation (if any)
    for hdrNonStdRoles in (view.colHdrNonStdRoles, view.rowHdrNonStdRoles):
        iCodeRole = -1
        for i, hdrNonStdRole in enumerate(hdrNonStdRoles):
            if 'code' in os.path.basename(hdrNonStdRole).lower():
                iCodeRole = i
                break
        if iCodeRole >= 0 and len(hdrNonStdRoles) > 1 and iCodeRole < len(hdrNonStdRoles) - 1:
            del hdrNonStdRoles[iCodeRole]
            hdrNonStdRoles.append(hdrNonStdRole)

    return (tblAxisRelSet, xTopStructuralNode, yTopStructuralNode, zTopStructuralNode)

def sortkey(obj):
    if isinstance(obj, ModelObject):
        return obj.objectIndex
    return obj

def childContainsOpenNodes(childStructuralNode):
    if isinstance(childStructuralNode.definitionNode, DefnMdlAspectNode) \
       and (childStructuralNode.isLabeled \
            or any([node.isEntryPrototype(default=False) for node in childStructuralNode.childStructuralNodes])):
        # either the child structural node has a concrete header or it contains a structure
        # that has not yet a concrete value
        return True
    else:
        for node in childStructuralNode.childStructuralNodes:
            if childContainsOpenNodes(node):
                return True
        return False

#def expandDefinition(view, strctMdlNode, depth, facts, i=None, tblAxisRels=None, processOpenDefinitionNode=True, rollUpNode=None):
def expandDefinition(view, strctMdlNode, depth, facts, i=None, tblBrkdnRels=None, processOpenDefinitionNode=True, rollUpNode=None):
    subtreeRelationships = view.axisSubtreeRelSet.fromModelObject(strctMdlNode.defnMdlObj)
    defnMdlNode = strMdlTable.defnMdlNode
    axis = strMdlTable.axis
    
    def checkLabelWidth(strctMdlNode, checkBoundFact=False):
        if axis == "y":
            # messages can't be evaluated, just use the text portion of format string
            label = strctMdlNode.header(lang=view.lang, 
                                          returnGenLabel=not checkBoundFact, 
                                          returnMsgFormatString=not checkBoundFact)
            if label:
                # need to et more exact word length in screen units
                widestWordLen = max(len(w) * RENDER_UNITS_PER_CHAR for w in label.split())
                # abstract only pertains to subtree of closed nodesbut not cartesian products or open nodes
                while strctMdlNode.depth >= len(view.rowHdrColWidth):
                    view.rowHdrColWidth.append(0)
                if defnMdlObj.isAbstract or not subtreeRelationships: # isinstance(definitionNode, ModelOpenDefinitionNode):                    
                    if widestWordLen > view.rowHdrColWidth[structuralNode.depth]:
                        view.rowHdrColWidth[strctMdlNode.depth] = widestWordLen
                else:
                    if widestWordLen > view.rowNonAbstractHdrSpanMin[strctMdlNode.depth]:
                        view.rowNonAbstractHdrSpanMin[strctMdlNode.depth] = widestWordLen
                        
    if axis == "z" and not strctMdlNode.aspects:
        strctMdlNode.aspects = view.zOrdinateChoices.get(defnMdlNode, None)
    if strctMdlNode and isinstance(defnMdlNode, (DefnMdlBreakdown, DefnMdlDefinitionNode)):
        try:
            try:
                ordCardinality, ordDepth = defnMdlNode.cardinalityAndDepth(strctMdlNode, handleXPathException=False)
            except XPathException as ex:
                if isinstance(defnMdlNode, DefnMdlConceptRelationshipNode):
                    view.modelXbrl.error("xbrlte:expressionNotCastableToRequiredType",
                        _("Relationship node %(xlinkLabel)s expression not castable to required type (%(xpathError)s)"),
                        modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName,
                        xpathError=str(ex))
                    return
            if (not defnMdlNode.isAbstract and
                isinstance(defnMdlNode, DefnMdlClosedDefinitionNode) and 
                ordCardinality == 0 and not defnMdlNode.isRollUp):
                view.modelXbrl.error("xbrlte:closedDefinitionNodeZeroCardinality",
                    _("Closed definition node %(xlinkLabel)s does not contribute at least one structural node"),
                    modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName)
            nestedDepth = depth + ordDepth
            # HF test
            cartesianProductNestedArgs = [view, nestedDepth, axis, facts, tblBrkdnRels, i]
            if axis == "z":
                if depth == 1: # choices (combo boxes) don't add to z row count
                    view.zAxisRows += 1 
            elif axis == "x":
                if ordDepth:
                    if nestedDepth - 1 > view.colHdrRows:
                        view.colHdrRows = nestedDepth - 1
                hdrNonStdRoles = view.colHdrNonStdRoles
            elif axis == "y":
                if ordDepth:
                    if nestedDepth - 1 > view.rowHdrCols: 
                        view.rowHdrCols = nestedDepth - 1
                        for j in range(1 + ordDepth):
                            view.rowHdrColWidth.append(RENDER_UNITS_PER_CHAR)  # min width for 'tail' of nonAbstract coordinate
                            view.rowNonAbstractHdrSpanMin.append(0)
                    checkLabelWidth(structuralNode, checkBoundFact=False)
                hdrNonStdRoles = view.rowHdrNonStdRoles
            if axis in ("x", "y"):
                hdrNonStdPosition = -1  # where a match last occured
                for rel in view.modelXbrl.relationshipSet(XbrlConst.elementLabel).fromModelObject(definitionNode):
                    if isinstance(rel.toModelObject, ModelResource) and rel.toModelObject.role != XbrlConst.genStandardLabel:
                        labelLang = rel.toModelObject.xmlLang
                        labelRole = rel.toModelObject.role
                        if (labelLang == view.lang or labelLang.startswith(view.lang) or view.lang.startswith(labelLang)
                            or ("code" in labelRole)):
                            labelRole = rel.toModelObject.role
                            if labelRole in hdrNonStdRoles:
                                hdrNonStdPosition = hdrNonStdRoles.index(labelRole)
                            else:
                                hdrNonStdRoles.insert(hdrNonStdPosition + 1, labelRole)
            isCartesianProductExpanded = False
            if not isinstance(defnMdlNode, DefnMdlAspectNode):
                isCartesianProductExpanded = True
                # note: reduced set of facts should always be passed to subsequent open nodes
                for axisSubtreeRel in subtreeRelationships:
                    childDefinitionNode = axisSubtreeRel.toModelObject
                    if childDefinitionNode.isRollUp and rollUpNode is None:
                        if childDefinitionNode.parentChildOrder == "parent-first":
                            expandDefinition(view, structuralNode, breakdownNode, childDefinitionNode, depth, axis, facts, i, tblAxisRels, rollUpNode=childDefinitionNode) #recurse
                        expandDefinition(view, structuralNode, breakdownNode, childDefinitionNode, depth, axis, facts, i, tblAxisRels) #recurse
                        if childDefinitionNode.parentChildOrder == "children-first":
                            expandDefinition(view, structuralNode, breakdownNode, childDefinitionNode, depth, axis, facts, i, tblAxisRels, rollUpNode=childDefinitionNode) #recurse
                    else:
                        if (isinstance(defnMdlNode, DefnMdlBreakdown) and
                            isinstance(childDefinitionNode, DefnMdlRelationshipDefinitionNode)): # append list products to composititionAxes subObjCntxs
                            childStructuralNode = structuralNode
                        else:
                            childStructuralNode = StructuralNode(structuralNode, breakdownNode, rollUpNode if rollUpNode is not None else childDefinitionNode) # others are nested structuralNode
                            if axis != "z":
                                structuralNode.childStructuralNodes.append(childStructuralNode)
                        if axis != "z":
                            expandDefinition(view, childStructuralNode, breakdownNode, childDefinitionNode, depth+ordDepth, axis, facts, i, tblAxisRels) #recurse
                            if not childContainsOpenNodes(childStructuralNode) :
                                # To be computed only if the structural node does not contain an open node
                                cartesianProductExpander(childStructuralNode, *cartesianProductNestedArgs)
                        else:
                            childStructuralNode.indent = depth - 1
                            if structuralNode.choiceStructuralNodes is not None:
                                structuralNode.choiceStructuralNodes.append(childStructuralNode)
                            expandDefinition(view, childStructuralNode, breakdownNode, childDefinitionNode, depth + 1, axis, facts) #recurse
                        if rollUpNode is not None:
                            structuralNode.rollUpStructuralNode = childStructuralNode
                    if rollUpNode is not None:
                        break # single iteration when expanding default node for roll up
                    
            #if not hasattr(structuralNode, "indent"): # probably also for multiple open axes
            if processOpenDefinitionNode:
                if isinstance(defnMdlNode, DefnMdlRelationshipDefinitionNode):
                    structuralNode.isLabeled = False
                    selfStructuralNodes = {} if defnMdlNode.axis.endswith('-or-self') else None
                    for rel in defnMdlNode.relationships(structuralNode):
                        if not isinstance(rel, list):
                            relChildStructuralNode = addRelationship(breakdownNode, defnMdlNode, rel, structuralNode, cartesianProductNestedArgs, selfStructuralNodes)
                        else:
                            addRelationships(breakdownNode, defnMdlNode, rel, relChildStructuralNode, cartesianProductNestedArgs)
                    if axis == "z":
                        # if definitionNode is first structural node child remove it
                        if structuralNode.choiceStructuralNodes and structuralNode.choiceStructuralNodes[0].defnMdlNode == defnMdlNode:
                            del structuralNode.choiceStructuralNodes[0]
                        # flatten hierarchy of nested structural nodes inot choice nodes (for single listbox)
                        def flattenChildNodesToChoices(childStructuralNodes, indent):
                            while childStructuralNodes:
                                choiceStructuralNode = childStructuralNodes.pop(0)
                                choiceStructuralNode.indent = indent
                                structuralNode.choiceStructuralNodes.append(choiceStructuralNode)
                                flattenChildNodesToChoices(choiceStructuralNode.childStructuralNodes, indent + 1)
                        if structuralNode.childStructuralNodes:
                            flattenChildNodesToChoices(structuralNode.childStructuralNodes, 0)
                    # set up by defnMdlNode.relationships
                    if isinstance(defnMdlNode, DefnMdlConceptRelationshipNode):
                        if (defnMdlNode._sourceQname != XbrlConst.qnXfiRoot and
                            definitionNode._sourceQname not in view.modelXbrl.qnameConcepts):
                            view.modelXbrl.error("xbrlte:invalidConceptRelationshipSource",
                                _("Concept relationship rule node %(xlinkLabel)s source %(source)s does not refer to an existing concept."),
                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, source=defnMdlNode._sourceQname)
                    elif isinstance(defnMdlNode, DefnMdlDimensionRelationshipNode):
                        dim = view.modelXbrl.qnameConcepts.get(defnMdlNode._dimensionQname)
                        if dim is None or not dim.isExplicitDimension:
                            view.modelXbrl.error("xbrlte:invalidExplicitDimensionQName",
                                _("Dimension relationship rule node %(xlinkLabel)s dimension %(dimension)s does not refer to an existing explicit dimension."),
                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, dimension=defnMdlNode._dimensionQname)
                        domMbr = view.modelXbrl.qnameConcepts.get(defnMdlNode._sourceQname)
                        if domMbr is None or not domMbr.isDomainMember:
                            view.modelXbrl.error("xbrlte:invalidDimensionRelationshipSource",
                                _("Dimension relationship rule node %(xlinkLabel)s source %(source)s does not refer to an existing domain member."),
                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, source=defnMdlNode._sourceQname)
                    if (defnMdlNode._axis in ("child", "child-or-self", "parent", "parent-or-self", "sibling", "sibling-or-self") and
                        (not isinstance(defnMdlNode._generations, _NUM_TYPES) or defnMdlNode._generations > 1)):
                        view.modelXbrl.error("xbrlte:relationshipNodeTooManyGenerations ",
                            _("Relationship rule node %(xlinkLabel)s formulaAxis %(axis)s implies a single generation tree walk but generations %(generations)s is greater than one."),
                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode._axis, generations=defnMdlNode._generations)
                    
                elif isinstance(defnMdlNode, DefnMdlAspectNode):
                    structuralNode.setHasOpenNode()
                    structuralNode.isLabeled = False
                    isCartesianProductExpanded = True
                    structuralNode.abstract = True # spanning ordinate acts as a subtitle
                    filteredFactsPartitions = structuralNode.evaluate(defnMdlNode, 
                                                                      defnMdlNode.filteredFactsPartitions, 
                                                                      evalArgs=(facts,))
                    if structuralNode._rendrCntx.formulaOptions.traceVariableFilterWinnowing:
                        view.modelXbrl.info("table:trace",
                            _("Filter node %(xlinkLabel)s facts partitions: %(factsPartitions)s"), 
                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel,
                            factsPartitions=str(filteredFactsPartitions))
                        
                    # ohly for fact entry (true if no parent open nodes or all are on entry prototype row)
                    if axis != "z":
                        childList = structuralNode.childStructuralNodes
                        if structuralNode.isEntryPrototype(default=True):
                            for i in range(getattr(view, "openBreakdownLines", 
                                                   # for file output, 1 entry row if no facts
                                                   0 if filteredFactsPartitions else 1)):
                                view.aspectEntryObjectId += 1
                                filteredFactsPartitions.append([FactPrototype(view, {"aspectEntryObjectId": OPEN_ASPECT_ENTRY_SURROGATE + str(view.aspectEntryObjectId)})])
                                if structuralNode.isEntryPrototype(default=False):
                                    break # only one node per cartesian product under outermost nested open entry row
                    else:
                        childList = structuralNode.choiceStructuralNodes
                    for factsPartition in filteredFactsPartitions:
                        childStructuralNode = StructuralNode(structuralNode, breakdownNode, defnMdlNode, contextItemFact=factsPartition[0])
                        
                        # store the partition for later reuse when spreading facts in body cells
                        childStructuralNode.factsPartition = factsPartition
                                 
                        childStructuralNode.indent = 0
                        childStructuralNode.depth -= 1  # for label width; parent is merged/invisible
                        childList.append(childStructuralNode)
                        checkLabelWidth(childStructuralNode, checkBoundFact=True)
                        #expandDefinition(view, childStructuralNode, breakdownNode, defnMdlNode, depth, axis, factsPartition, processOpenDefinitionNode=False) #recurse
                        cartesianProductNestedArgs[3] = factsPartition
                        # note: reduced set of facts should always be passed to subsequent open nodes
                        if subtreeRelationships:
                            for axisSubtreeRel in subtreeRelationships:
                                child2DefinitionNode = axisSubtreeRel.toModelObject
                                child2StructuralNode = StructuralNode(childStructuralNode, breakdownNode, child2DefinitionNode) # others are nested structuralNode
                                childStructuralNode.childStructuralNodes.append(child2StructuralNode)
                                expandDefinition(view, child2StructuralNode, breakdownNode, child2DefinitionNode, depth+ordDepth, axis, factsPartition) #recurse
                                cartesianProductExpander(child2StructuralNode, *cartesianProductNestedArgs)
                        else:
                            cartesianProductExpander(childStructuralNode, *cartesianProductNestedArgs)
                    # sort by header (which is likely to be typed dim value, for example)
                    childList.sort(key=lambda childStructuralNode: 
                                   childStructuralNode.header(lang=view.lang, 
                                                              returnGenLabel=False, 
                                                              returnMsgFormatString=False) 
                                   or '') # exception on trying to sort if header returns None
                    
                    # TBD if there is no abstract 'sub header' for these subOrdCntxs, move them in place of parent structuralNode 
                elif isinstance(defnMdlNode, ModelRuleDefinitionNode):
                    for constraintSet in defnMdlNode.constraintSets.values():
                        _aspectsCovered = constraintSet.aspectsCovered()
                        for aspect in _aspectsCovered:
                            if not constraintSet.aspectValueDependsOnVars(aspect):
                                if aspect == Aspect.CONCEPT:
                                    conceptQname = defnMdlNode.aspectValue(view.rendrCntx, Aspect.CONCEPT)
                                    concept = view.modelXbrl.qnameConcepts.get(conceptQname)
                                    if concept is None or not concept.isItem or concept.isDimensionItem or concept.isHypercubeItem:
                                        view.modelXbrl.error("xbrlte:invalidQNameAspectValue",
                                            _("Rule node %(xlinkLabel)s specifies concept %(concept)s does not refer to an existing primary item concept."),
                                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, concept=conceptQname)
                                elif isinstance(aspect, QName):
                                    memQname = defnMdlNode.aspectValue(view.rendrCntx, aspect)
                                    mem = view.modelXbrl.qnameConcepts.get(memQname)
                                    if isinstance(memQname, QName) and (mem is None or not mem.isDomainMember) and memQname != XbrlConst.qnFormulaDimensionSAV: # SAV is absent dimension member, reported in validateFormula:
                                        view.modelXbrl.error("xbrlte:invalidQNameAspectValue",
                                            _("Rule node %(xlinkLabel)s specifies domain member %(concept)s does not refer to an existing domain member concept."),
                                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, concept=memQname)
                    #if not defnMdlNode.constraintSets:
                    #    view.modelXbrl.error("xbrlte:incompleteAspectRule",
                    #        _("Rule node %(xlinkLabel)s does not specify an aspect value."),
                    #        modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel)
                if axis == "z":
                    if structuralNode.choiceStructuralNodes:
                        choiceNodeIndex = view.zOrdinateChoices.get(defnMdlNode, 0)
                        if isinstance(choiceNodeIndex, dict):  # aspect entry for open node
                            structuralNode.aspects = choiceNodeIndex
                            structuralNode.choiceNodeIndex = -1
                        elif choiceNodeIndex < len(structuralNode.choiceStructuralNodes):
                            structuralNode.choiceNodeIndex = choiceNodeIndex
                        else:
                            structuralNode.choiceNodeIndex = 0
                    view.zmostOrdCntx = structuralNode
                        
                if not isCartesianProductExpanded or (axis == "z" and structuralNode.choiceStructuralNodes is not None):
                    cartesianProductExpander(structuralNode, *cartesianProductNestedArgs)
                        
                if not structuralNode.childStructuralNodes: # childless root ordinate, make a child to iterate in producing table
                    subOrdContext = StructuralNode(structuralNode, breakdownNode, defnMdlNode)
        except ResolutionException as ex:
            if sys.version[0] >= '3':
                #import traceback
                #traceback.print_tb(ex.__traceback__)
                raise ex.with_traceback(ex.__traceback__)  # provide original traceback information
            else:
                raise ex
        except Exception as ex:
            e = ResolutionException("arelle:resolutionException",
                                    _("Exception in resolution of definition node %(node)s: %(error)s"),
                                    modelObject=defnMdlNode, node=defnMdlNode.qname, error=str(ex)
                                    )
            if sys.version[0] >= '3':
                raise e.with_traceback(ex.__traceback__)  # provide original traceback information
            else:
                raise e
    elif structuralNode and defnMdlNode is None: # no breakdown nodes for axis
        cartesianProductNestedArgs = [view, depth+1, axis, facts, (), i]
        cartesianProductExpander(structuralNode, *cartesianProductNestedArgs)
            
def cartesianProductExpander(childStructuralNode, view, depth, axis, facts, tblAxisRels, i):
    if i is not None: # recurse table relationships for cartesian product
        for j, tblRel in enumerate(tblAxisRels[i+1:]):
            tblObj = tblRel.toModelObject
            if isinstance(tblObj, DefnMdlDefinitionNode) and axis == tblRel.axis:        
                #addBreakdownNode(view, axis, tblObj)
                #if tblObj.cardinalityAndDepth(childStructuralNode)[1] or axis == "z":
                if axis == "z":
                    subOrdTblCntx = StructuralNode(childStructuralNode, tblObj, tblObj)
                    subOrdTblCntx._choiceStructuralNodes = []  # this is a breakdwon node
                    subOrdTblCntx.indent = 0 # separate breakdown not indented]
                    depth = 0 # cartesian next z is also depth 0
                    childStructuralNode.childStructuralNodes.append(subOrdTblCntx)
                else: # non-ordinate composition
                    subOrdTblCntx = childStructuralNode
                # predefined axes need facts sub-filtered
                if isinstance(childStructuralNode.defnMdlNode, DefnMdlClosedDefinitionNode):
                    matchingFacts = childStructuralNode.evaluate(childStructuralNode.defnMdlNode, 
                                                        childStructuralNode.defnMdlNode.filteredFacts, 
                                                        evalArgs=(facts,))
                else:
                    matchingFacts = facts
                # returns whether there were no structural node results
                subOrdTblCntx.abstract = True # can't be abstract across breakdown
                expandDefinition(view, subOrdTblCntx, tblObj, tblObj,
                            depth, # depth + (0 if axis == 'z' else 1), 
                            axis, matchingFacts, j + i + 1, tblAxisRels) #cartesian product
                break
                
def addRelationship(breakdownNode, relDefinitionNode, rel, structuralNode, cartesianProductNestedArgs, selfStructuralNodes=None):
    variableQname = relDefinitionNode.variableQname
    conceptQname = relDefinitionNode.conceptQname
    coveredAspect = relDefinitionNode.coveredAspect(structuralNode)
    if not coveredAspect:
        return None
    if selfStructuralNodes is not None:
        fromConceptQname = rel.fromModelObject.qname
        # is there an ordinate for this root object?
        if fromConceptQname in selfStructuralNodes:
            childStructuralNode = selfStructuralNodes[fromConceptQname]
        else:
            childStructuralNode = StructuralNode(structuralNode, breakdownNode, relDefinitionNode)
            structuralNode.childStructuralNodes.append(childStructuralNode)
            selfStructuralNodes[fromConceptQname] = childStructuralNode
            if variableQname:
                childStructuralNode.variables[variableQname] = []
            if conceptQname:
                childStructuralNode.variables[conceptQname] = fromConceptQname
            childStructuralNode.aspects[coveredAspect] = fromConceptQname
        relChildStructuralNode = StructuralNode(childStructuralNode, breakdownNode, relDefinitionNode)
        childStructuralNode.childStructuralNodes.append(relChildStructuralNode)
    else:
        relChildStructuralNode = StructuralNode(structuralNode, breakdownNode, relDefinitionNode)
        structuralNode.childStructuralNodes.append(relChildStructuralNode)
    preferredLabel = rel.preferredLabel
    if preferredLabel == XbrlConst.periodStartLabel:
        relChildStructuralNode.tagSelector = "table.periodStart"
    elif preferredLabel == XbrlConst.periodStartLabel:
        relChildStructuralNode.tagSelector = "table.periodEnd"
    if variableQname:
        relChildStructuralNode.variables[variableQname] = rel
    toConceptQname = rel.toModelObject.qname
    if conceptQname:
        relChildStructuralNode.variables[conceptQname] = toConceptQname
    relChildStructuralNode.aspects[coveredAspect] = toConceptQname
    cartesianProductExpander(relChildStructuralNode, *cartesianProductNestedArgs)
    return relChildStructuralNode

def addRelationships(breakdownNode, relDefinitionNode, rels, structuralNode, cartesianProductNestedArgs):
    childStructuralNode = None # holder for nested relationships
    for rel in rels:
        if not isinstance(rel, list):
            # first entry can be parent of nested list relationships
            childStructuralNode = addRelationship(breakdownNode, relDefinitionNode, rel, structuralNode, cartesianProductNestedArgs)
        elif childStructuralNode is None:
            childStructuralNode = StructuralNode(structuralNode, breakdownNode, relDefinitionNode)
            structuralNode.childStructuralNodes.append(childStructuralNode)
            addRelationships(breakdownNode, relDefinitionNode, rel, childStructuralNode, cartesianProductNestedArgs)
        else:
            addRelationships(breakdownNode, relDefinitionNode, rel, childStructuralNode, cartesianProductNestedArgs)
            


