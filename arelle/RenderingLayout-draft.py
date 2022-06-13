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
from arelle.ModelFormulaObject import Aspect
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

def layoutTableStructure(view, strctMdlTable):
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
    view.rendrCntx = defnMdlTable.renderingXPathContext
    
    facts = view.modelXbrl.factsInInstance
    if facts:
        facts = defnMdlTable.filteredFacts(view.rendrCntx, view.modelXbrl.factsInInstance) # apply table filters
    
    # do z's first to set variables needed by x and y axes expressions
    for axis in ("z", "x", "y"):
        for strctMdlBreakdown in strctMdlTable.strctMdlChildNodes:
            if strctMdlBreakdown.axis == axis:
                layoutStrMdlNode(view, strctMdlTable, strctMdlBreakdown, 1, facts, 1)
                if axis == "x":
                    view.dataCols += strctMdlBreakdown.leafNodeCount
                elif axis == "y":
                    view.dataRows += strctMdlBreakdown.leafNodeCount
                
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
                if obj.hasRollUpChild:
                    o["hasRollUpChild"] = True
                if obj.isRollUp:
                    o["isRollUp"] = True
                o["structuralDepth"] = obj.structuralDepth
                o["aspectsCovered"] = str(obj.aspectsCovered)
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

    
def checkLabelWidth(view, strctMdlNode, subtreeRels, checkBoundFact=False):
    if strctMdlNode.axis == "y":
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
            if strctMdlNode.defnMdlNode.isAbstract or not subtreeRels:                   
                if widestWordLen > view.rowHdrColWidth[strctMdlNode.depth]:
                    view.rowHdrColWidth[strctMdlNode.depth] = widestWordLen
            else:
                if widestWordLen > view.rowNonAbstractHdrSpanMin[strctMdlNode.depth]:
                    view.rowNonAbstractHdrSpanMin[strctMdlNode.depth] = widestWordLen

