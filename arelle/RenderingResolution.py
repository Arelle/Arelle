'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os, io, sys, json
from collections import defaultdict, OrderedDict
from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource
from arelle.ModelValue import QName
from arelle.ModelFormulaObject import Aspect, aspectStr
from arelle.ModelRenderingObject import (DefnMdlTable, DefnMdlBreakdown,
                                         DefnMdlDefinitionNode, DefnMdlClosedDefinitionNode, DefnMdlRuleDefinitionNode,
                                         DefnMdlRelationshipNode, DefnMdlAspectNode,
                                         DefnMdlConceptRelationshipNode, DefnMdlDimensionRelationshipNode,
                                         StrctMdlNode, StrctMdlTableSet, StrctMdlTable, StrctMdlBreakdown, StrctMdlStructuralNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE)
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.XPathContext import XPathException
NoneType = type(None)

RENDER_UNITS_PER_CHAR = 16 # nominal screen units per char for wrapLength computation and adjustment

class ResolutionException(Exception):
    def __init__(self, code, message, **kwargs):
        self.kwargs = kwargs
        self.code = code
        self.message = message
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception {1}').format(self.code, self.message % self.kwargs)

def resolveTableStructure(view, viewTblELR):
    if isinstance(viewTblELR, DefnMdlTable):
        # called with a defnMdlTable instead of an ELR
        
        # find an ELR for this table object
        defnMdlTable = viewTblELR
        strctMdlTable = StrctMdlTable(defnMdlTable)
        for rel in view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD)).fromModelObject(table):
            # find relationships in table's linkrole
            view.defnSubtreeRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD), rel.linkrole)
            return resolveTableAxesStructure(view, strctMdlTable,
                                             view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD), rel.linkrole))
        # no relationships from table found
        return None
    
    # called with an ELR or list of ELRs
    tblBrkdnRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD), viewTblELR)
    view.defnSubtreeRelSet = view.modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD), viewTblELR)
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
            strctMdlTable = StrctMdlTable(defnMdlTable)
            resolveTableAxesStructure(view, strctMdlTable, tblBrkdnRelSet)
            return strctMdlTable
    except ResolutionException as ex:
        view.modelXbrl.error(ex.code, ex.message, exc_info=True, **ex.kwargs);        
    
    return None