#def resolveDefinition(view, strctMdlNode, depth, facts, i=None, tblAxisRels=None, processOpenDefinitionNode=True, rollUpNode=None):
def layoutStrMdlNode(view, strctMdlParent, strctMdlNode, depth, facts, i=None, rollUpNode=None):
    axis = strctMdlNode.axis
                        
    if axis == "z" and not strctMdlNode.aspects:
        strctMdlNode.aspects = view.zOrdinateChoices.get(defnMdlNode, None)
    if isinstance(defnMdlNode, (DefnMdlBreakdown, DefnMdlDefinitionNode)):
        try:
            for strctMdlChild in strctMdlNode.strctMdlEffectiveChildNodes:
                layoutStrMdlNode(view, strctMdlNode, strctMdlChild, depth, facts)
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
                    checkLabelWidth(strctMdlNode, checkBoundFact=False)
                hdrNonStdRoles = view.rowHdrNonStdRoles
            if axis in ("x", "y"):
                hdrNonStdPosition = -1  # where a match last occured
                for rel in view.modelXbrl.relationshipSet(XbrlConst.elementLabel).fromModelObject(defnMdlNode):
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
                for subtreeRel in subtreeRels:
                    childDefnMdlNode = subtreeRel.toModelObject
                    if childDefnMdlNode.isRollUp:
                        rollUpStrctNode = StrctMdlStructuralNode(strctMdlParent, childDefnMdlNode)
                        if childDefnMdlNode.parentChildOrder == "parent-first":
                            rollUpStrctNode.rollUpChildStrctMdlNode = \
                                resolveDefinition(view, rollUpStrctNode, childDefnMdlNode, depth, axis, facts, i, tblBrkdnRels) #recurse
                        resolveDefinition(view, rollUpStrctNode, childDefnMdlNode, depth, axis, facts, i, tblBrkdnRels) #recurse
                        if childDefnMdlNode.parentChildOrder == "children-first":
                            rollUpStrctNode.rollUpChildStrctMdlNode = \
                                resolveDefinition(view, rollUpStrctNode, childDefnMdlNode, depth, axis, facts, i, tblBrkdnRels) #recurse
                    else:
                        childStrctNode = resolveDefinition(view, strctMdlNode, childDefnMdlNode, depth, axis, facts, i, tblBrkdnRels)
            if isinstance(defnMdlNode, DefnMdlRelationshipNode):
                strctMdlNode.isLabeled = False
                selfStructuralNodes = {} if defnMdlNode.axis.endswith('-or-self') else None
                for rel in defnMdlNode.relationships(strctMdlNode):
                    if not isinstance(rel, list):
                        relChildStructuralNode = addRelationship(breakdownNode, defnMdlNode, rel, strctMdlNode, cartesianProductNestedArgs, selfStructuralNodes)
                    else:
                        addRelationships(breakdownNode, defnMdlNode, rel, relChildStructuralNode, cartesianProductNestedArgs)
                if axis == "z":
                    # if defnMdlNode is first structural node child remove it
                    if strctMdlNode.choiceStructuralNodes and strctMdlNode.choiceStructuralNodes[0].defnMdlNode == defnMdlNode:
                        del strctMdlNode.choiceStructuralNodes[0]
                    # flatten hierarchy of nested structural nodes inot choice nodes (for single listbox)
                    def flattenChildNodesToChoices(strctMdlChildNodes, indent):
                        while strctMdlChildNodes:
                            choiceStructuralNode = strctMdlChildNodes.pop(0)
                            choiceStructuralNode.indent = indent
                            strctMdlNode.choiceStructuralNodes.append(choiceStructuralNode)
                            flattenChildNodesToChoices(choiceStructuralNode.strctMdlChildNodes, indent + 1)
                    if strctMdlNode.strctMdlChildNodes:
                        flattenChildNodesToChoices(strctMdlNode.strctMdlChildNodes, 0)
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
                isCartesianProductExpanded = True
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
                    childStructuralNode = StrctMdlStructuralNode(strctMdlNode, breakdownNode, defnMdlNode, contextItemFact=factsPartition[0])
                    
                    # store the partition for later reuse when spreading facts in body cells
                    childStructuralNode.factsPartition = factsPartition
                             
                    childStructuralNode.indent = 0
                    childStructuralNode.depth -= 1  # for label width; parent is merged/invisible
                    childList.append(childStructuralNode)
                    checkLabelWidth(childStructuralNode, checkBoundFact=True)
                    #resolveDefinition(view, childStructuralNode, breakdownNode, defnMdlNode, depth, axis, factsPartition, processOpenDefinitionNode=False) #recurse
                    cartesianProductNestedArgs[3] = factsPartition
                    # note: reduced set of facts should always be passed to subsequent open nodes
                    if subtreeRels:
                        for subtreeRel in subtreeRels:
                            child2DefinitionNode = subtreeRel.toModelObject
                            child2StructuralNode = StrctMdlStructuralNode(childStructuralNode, breakdownNode, child2DefinitionNode) # others are nested structuralNode
                            childStructuralNode.strctMdlChildNodes.append(child2StructuralNode)
                            resolveDefinition(view, child2StructuralNode, breakdownNode, child2DefinitionNode, depth+ordDepth, axis, factsPartition) #recurse
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
                        strctMdlNode.aspects = choiceNodeIndex
                        strctMdlNode.choiceNodeIndex = -1
                    elif choiceNodeIndex < len(strctMdlNode.choiceStructuralNodes):
                        strctMdlNode.choiceNodeIndex = choiceNodeIndex
                    else:
                        strctMdlNode.choiceNodeIndex = 0
                view.zmostOrdCntx = strctMdlNode
                    
            if not isCartesianProductExpanded or (axis == "z" and strctMdlNode.choiceStructuralNodes is not None):
                cartesianProductExpander(strctMdlNode, *cartesianProductNestedArgs)
                    
            if isinstance(strctMdlNode, StrctMdlBreakdown) and not strctMdlNode.strctMdlChildNodes: # childless root ordinate, make a child to iterate in producing table
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