def resolveTableAxesStructure(view, strctMdlTable, tblBrkdnRelSet):
    defnMdlTable = strctMdlTable.defnMdlNode
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
    view.zmostOrdCntx = None
    view.defnMdlTable = defnMdlTable
    view.aspectEntryObjectId = 0
    view.rendrCntx = defnMdlTable.renderingXPathContext
    
    # must be cartesian product of top level relationships
    view.tblBrkdnRels = tblBrkdnRels = tblBrkdnRelSet.fromModelObject(defnMdlTable)
    
    facts = view.modelXbrl.factsInInstance
    if facts:
        facts = defnMdlTable.filteredFacts(view.rendrCntx, view.modelXbrl.factsInInstance) # apply table filters
    for tblBrkdnRel in tblBrkdnRels:
        defnMdlBreakdown = tblBrkdnRel.toModelObject
        strctMdlTable.defnMdlBreakdowns[tblBrkdnRel.axis].append(defnMdlBreakdown)
    
    # do z's first to set variables needed by x and y axes expressions
    for axis in ("z", "x", "y"):
        axisHasNoBreakdown = True
        for i, tblBrkdnRel in enumerate(tblBrkdnRels):
            defnMdlBreakdown = tblBrkdnRel.toModelObject
            if tblBrkdnRel.axis == axis:
                axisHasNoBreakdown = False
                strctMdlBreakdown = resolveDefinition(view, strctMdlTable, defnMdlBreakdown, 1, facts, 1, tblBrkdnRels, axis=axis)
                if axis == "x":
                    view.dataCols += strctMdlBreakdown.leafNodeCount
                elif axis == "y":
                    view.dataRows += strctMdlBreakdown.leafNodeCount
        if axisHasNoBreakdown:
            strctMdlBreakdown = resolveDefinition(view, strctMdlTable, None, 1, facts, 1, tblBrkdnRels, axis=axis)
            if axis == "x":
                view.dataCols += strctMdlBreakdown.leafNodeCount
                strctMdlBreakdown.setHasOpenNode()
            elif axis == "y":
                view.dataRows += strctMdlBreakdown.leafNodeCount
                strctMdlBreakdown.setHasOpenNode()
    # height balance each breakdown
    for strctMdlBrkdn in strctMdlTable.strctMdlChildNodes:
        def checkDepth(strctMdlNode, depth):
            m = depth
            for childStrctMdlNode in strctMdlNode.strctMdlChildNodes:
                m = checkDepth(childStrctMdlNode, depth + 1)
            return m
        breakdownDepth = checkDepth(strctMdlBrkdn, 0)
        # add roll up nodes to make axis depth uniform
        def heightBalance(strctMdlNode, depth):
            noChildren = True
            if depth < breakdownDepth and not strctMdlNode.strctMdlChildNodes:
                # add extra strct mdl child to be a rollup
                balancingChild = StrctMdlStructuralNode(strctMdlNode, strMdlNode.defnMdlNode)
                balancingChild.rollup = True
            for childStrctMdlNode in strctMdlNode.strctMdlChildNodes:
                heightBalance(childStrctMdlNode, depth + 1)
        heightBalance(strctMdlBrkdn, 0)        
                                
    # uncomment below for debugging Definition and Structural Models             
    def jsonStrctMdlEncoder(obj, indent="\n"):
        if isinstance(obj, StrctMdlNode):
            o = OrderedDict()
            o["strctMdlNode"] = type(obj).__name__
            if isinstance(obj, StrctMdlTable):
                o["entryFile"] = obj.defnMdlNode.modelXbrl.modelDocument.basename,
            if obj.axis:
                o["axis"] = obj.axis
            if obj.isAbstract:
                o["abstract"] = True
            if isinstance(obj, StrctMdlStructuralNode):
                if obj.hasChildRollup:
                    o["hasChildRollup"] = True
                if obj.rollup:
                    o["rollup"] = True
                o["structuralDepth"] = obj.structuralDepth
                _aspectsCovered = obj.aspectsCovered()
                if _aspectsCovered:
                    o["aspectsCovered"] = OrderedDict((aspectStr(a),str(obj.aspectValue(a)).replace(OPEN_ASPECT_ENTRY_SURROGATE, "OPEN_ASPECT_ENTRY_")) for a in _aspectsCovered)
            if obj.defnMdlNode is not None:
                o["defnMdlNode"] = str(obj.defnMdlNode)
            if obj.strctMdlChildNodes:
                o["strctMdlChildNodes"] = obj.strctMdlChildNodes
            # print(str(o))
            return o
        raise TypeError("Type {} is not supported for json output".format(type(obj).__name__))
    with io.open(r"/Users/hermf/temp/test.json", 'wt') as fh:
        json.dump(strctMdlTable, fh, ensure_ascii=False, indent=2, default=jsonStrctMdlEncoder)
   
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

def sortkey(obj):
    if isinstance(obj, ModelObject):
        return obj.objectIndex
    return obj

def childContainsOpenNodes(childStructuralNode):
    if isinstance(childStructuralNode.defnMdlNode, DefnMdlAspectNode) \
       and (childStructuralNode.isLabeled \
            or any([node.isEntryPrototype(default=False) for node in childStructuralNode.strctMdlChildNodes])):
        # either the child structural node has a concrete header or it contains a structure
        # that has not yet a concrete value
        return True
    else:
        for node in childStructuralNode.strctMdlChildNodes:
            if childContainsOpenNodes(node):
                return True
        return False

#def resolveDefinition(view, strctMdlNode, depth, facts, i=None, tblAxisRels=None, processOpenDefinitionNode=True, rollUpNode=None):
def resolveDefinition(view, strctMdlParent, defnMdlNode, depth, facts, i=None, tblBrkdnRels=None, rollUpNode=None, axis=None):
    if isinstance(defnMdlNode, (NoneType, DefnMdlBreakdown)):
        strctMdlNode = StrctMdlBreakdown(strctMdlParent, defnMdlNode, axis)
    else:
        strctMdlNode = StrctMdlStructuralNode(strctMdlParent, defnMdlNode)
        
    subtreeRels = view.defnSubtreeRelSet.fromModelObject(defnMdlNode)
    axis = strctMdlNode.axis
                        
    if isinstance(defnMdlNode, (DefnMdlBreakdown, DefnMdlDefinitionNode)):
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
            if not isinstance(defnMdlNode, DefnMdlAspectNode):
                # note: reduced set of facts should always be passed to subsequent open nodes
                for subtreeRel in subtreeRels:
                    childDefnMdlNode = subtreeRel.toModelObject
                    childStrctNode = resolveDefinition(view, strctMdlNode, childDefnMdlNode, depth, facts, i, tblBrkdnRels)
                    if childDefnMdlNode.isRollUp:
                        rollUpStrctNode = StrctMdlStructuralNode(childStrctNode, childDefnMdlNode)
                        rollUpStrctNode.rollup = True
                        childStrctNode.hasChildRollup = True
                        strctMdlNode.rollUpChildStrctMdlNode = rollUpStrctNode
                        if childDefnMdlNode.parentChildOrder == "parent-first":
                            childStrctNode.strctMdlChildNodes = childStrctNode.strctMdlChildNodes[-1:] + childStrctNode.strctMdlChildNodes[0:-1]
            if isinstance(defnMdlNode, DefnMdlRelationshipNode):
                strctMdlNode.isLabeled = False
                selfStructuralNodes = {} if defnMdlNode.axis.endswith('-or-self') else None
                for rel in defnMdlNode.relationships(strctMdlNode):
                    if not isinstance(rel, list):
                        relChildStructuralNode = addRelationship(defnMdlNode, rel, strctMdlParent, selfStructuralNodes)
                    else:
                        addRelationships(defnMdlNode, rel, strctMdlParent)
                # relationship strct mdl nodes were added to strctMdlNode, move them to parent and dereference strctMdlNode
                del strctMdlParent.strctMdlChildNodes[0] # remove unused strctMdlNode as rel str mdl nodes are owned by parent
                if axis == "z":
                    # if defnMdlNode is first structural node child remove it
                    if strctMdlParent.choiceStructuralNodes and strctMdlParent.choiceStructuralNodes[0].defnMdlNode == defnMdlNode:
                        del strctMdlParent.choiceStructuralNodes[0]
                    # flatten hierarchy of nested structural nodes inot choice nodes (for single listbox)
                    def flattenChildNodesToChoices(strctMdlChildNodes, indent):
                        while strctMdlChildNodes:
                            choiceStructuralNode = strctMdlChildNodes.pop(0)
                            choiceStructuralNode.indent = indent
                            strctMdlNode.choiceStructuralNodes.append(choiceStructuralNode)
                            flattenChildNodesToChoices(choiceStructuralNode.strctMdlChildNodes, indent + 1)
                    if strctMdlParent.strctMdlChildNodes:
                        flattenChildNodesToChoices(strctMdlParent.strctMdlChildNodes, 0)
                # set up by defnMdlNode.relationships
                if isinstance(defnMdlNode, DefnMdlConceptRelationshipNode):
                    if (defnMdlNode._sourceQname != XbrlConst.qnXfiRoot and
                        defnMdlNode._sourceQname not in view.modelXbrl.qnameConcepts):
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
                strctMdlNode.setHasOpenNode()
                strctMdlNode.isLabeled = False
                strctMdlNode.abstract = True # spanning ordinate acts as a subtitle
                filteredFactsPartitions = strctMdlNode.evaluate(defnMdlNode, 
                                                                  defnMdlNode.filteredFactsPartitions, 
                                                                  evalArgs=(facts,))
                if strctMdlNode._rendrCntx.formulaOptions.traceVariableFilterWinnowing:
                    view.modelXbrl.info("table:trace",
                        _("Filter node %(xlinkLabel)s facts partitions: %(factsPartitions)s"), 
                        modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel,
                        factsPartitions=str(filteredFactsPartitions))
                    
                # ohly for fact entry (true if no parent open nodes or all are on entry prototype row)
                if axis != "z":
                    childList = strctMdlNode.strctMdlChildNodes
                    if strctMdlNode.isEntryPrototype(default=True):
                        for i in range(getattr(view, "openBreakdownLines", 
                                               # for file output, 1 entry row if no facts
                                               0 if filteredFactsPartitions else 1)):
                            view.aspectEntryObjectId += 1
                            filteredFactsPartitions.append([FactPrototype(view, {"aspectEntryObjectId": OPEN_ASPECT_ENTRY_SURROGATE + str(view.aspectEntryObjectId)})])
                            if strctMdlNode.isEntryPrototype(default=False):
                                break # only one node per cartesian product under outermost nested open entry row
                else:
                    childList = strctMdlNode.choiceStructuralNodes
                for factsPartition in filteredFactsPartitions:
                    childStructuralNode = StrctMdlStructuralNode(strctMdlNode, defnMdlNode, contextItemFact=factsPartition[0])
                    
                    # store the partition for later reuse when spreading facts in body cells
                    childStructuralNode.factsPartition = factsPartition
                             
                    childStructuralNode.indent = 0
                    # childStructuralNode.depth -= 1  # for label width; parent is merged/invisible
                    if axis == "z":
                        childList.append(childStructuralNode)
                    # checkLabelWidth(childStructuralNode, checkBoundFact=True)
                    #resolveDefinition(view, childStructuralNode, defnMdlNode, depth, axis, factsPartition, processOpenDefinitionNode=False) #recurse
                    if subtreeRels:
                        for subtreeRel in subtreeRels:
                            child2DefinitionNode = subtreeRel.toModelObject
                            child2StructuralNode = StrctMdlStructuralNode(childStructuralNode, child2DefinitionNode) # others are nested structuralNode
                            childStructuralNode.strctMdlChildNodes.append(child2StructuralNode)
                            resolveDefinition(view, child2StructuralNode, child2DefinitionNode, depth+ordDepth, factsPartition) #recurse
                # sort by header (which is likely to be typed dim value, for example)
                childList.sort(key=lambda childStructuralNode: 
                               childStructuralNode.header(lang=view.lang, 
                                                          returnGenLabel=False, 
                                                          returnMsgFormatString=False) 
                               or '') # exception on trying to sort if header returns None
                
                # TBD if there is no abstract 'sub header' for these subOrdCntxs, move them in place of parent structuralNode 
            elif isinstance(defnMdlNode, DefnMdlRuleDefinitionNode):
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
                if strctMdlNode.choiceStructuralNodes:
                    choiceNodeIndex = view.zOrdinateChoices.get(defnMdlNode, 0)
                    if isinstance(choiceNodeIndex, dict):  # aspect entry for open node
                        strctMdlNode.choiceNodeIndex = -1
                    elif choiceNodeIndex < len(strctMdlNode.choiceStructuralNodes):
                        strctMdlNode.choiceNodeIndex = choiceNodeIndex
                    else:
                        strctMdlNode.choiceNodeIndex = 0
                view.zmostOrdCntx = strctMdlNode
                    
            if isinstance(defnMdlNode, (NoneType, DefnMdlBreakdown)) and not strctMdlNode.strctMdlChildNodes: # childless root ordinate, make a child to iterate in producing table
                subOrdContext = StrctMdlStructuralNode(strctMdlNode, defnMdlNode)
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
        
    return strctMdlNode
            
def addRelationship(relDefinitionNode, rel, strctMdlNode, selfStructuralNodes=None):
    variableQname = relDefinitionNode.variableQname
    conceptQname = relDefinitionNode.conceptQname
    coveredAspect = relDefinitionNode.coveredAspect(strctMdlNode)
    if not coveredAspect:
        return None
    if selfStructuralNodes is not None:
        fromConceptQname = rel.fromModelObject.qname
        # is there an ordinate for this root object?
        if fromConceptQname in selfStructuralNodes:
            childStructuralNode = selfStructuralNodes[fromConceptQname]
        else:
            childStructuralNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
            selfStructuralNodes[fromConceptQname] = childStructuralNode
            if variableQname:
                childStructuralNode.variables[variableQname] = []
            if conceptQname:
                childStructuralNode.variables[conceptQname] = fromConceptQname
            childStructuralNode.aspects[coveredAspect] = fromConceptQname
        relChildStructuralNode = StrctMdlStructuralNode(childStructuralNode, relDefinitionNode)
    else:
        relChildStructuralNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
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
    return relChildStructuralNode

def addRelationships(relDefinitionNode, rels, strctMdlNode):
    childStructuralNode = None # holder for nested relationships
    for rel in rels:
        if not isinstance(rel, list):
            # first entry can be parent of nested list relationships
            childStructuralNode = addRelationship(relDefinitionNode, rel, strctMdlNode)
        elif childStructuralNode is None:
            childStructuralNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
            addRelationships(relDefinitionNode, rel, childStructuralNode)
        else:
            addRelationships(relDefinitionNode, rel, childStructuralNode)
            


