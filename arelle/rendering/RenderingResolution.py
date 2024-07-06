'''
See COPYRIGHT.md for copyright information.
'''
import os, io, sys, json
from collections import defaultdict, OrderedDict
from arelle import XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelResource, ModelRelationship
from arelle.ModelValue import QName
from arelle.Aspect import Aspect, aspectStr, aspectModelAspect
from arelle.ModelRenderingObject import (ResolutionException, DefnMdlTable, DefnMdlBreakdown,
                                         DefnMdlDefinitionNode, DefnMdlClosedDefinitionNode, DefnMdlRuleDefinitionNode,
                                         DefnMdlRelationshipNode, DefnMdlAspectNode, DefnMdlOpenDefinitionNode,
                                         DefnMdlConceptRelationshipNode, DefnMdlDimensionRelationshipNode,
                                         StrctMdlNode, StrctMdlTableSet, StrctMdlTable, StrctMdlBreakdown, StrctMdlStructuralNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_IMPLIES_DEFAULT_MEMBER,
                                         ROLLUP_FOR_CONCEPT_RELATIONSHIP_NODE, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         ROLLUP_FOR_CLOSED_DEFINITION_NODE, ROLLUP_FOR_OPEN_DEFINITION_NODE,
                                         ROLLUP_FOR_DEFINITION_NODE,
                                         UNREPORTED_ASPECT_SORT_VALUE,
                                         aspectStrctNodes)
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.PythonUtil import flattenSequence, flattenToSet
from arelle.formula.XPathContext import XPathException, FunctionArgType
from numbers import Number
NoneType = type(None)
EMPTY_LIST = []
EMPTY_DICT = {}

TRACE_RESOLUTION = False
TRACE_TABLE_STRUCTURE = True

RENDER_UNITS_PER_CHAR = 16 # nominal screen units per char for wrapLength computation and adjustment

def prod(seq):
    p = 1
    for n in seq:
        p *= n
    return p

def resolveTableStructure(view, viewTblELR):
    if isinstance(viewTblELR, DefnMdlTable):
        # called with a defnMdlTable instead of an ELR

        # find an ELR for this table object
        defnMdlTable = viewTblELR
        strctMdlTable = StrctMdlTable(defnMdlTable)
        for rel in view.modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD)).fromModelObject(defnMdlTable):
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
            view.rendrCntx = defnMdlTable.renderingXPathContext
            strctMdlTableSet = StrctMdlTableSet(defnMdlTable)
            referencedVariables = defnMdlTable.variableRefs()
            for tblParamRel in view.modelXbrl.relationshipSet((XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)).fromModelObject(defnMdlTable):
                referencedVariables.add(tblParamRel.variableQname) # https://gitlab.xbrl.org/rendering/table-linkbase/-/issues/32#note_20551
            # determine number of tables based on cartesian product of multi-valued parameters
            varSeqValues = OrderedDict(( # order tables by lexicographic key order
                (name, flattenSequence(view.rendrCntx.inScopeVars.get(name,())))
                for name in sorted(referencedVariables,reverse=True))) # want last variable to iterate first
            varSeqIndx = dict((name,0) for name in varSeqValues)
            for tblNum in range(prod((len(seqVal) or 1)
                                     for name, seqVal in varSeqValues.items())):
                strctMdlTable = StrctMdlTable(strctMdlTableSet, defnMdlTable)
                for name, seqVal in varSeqValues.items():
                    if len(seqVal) > 0:
                        thisSeqVal = seqVal[varSeqIndx[name]]
                        view.rendrCntx.inScopeVars[name] = [thisSeqVal]
                        strctMdlTable.tblParamValues[name] = thisSeqVal
                resolveTableAxesStructure(view, strctMdlTable, tblBrkdnRelSet)
                # iterate paramSeqIndex
                for name, seqVal in varSeqValues.items():
                    varSeqIndx[name] += 1
                    if varSeqIndx[name] < len(seqVal):
                        view.rendrCntx.inScopeVars[name] = seqVal[varSeqIndx[name]]
                        break
                    varSeqIndx[name] = 0 # reset this param and set next one
                    if len(seqVal) > 0:
                        view.rendrCntx.inScopeVars[name] = seqVal[varSeqIndx[name]]
            return strctMdlTableSet
    except ResolutionException as ex:
        #traceback.print_exc()
        view.modelXbrl.error(ex.code, ex.message, exc_info=True, **ex.kwargs);

    return None

def resolveTableAxesStructure(view, strctMdlTable, tblBrkdnRelSet):
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
    view.zAxisBreakdowns = 0
    view.zmostOrdCntx = None
    view.defnMdlTable = defnMdlTable = strctMdlTable.defnMdlNode
    view.aspectEntryObjectId = 0

    # must be cartesian product of top level relationships
    view.tblBrkdnRels = tblBrkdnRels = tblBrkdnRelSet.fromModelObject(defnMdlTable)

    for tblBrkdnRel in tblBrkdnRels:
        defnMdlBreakdown = tblBrkdnRel.toModelObject
        strctMdlTable.defnMdlBreakdowns[tblBrkdnRel.axis].append(defnMdlBreakdown)

    facts = view.modelXbrl.factsInInstance
    if facts:
        facts = defnMdlTable.filteredFacts(view.rendrCntx, view.modelXbrl.factsInInstance) # apply table filters
    # do z's first to set variables needed by x and y axes expressions
    for axis in ("z", "y", "x"):
        axisBrkdnRels = [r for r in tblBrkdnRels if r.axis == axis]
        for tblBrkdnRel in axisBrkdnRels:
            defnMdlBreakdown = tblBrkdnRel.toModelObject
            strctMdlBreakdown = resolveDefinition(view, strctMdlTable, defnMdlBreakdown, 0, facts, 0, axisBrkdnRels, axis=axis)
            # perform any supplemental leveling of child str mdl nodes
            descendantDepths = [getDepth(d) for d in strctMdlBreakdown.strctMdlChildNodes]
            if min(descendantDepths) != max (descendantDepths):
                addDescendantRollups(strctMdlBreakdown)
            # add any defaulted dimensions needed on leaf nodes
            addDefaultedDimensionsToLeafNodes(strctMdlBreakdown)
            if axis == "x":
                view.dataCols += strctMdlBreakdown.leafNodeCount
            elif axis == "y":
                view.dataRows += strctMdlBreakdown.leafNodeCount
            elif axis == "z":
                view.zAxisBreakdowns = len(axisBrkdnRels)
            break # 2nd and following breakdown nodes resolved by cartesianProductExpander within resolveDefinition
        if not axisBrkdnRels: # no breakdown rels
            strctMdlBreakdown = resolveDefinition(view, strctMdlTable, None, 1, facts, 0, axisBrkdnRels, axis=axis)
            strctMdlBreakdown.setHasOpenNode()
            if axis == "x":
                view.dataCols += strctMdlBreakdown.leafNodeCount
                strctMdlBreakdown.setHasOpenNode()
            elif axis == "y":
                view.dataRows += strctMdlBreakdown.leafNodeCount
                strctMdlBreakdown.setHasOpenNode()
    # check for clashing and unresolved tagSelectors
    strctMdlAxisNodes = defaultdict(list)
    def compileAlignedStrctNodes(strctNode):
        childNodes = strctNode.strctMdlChildNodes
        if not childNodes: # this is a leaf node
            if not isinstance(strctNode, StrctMdlBreakdown) and not strctNode.defnMdlNode.isAbstract:
                strctMdlAxisNodes[strctNode.axis].append(strctNode)
        else:
            for childStrctNode in childNodes:
                compileAlignedStrctNodes(childStrctNode)
    for axis in ("z", "y", "x"):
        compileAlignedStrctNodes(strctMdlTable.strctMdlFirstAxisBreakdown(axis))
    for zStrctMdlNode in strctMdlAxisNodes.get("z", [None]):
        zAspectStrctNodes = aspectStrctNodes(zStrctMdlNode)
        for yStrctMdlNode in strctMdlAxisNodes.get("y", [None]):
            yAspectStrctNodes = aspectStrctNodes(yStrctMdlNode)
            for xStrctMdlNode in strctMdlAxisNodes.get("x", [None]):
                xAspectStrctNodes = aspectStrctNodes(xStrctMdlNode)
                stNodes = (zStrctMdlNode, yStrctMdlNode, xStrctMdlNode)
                cellTagSelectors = set(ts for sn in stNodes if sn for ts in sn.tagSelectors if ts)
                if {"table.periodStart","table.periodEnd"} & cellTagSelectors:
                    cellTagSelectors &= {"table.periodStart","table.periodEnd"}
                for _aspectStrctNodes in (zAspectStrctNodes.values(), yAspectStrctNodes.values(), xAspectStrctNodes.values()):
                    for aspectStrctNode in flattenToSet(_aspectStrctNodes):
                        strctNodeTags = aspectStrctNode.defnMdlNode.constraintSets.keys()
                        if len(cellTagSelectors & strctNodeTags) > 1:
                            view.modelXbrl.error("xbrlte:tagSelectorClash",
                                _("Cell has multiple tag selectors for same aspect node %(nodeId)s %(clashingSelectors)s"),
                                modelObject=stNodes, clashingSelectors=", ".join(cellTagSelectors & strctNodeTags), nodeId=aspectStrctNode.defnMdlNode.id)
                        for cellTagSelector in cellTagSelectors:
                            if cellTagSelector not in strctNodeTags and None not in strctNodeTags:
                                view.modelXbrl.error("xbrlte:noMatchingConstraintSet",
                                    _("Cell has missing constraint set for tag selector %(cellTagSelector)s, node %(nodeId)s"),
                                    modelObject=stNodes, cellTagSelector=cellTagSelector, nodeId=aspectStrctNode.defnMdlNode.id)

    view.colHdrTopRow = view.zAxisBreakdowns # need rest if combobox used (2 if view.zAxisRows else 1)
    for i in range(view.rowHdrCols):
        if view.rowNonAbstractHdrSpanMin[i]:
            lastRowMinWidth = view.rowNonAbstractHdrSpanMin[i] - sum(view.rowHdrColWidth[i] for j in range(i, view.rowHdrCols - 1))
            if lastRowMinWidth > view.rowHdrColWidth[view.rowHdrCols - 1]:
                view.rowHdrColWidth[view.rowHdrCols - 1] = lastRowMinWidth
    #view.rowHdrColWidth = (60,60,60,60,60,60,60,60,60,60,60,60,60,60)
    # use as wraplength for all row hdr name columns 200 + fixed indent and abstract mins (not incl last name col)
    view.rowHdrWrapLength = 200 + sum(view.rowHdrColWidth[:view.rowHdrCols + 1])
    if view.colHdrRows == 0:
        view.colHdrRows = 1 # always reserve a col header row even if no labels for col headers
    view.dataFirstRow = view.colHdrTopRow + view.colHdrRows + len(view.colHdrNonStdRoles)
    view.dataFirstCol = view.rowHdrCols + len(view.rowHdrNonStdRoles)
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
    if TRACE_RESOLUTION: print(
        f"dataCols {view.dataCols} dataRows {view.dataRows} dataFirstCol {view.dataFirstCol} dataFirstRow {view.dataFirstRow} "
        f"colHdrRows {view.colHdrRows} rowHdrCols {view.rowHdrCols} zAxisBreakdowns {view.zAxisBreakdowns} "
        f"colHdrTopRow {view.colHdrTopRow} colHdrRows {view.colHdrRows} colHdrNonStdRoles {len(view.colHdrNonStdRoles)} "
        f"rowHdrNonStdRoles {len(view.rowHdrNonStdRoles)}"
        )

def sortkey(obj):
    if isinstance(obj, ModelObject):
        return obj.objectIndex
    return obj

def childContainsOpenNodes(childStrctMdlNode):
    if childStrctMdlNode is None:
        return False
    if isinstance(childStrctMdlNode.defnMdlNode, DefnMdlAspectNode) \
       and (childStrctMdlNode.isLabeled \
            or any([node.isEntryPrototype(default=False) for node in childStrctMdlNode.strctMdlChildNodes])):
        # either the child structural node has a concrete header or it contains a structure
        # that has not yet a concrete value
        return True
    else:
        for node in childStrctMdlNode.strctMdlChildNodes:
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
                view.rowHdrColWidth.append(RENDER_UNITS_PER_CHAR)
                view.rowNonAbstractHdrSpanMin.append(0)
            if strctMdlNode.defnMdlNode.isAbstract or not subtreeRels:
                if widestWordLen > view.rowHdrColWidth[strctMdlNode.depth]:
                    view.rowHdrColWidth[strctMdlNode.depth] = widestWordLen
            else:
                if widestWordLen > view.rowNonAbstractHdrSpanMin[strctMdlNode.depth]:
                    view.rowNonAbstractHdrSpanMin[strctMdlNode.depth] = widestWordLen

#def resolveDefinition(view, strctMdlNode, depth, facts, i=None, tblAxisRels=None, processOpenDefinitionNode=True, rollUpNode=None):
def resolveDefinition(view, strctMdlParent, defnMdlNode, depth, facts, iBrkdn=None, axisBrkdnRels=None, rollUpNode=None, axis=None, mergeAspects=None):
    if isinstance(defnMdlNode, (NoneType, DefnMdlBreakdown)):
        strctMdlNode = StrctMdlBreakdown(strctMdlParent, defnMdlNode, axis)
    else:
        if isinstance(defnMdlNode, (DefnMdlRelationshipNode,DefnMdlAspectNode)) or mergeAspects or defnMdlNode.isMerged:
            strctMdlNode = strctMdlParent # all children are added during relationship navigatio below
        else:
            strctMdlNode = StrctMdlStructuralNode(strctMdlParent, defnMdlNode)
    if strctMdlParent.axis:
        axis = strctMdlParent.axis

    subtreeRels = view.defnSubtreeRelSet.fromModelObject(defnMdlNode)

    if isinstance(defnMdlNode, (DefnMdlBreakdown, DefnMdlDefinitionNode)):
        try:
            try:
                ordCardinality, ordDepth = defnMdlNode.cardinalityAndDepth(strctMdlNode, handleXPathException=False)
            except (XPathException, FunctionArgType, ResolutionException) as ex:
                if (isinstance(defnMdlNode, DefnMdlRelationshipNode) and
                    type(ex) == FunctionArgType and ex.argNum == 5 and isinstance(ex.value, int) and ex.value >= 0):
                    view.modelXbrl.error("xbrlte:relationshipNodeTooManyGenerations",
                                         ex.expectedType,
                                         modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName)
                elif isinstance(defnMdlNode, DefnMdlRelationshipNode) and type(ex) == ResolutionException:
                    view.modelXbrl.error(ex.code,
                    _("Relationship node %(xlinkLabel)s expression not castable to required type (%(error)s)"),
                    modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName,
                    error=ex.message)
                else:
                    view.modelXbrl.error("xbrlte:expressionNotCastableToRequiredType",
                    _("Relationship node %(xlinkLabel)s expression not castable to required type (%(xpathError)s)"),
                    modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName,
                    xpathError=str(ex))
                return
            if (not defnMdlNode.isAbstract and
                isinstance(defnMdlNode, DefnMdlClosedDefinitionNode) and
                ordCardinality == 0 and not defnMdlNode.childrenCoverSameAspects):
                view.modelXbrl.error("xbrlte:closedDefinitionNodeZeroCardinality",
                    _("Closed definition node %(xlinkLabel)s does not contribute at least one structural node"),
                    modelObject=(view.defnMdlTable,defnMdlNode), xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode.localName)
            nestedDepth = depth + ordDepth
            cartesianProductNestedArgs = [view, nestedDepth, axis, facts, axisBrkdnRels, iBrkdn]
            if axis == "x":
                if ordDepth:
                    if nestedDepth > view.colHdrRows:
                        view.colHdrRows = nestedDepth - 1
                hdrNonStdRoles = view.colHdrNonStdRoles
            elif axis == "y":
                if ordDepth:
                    if nestedDepth > view.rowHdrCols:
                        view.rowHdrCols = nestedDepth
                        if not isinstance(defnMdlNode, DefnMdlRelationshipNode):
                            # not quite sure of this condition, but Solvency (rule node) need one less col than a relationship node (german taxonomy)
                            view.rowHdrCols -= 1
                        for j in range(1 + ordDepth):
                            view.rowHdrColWidth.append(RENDER_UNITS_PER_CHAR)  # min width for 'tail' of nonAbstract coordinate
                            view.rowNonAbstractHdrSpanMin.append(0)
                    elif isinstance(strctMdlNode, StrctMdlBreakdown):
                        view.rowHdrCols = view.rowHdrCols + nestedDepth
                        for j in range(1 + ordDepth):
                            view.rowHdrColWidth.append(RENDER_UNITS_PER_CHAR)  # min width for 'tail' of nonAbstract coordinate
                            view.rowNonAbstractHdrSpanMin.append(0)
                    checkLabelWidth(view, strctMdlNode, subtreeRels, checkBoundFact=False)
                hdrNonStdRoles = view.rowHdrNonStdRoles
                # print(f"id {defnMdlNode.id} depth {depth} y axis ordDepth {ordDepth} nestedDepth {nestedDepth} rowHdrCols {view.rowHdrCols}")
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
                childStrctNode = None
                hasUnreportedChildStrctNode = False
                for subtreeRel in subtreeRels:
                    childDefnMdlNode = subtreeRel.toModelObject

                    if childDefnMdlNode.isMerged:
                        '''
                        childSubtreeRels = view.defnSubtreeRelSet.fromModelObject(childDefnMdlNode)
                        for childSubtreeRel in childSubtreeRels:
                            mergedChildDefnMdlNode = childSubtreeRel.toModelObject
                            childStrctNode = resolveDefinition(view, strctMdlNode, mergedChildDefnMdlNode, depth+ordDepth, facts, iBrkdn, axisBrkdnRels, parentMerges=True)
                            for gStrctNode in strctMdlNode.strctMdlChildNodes:
                                for mergedAspect in childDefnMdlNode.aspectsCovered():
                                    aspect = childDefnMdlNode.aspectValue(view.rendrCntx, mergedAspect)
                                    if mergedAspect not in gStrctNode.aspects:
                                        if isinstance(aspect, list):
                                            aspect = set(aspect)
                                        gStrctNode.aspects[mergedAspect] = aspect
                                if childDefnMdlNode.tagSelector is not None and not gStrctNode.tagSelector:
                                    gStrctNode.tagSelector = childDefnMdlNode.tagSelector
                            # print(childStrctNode.aspectsCovered())
                        '''
                        childMergeAspects = mergeAspects.copy() if mergeAspects else {}
                        for mergedAspect in childDefnMdlNode.aspectsCovered():
                            aspect = childDefnMdlNode.aspectValue(view.rendrCntx, mergedAspect)
                            if isinstance(aspect, list):
                                aspect = set(aspect)
                            childMergeAspects[mergedAspect] = aspect
                        if childDefnMdlNode.tagSelector is not None:
                            childMergeAspects.setdefault("tagSelectors",set()).add(childDefnMdlNode.tagSelector)
                        childStrctNode = resolveDefinition(view, strctMdlNode, childDefnMdlNode, depth, facts, iBrkdn, axisBrkdnRels, mergeAspects=childMergeAspects)
                    elif defnMdlNode.isMerged and isinstance(childDefnMdlNode, (DefnMdlAspectNode,DefnMdlRelationshipNode)):
                        # parent is a merged node and child is an aspect node
                        childStrctNode = resolveDefinition(view, strctMdlNode, childDefnMdlNode, depth, facts, iBrkdn, axisBrkdnRels, mergeAspects=mergeAspects)
                    elif not isinstance(childDefnMdlNode, DefnMdlTable):
                        childStrctNode = resolveDefinition(view, strctMdlNode, childDefnMdlNode, depth+ordDepth, facts, iBrkdn, axisBrkdnRels)
                        for aspect in (mergeAspects or ()):
                            if aspect == "tagSelectors":
                                childStrctNode.tagSelectors |= mergeAspects["tagSelectors"]
                            elif aspect not in childStrctNode.aspectsCovered(inherit=False):
                                childStrctNode.aspects[aspect] = mergeAspects[aspect]
                        descendantDefMdlNodes = view.defnSubtreeRelSet.fromModelObject(childDefnMdlNode)
                        if not isinstance(childDefnMdlNode, DefnMdlAspectNode) and not childDefnMdlNode.isAbstract and descendantDefMdlNodes:
                            # contributes at least one child node
                            rollupAspectDefinitionNode = childDefnMdlNode
                            _rollup = ROLLUP_IMPLIES_DEFAULT_MEMBER
                            # definition node is that of the other child elements, to contribute a defaulted dimension
                            if childStrctNode.strctMdlChildNodes:
                                childStrctNodeAspectsCovered = childStrctNode.aspectsCovered()
                                if childStrctNodeAspectsCovered  & {Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS}:
                                    if childStrctNodeAspectsCovered == childStrctNode.strctMdlChildNodes[0].aspectsCovered():
                                        _rollup = ROLLUP_SPECIFIES_MEMBER
                                    else:
                                        rollupAspectDefinitionNode = childStrctNode.strctMdlChildNodes[0].defnMdlNode
                            rollUpStrctNode = StrctMdlStructuralNode(childStrctNode, rollupAspectDefinitionNode)
                            rollUpStrctNode.rollup = _rollup
                            childStrctNode.hasChildRollup = True
                            childStrctNode.rollUpChildStrctMdlNode = rollUpStrctNode
                            if isinstance(childDefnMdlNode, DefnMdlClosedDefinitionNode) and childDefnMdlNode.parentChildOrder == "parent-first":
                                childStrctNode.strctMdlChildNodes = childStrctNode.strctMdlChildNodes[-1:] + childStrctNode.strctMdlChildNodes[0:-1]
                            cartesianProductExpander(rollUpStrctNode, *cartesianProductNestedArgs)
                        if not childContainsOpenNodes(childStrctNode) and not childDefnMdlNode.childrenCoverSameAspects:
                            # To be computed only if the structural node does not contain an open node
                            cartesianProductExpander(childStrctNode, *cartesianProductNestedArgs)
                        if childStrctNode is not None and childStrctNode.isUnreported and isinstance(childDefnMdlNode, DefnMdlOpenDefinitionNode):
                            hasUnreportedChildStrctNode = True
                            strctMdlNode.strctMdlChildNodes.remove(childStrctNode)
                if hasUnreportedChildStrctNode and not strctMdlNode.strctMdlChildNodes and childStrctNode is not None:
                    # has all child nodes unreported, move group for header up to this level
                    strctMdlNode.strctMdlChildNodes.extend(childStrctNode.strctMdlChildNodes)
                # check if a children specify explicit dimensions and one is missing default
                descendantDefMdlNodes = view.defnSubtreeRelSet.fromModelObject(defnMdlNode)
                defnMdlChildDefDimsCovered = set( # defaulted dims in children
                    aspect
                    for rel in descendantDefMdlNodes
                    if not isinstance(rel.toModelObject, (NoneType,DefnMdlTable))
                    for aspect in rel.toModelObject.aspectsCovered()
                    if isinstance(aspect, QName) and aspect in view.modelXbrl.qnameDimensionDefaults
                )
                # note child defnMdlNodes needing default dimension
                for rel in descendantDefMdlNodes:
                    descDefnMdlNode = rel.toModelObject
                    if not isinstance(descDefnMdlNode, (NoneType,DefnMdlTable)):
                        defaultedDims = defnMdlChildDefDimsCovered - descDefnMdlNode.aspectsCovered() - defnMdlNode.aspectsCovered()
                        if defaultedDims:
                            descDefnMdlNode.deemedDefaultedDims = defaultedDims
                # check if child strct nodes specify explicit dimensions and one is missing default
                strctMdlChildDefDimsCovered = set( # defaulted dims in children
                    aspect
                    for gStrctNode in strctMdlParent.strctMdlChildNodes
                    for aspect in gStrctNode.aspectsCovered(inherit=True)
                    if isinstance(aspect, QName) and aspect in view.modelXbrl.qnameDimensionDefaults and gStrctNode.axis == axis
                )
                # note child defnMdlNodes needing default dimension
                anyUncoveredChilds = (defnMdlChildDefDimsCovered and
                                      any(defnMdlChildDefDimsCovered - gStrctNode.aspectsCovered(inherit=True)
                                          for gStrctNode in strctMdlParent.strctMdlChildNodes))
                for gStrctNode in strctMdlParent.strctMdlChildNodes:
                    if gStrctNode.axis == axis: # don't cross over breakdowns of other axis
                        defaultedDims = strctMdlChildDefDimsCovered - gStrctNode.aspectsCovered(inherit=True)
                        # remove any OMIT dimensions
                        if gStrctNode.hasAspect(Aspect.OMIT_DIMENSIONS):
                            defaultedDims |= set(gStrctNode.aspectValue(Aspect.OMIT_DIMENSIONS))
                        if defaultedDims:
                            gStrctNode.defnMdlNode.deemedDefaultedDims = defaultedDims
                        elif (anyUncoveredChilds and gStrctNode.defnMdlNode is not None
                              and (defnMdlChildDefDimsCovered - gStrctNode.aspectsCovered(inherit=True))):
                            gStrctNode.defnMdlNode.deemedDefaultedDims = defnMdlChildDefDimsCovered
            if isinstance(defnMdlNode, DefnMdlRelationshipNode):
                rels = defnMdlNode.relationships(strctMdlParent)
                if defnMdlNode.isOrSelfAxis:
                    rootOrSelfStructuralNodes = {}
                    addRelationships(defnMdlNode, defnMdlNode._sourceQnames, strctMdlParent, rootOrSelfStructuralNodes)
                else:
                    rootOrSelfStructuralNodes = None
                addRelationships(defnMdlNode, rels, strctMdlParent, rootOrSelfStructuralNodes)
                trimAbstractNodes(strctMdlParent)
                addDescendantRollups(strctMdlParent)
                # set up by defnMdlNode.relationships
                if isinstance(defnMdlNode, DefnMdlConceptRelationshipNode):
                    if (defnMdlNode._sourceQnames != [XbrlConst.qnXfiRoot] and
                        any(c is None or c.isHypercubeItem or c.isDimensionItem
                            for qn in defnMdlNode._sourceQnames
                            for c in (view.modelXbrl.qnameConcepts.get(qn),))):
                        view.modelXbrl.error("xbrlte:invalidConceptRelationshipSource",
                            _("Concept relationship rule node %(xlinkLabel)s source %(source)s does not refer to an existing concept."),
                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, source=", ".join(str(q) for q in defnMdlNode._sourceQnames))
                    else:
                        # check if single network
                        networks = set() # entry is linkrole, arcrole, linkQName, arcQName
                        for rel in flattenSequence(defnMdlNode.relationships(strctMdlNode)):
                            if isinstance(rel, ModelRelationship):
                                networks.add((rel.arcrole, rel.linkrole, rel.qname, rel.arcElement.qname))
                            else:
                                networks.add(None) # root element
                        if len(networks) > 1:
                            view.modelXbrl.error("xbrlte:ambiguousConceptNetwork",
                                _("Concept relationship rule node %(xlinkLabel)s has %(count)s networks: %(networks)s"),
                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, count=len(networks), networks=str(networks))
                elif isinstance(defnMdlNode, DefnMdlDimensionRelationshipNode):
                    dim = view.modelXbrl.qnameConcepts.get(defnMdlNode._dimensionQname)
                    if (dim is None or not dim.isExplicitDimension): #  and len(view.modelXbrl.factsInInstance) > 0:
                        view.modelXbrl.error("xbrlte:invalidExplicitDimensionQName",
                            _("Dimension relationship rule node %(xlinkLabel)s dimension %(dimension)s does not refer to an existing explicit dimension."),
                            modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, dimension=defnMdlNode._dimensionQname)
                    for _sourceQname in defnMdlNode._sourceQnames:
                        domMbr = view.modelXbrl.qnameConcepts.get(_sourceQname)
                        if domMbr is None or not domMbr.isDomainMember:
                            view.modelXbrl.error("xbrlte:invalidDimensionRelationshipSource",
                                _("Dimension relationship rule node %(xlinkLabel)s source %(source)s does not refer to an existing domain member."),
                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, source=_sourceQname)
                if (defnMdlNode._formulaAxis in ("child", "child-or-self", "parent", "parent-or-self", "sibling", "sibling-or-self") and
                    (not isinstance(defnMdlNode._generations, Number) or defnMdlNode._generations > 1)):
                    view.modelXbrl.error("xbrlte:relationshipNodeTooManyGenerations ",
                        _("Relationship rule node %(xlinkLabel)s formulaAxis %(axis)s implies a single generation tree walk but generations %(generations)s is greater than one."),
                        modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, axis=defnMdlNode._formulaAxis, generations=defnMdlNode._generations)
                for childStrctNode in strctMdlParent.strctMdlChildNodes:
                    for aspect in (mergeAspects or ()):
                        if aspect == "tagSelectors":
                            childStrctNode.tagSelectors |= mergeAspects["tagSelectors"]
                        elif not defnMdlNode.hasAspect(childStrctNode, aspect):
                            childStrctNode.aspects[aspect] = mergeAspects[aspect]

            elif isinstance(defnMdlNode, DefnMdlAspectNode):
                strctMdlNode.setHasOpenNode()
                strctMdlNode.isLabeled = False
                isCartesianProductExpanded = True

                # strctMdlNode.abstract = True # spanning ordinate acts as a subtitle
                aspectFactsPartitions = strctMdlNode.evaluate(defnMdlNode,
                                                                  defnMdlNode.filteredFactsPartitions,
                                                                  evalArgs=(view.modelXbrl.factsInInstance,)) # for all reported facts ignoring parent def node filters
                if depth < 2:
                    filteredFactsPartitions = aspectFactsPartitions
                else:
                    filteredFactsPartitions = strctMdlNode.evaluate(defnMdlNode,
                                                                  defnMdlNode.filteredFactsPartitions,
                                                                  evalArgs=(facts,))

                # apply mergedAspects

                if strctMdlNode._rendrCntx.formulaOptions.traceVariableFilterWinnowing:
                    view.modelXbrl.info("table:trace",
                        _("Filter node %(xlinkLabel)s facts partitions: %(factsPartitions)s"),
                        modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel,
                        factsPartitions=str(filteredFactsPartitions))
                # only for fact entry (true if no parent open nodes or all are on entry prototype row)
                childList = strctMdlNode.strctMdlChildNodes
                if strctMdlNode.isEntryPrototype(default=True):
                    for i in range(getattr(view, "openBreakdownLines",
                                           # for file output, 1 entry row if no facts
                                           0 if filteredFactsPartitions else 1)):
                        view.aspectEntryObjectId += 1
                        filteredFactsPartitions.append([FactPrototype(view, {"aspectEntryObjectId": OPEN_ASPECT_ENTRY_SURROGATE + str(view.aspectEntryObjectId)})])
                        if strctMdlNode.isEntryPrototype(default=False):
                            break # only one node per cartesian product under outermost nested open entry row
                if depth >= 2:
                    for i in range(len(filteredFactsPartitions)):
                        filteredFactsPartitions[i] = set(filteredFactsPartitions[i])
                for aspectPartition in aspectFactsPartitions:
                    childStrctMdlNode = StrctMdlStructuralNode(strctMdlNode, defnMdlNode, contextItemFact=aspectPartition[0])
                    aspectPartition = set(aspectPartition)

                    # find matching filterFactsPartition
                    if depth < 2:
                        factsPartition = aspectPartition
                    else:
                        factsPartition = set()
                        for fp in filteredFactsPartitions:
                            if fp <= aspectPartition:
                                factsPartition = fp
                                break

                    # store the partition for later reuse when spreading facts in body cells if no aspect filters involved
                    if not defnMdlNode.filterRelationships:
                        childStrctMdlNode.factsPartition = factsPartition

                    childStrctMdlNode.indent = 0
                    #TBD this is now computed, not an attribute
                    #childStrctMdlNode.depth -= 1  # for label width; parent is merged/invisible
                    checkLabelWidth(view, childStrctMdlNode, subtreeRels, checkBoundFact=True)
                    #resolveDefinition(view, childStrctMdlNode, breakdownNode, defnMdlNode, depth, axis, factsPartition, processOpenDefinitionNode=False) #recurse

                    for aspect in (mergeAspects or ()):
                        if aspect == "tagSelectors":
                            childStrctMdlNode.tagSelectors |= mergeAspects["tagSelectors"]
                        elif not defnMdlNode.hasAspect(childStrctMdlNode, aspect):
                            childStrctMdlNode.aspects[aspect] = mergeAspects[aspect]

                    if subtreeRels:
                        for subtreeRel in subtreeRels:
                            child2DefinitionNode = subtreeRel.toModelObject
                            #child2StructuralNode = StrctMdlStructuralNode(childStrctMdlNode, child2DefinitionNode) # others are nested structuralNode
                            #childStrctMdlNode.strctMdlChildNodes.append(child2StructuralNode)
                            #resolveDefinition(view, child2StructuralNode, child2DefinitionNode, depth+ordDepth, factsPartition, iBrkdn, axisBrkdnRels) #recurse
                            resolveDefinition(view, childStrctMdlNode, child2DefinitionNode, depth+ordDepth, factsPartition, iBrkdn, axisBrkdnRels) #recurse
                # sort by header (which is likely to be typed dim value, for example)
                childList.sort(key=lambda childStrctMdlNode:
                               childStrctMdlNode.header(lang=view.lang,
                                                          returnGenLabel=False,
                                                          returnMsgFormatString=False,
                                                          layoutMdlSortOrder=True)
                               or '') # exception on trying to sort if header returns None
                #test case 1200 v10i may require fact in instance order
                if defnMdlNode.aspectsCovered() == {Aspect.CONCEPT}:
                    childList.sort(key=lambda childStrctMdlNode:
                                   min(f.objectIndex for f in childStrctMdlNode.factsPartition) if getattr(childStrctMdlNode,"factsPartition",None) else 999999999)
                # TBD if there is no abstract 'sub header' for these subOrdCntxs, move them in place of parent structuralNode
            elif isinstance(defnMdlNode, DefnMdlRuleDefinitionNode):
                for constraintSet in defnMdlNode.constraintSets.values():
                    _aspectsCovered = constraintSet.aspectsCovered()
                    for aspect in _aspectsCovered:
                        if not constraintSet.aspectValueDependsOnVars(aspect):
                            if aspect == Aspect.CONCEPT:
                                conceptQname = constraintSet.aspectValue(view.rendrCntx, Aspect.CONCEPT)
                                concept = view.modelXbrl.qnameConcepts.get(conceptQname)
                                if concept is None or not concept.isItem or concept.isDimensionItem or concept.isHypercubeItem:
                                    view.modelXbrl.error("xbrlte:invalidQNameAspectValue",
                                        _("Rule node %(xlinkLabel)s specifies concept %(concept)s does not refer to an existing primary item concept."),
                                        modelObject=constraintSet, xlinkLabel=defnMdlNode.xlinkLabel, concept=conceptQname)
                            elif isinstance(aspect, QName):
                                dimConcept = view.modelXbrl.qnameConcepts.get(aspect)
                                dimVal = defnMdlNode.aspectValue(view.rendrCntx, aspect)
                                if dimConcept is not None:
                                    if dimConcept.isTypedDimension: # dimValue is the member node
                                        if isinstance(dimVal, ModelObject) and not view.modelXbrl.factsByDimMemQname(aspect, dimVal.textValue):
                                            strctMdlNode.isUnreported = True # typed Dim is unreported
                                    else: # dimValue is a QName
                                        mem = view.modelXbrl.qnameConcepts.get(dimVal)
                                        if isinstance(dimVal, QName) and (mem is None or not mem.isDomainMember) and dimVal != XbrlConst.qnFormulaDimensionSAV: # SAV is absent dimension member, reported in validateFormula:
                                            view.modelXbrl.error("xbrlte:invalidQNameAspectValue",
                                                _("Rule node %(xlinkLabel)s specifies domain member %(concept)s does not refer to an existing domain member concept."),
                                                modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel, concept=dimVal)
                #if not defnMdlNode.constraintSets:
                #    view.modelXbrl.error("xbrlte:incompleteAspectRule",
                #        _("Rule node %(xlinkLabel)s does not specify an aspect value."),
                #        modelObject=defnMdlNode, xlinkLabel=defnMdlNode.xlinkLabel)
            if not isCartesianProductExpanded:
                cartesianProductExpander(strctMdlNode, *cartesianProductNestedArgs)

            if isinstance(defnMdlNode, (NoneType, DefnMdlBreakdown)) and not strctMdlNode.strctMdlChildNodes: # childless root ordinate, make a child to iterate in producing table
                subOrdContext = StrctMdlBreakdown(strctMdlNode, defnMdlNode, axis)
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

    elif strctMdlNode and defnMdlNode is None: # no breakdown nodes for axis
        cartesianProductNestedArgs = [view, depth+1, axis, facts, (), iBrkdn]
        cartesianProductExpander(strctMdlNode, *cartesianProductNestedArgs)

    return strctMdlNode

def cartesianProductExpander(childStrctMdlNode, view, depth, axis, facts, axisBrkdnRels, iBrkdn):
    if iBrkdn is not None: # recurse table relationships for cartesian product
        for j, axisBrkdnRel in enumerate(axisBrkdnRels[iBrkdn+1:]):
            brkdnDefnMdlNode = axisBrkdnRel.toModelObject
            if isinstance(brkdnDefnMdlNode, DefnMdlBreakdown):
                subOrdTblCntx = childStrctMdlNode
                # predefined axes need facts sub-filtered
                if isinstance(childStrctMdlNode.defnMdlNode, DefnMdlClosedDefinitionNode):
                    matchingFacts = childStrctMdlNode.evaluate(childStrctMdlNode.defnMdlNode,
                                                        childStrctMdlNode.defnMdlNode.filteredFacts,
                                                        evalArgs=(facts,))
                else:
                    matchingFacts = facts
                # returns whether there were no structural node results
                subOrdTblCntx.abstract = True # can't be abstract across breakdown
                resolveDefinition(view, subOrdTblCntx, brkdnDefnMdlNode,
                            depth, # depth + (0 if axis == 'z' else 1),
                            matchingFacts, j + iBrkdn + 1, axisBrkdnRels,
                            axis=subOrdTblCntx.axis) #cartesian product
                break

def addRelationship(relDefinitionNode, rel, strctMdlNode, rootOrSelfStructuralNodes=None):
    variableQname = relDefinitionNode.variableQname
    conceptQname = relDefinitionNode.conceptQname
    coveredAspect = relDefinitionNode.coveredAspect(strctMdlNode)
    if not coveredAspect:
        return None
    if rootOrSelfStructuralNodes is not None:
        if isinstance(rel, QName):
            fromConceptQname = rel
            if fromConceptQname == XbrlConst.qnXfiRoot:
                return None
        else:
            fromConceptQname = rel.fromModelObject.qname
        # is there an ordinate for this root object?
        if fromConceptQname in rootOrSelfStructuralNodes:
            childStrctMdlNode = rootOrSelfStructuralNodes[fromConceptQname]
        else:
            childStrctMdlNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
            rootOrSelfStructuralNodes[fromConceptQname] = childStrctMdlNode
            if variableQname:
                childStrctMdlNode.variables[variableQname] = []
            if conceptQname:
                childStrctMdlNode.variables[conceptQname] = fromConceptQname
            childStrctMdlNode.aspects[coveredAspect] = fromConceptQname
            concept = relDefinitionNode.modelXbrl.qnameConcepts.get(fromConceptQname)
            if concept is not None and concept.isAbstract:
                childStrctMdlNode.abstract = True
        if isinstance(rel, QName):
            return childStrctMdlNode
        relChildStrctMdlNode = StrctMdlStructuralNode(childStrctMdlNode, relDefinitionNode)
    else:
        relChildStrctMdlNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
    if isinstance(rel, ModelRelationship):
        if isinstance(relDefinitionNode, DefnMdlConceptRelationshipNode):
            preferredLabel = rel.preferredLabel
            genPreferredLabel = rel.get("{http://xbrl.org/2013/preferred-label}preferredLabel")
            if preferredLabel is None:
                if genPreferredLabel is not None:
                    preferredLabel = genPreferredLabel
            elif genPreferredLabel is not None:
                rel.modelXbrl.error("xbrlte:ambiguousPreferredLabel",
                    _("PresentationArc has both the preferredLabel (%(preferredLabel)s) and gpl:preferredLabel (%(genPreferredLabel)s) attributes"),
                    modelObject=rel, preferredLabel=preferredLabel, genPreferredLabel=genPreferredLabel)
            if preferredLabel == XbrlConst.periodStartLabel:
                relChildStrctMdlNode.tagSelector = "table.periodStart"
            elif preferredLabel == XbrlConst.periodEndLabel:
                relChildStrctMdlNode.tagSelector = "table.periodEnd"
        elif isinstance(relDefinitionNode, DefnMdlDimensionRelationshipNode):
            relChildStrctMdlNode.abstract = not rel.isUsable
        toConceptQname = rel.toModelObject.qname
    else:
        toConceptQname = rel # QName
    if variableQname:
        relChildStrctMdlNode.variables[variableQname] = rel
    if conceptQname:
        relChildStrctMdlNode.variables[conceptQname] = toConceptQname
    relChildStrctMdlNode.aspects[coveredAspect] = toConceptQname
    concept = relDefinitionNode.modelXbrl.qnameConcepts.get(toConceptQname)
    if isinstance(relDefinitionNode, DefnMdlConceptRelationshipNode) and concept is not None and concept.isAbstract:
        relChildStrctMdlNode.abstract = True
    return relChildStrctMdlNode

def addRelationships(relDefinitionNode, rels, strctMdlNode, rootOrSelfStructuralNodes=None):
    childStrctMdlNode = None # holder for nested relationships
    for rel in rels:
        if not isinstance(rel, list):
            # first entry can be parent of nested list relationships
            childStrctMdlNode = addRelationship(relDefinitionNode, rel, strctMdlNode, rootOrSelfStructuralNodes)
        elif childStrctMdlNode is None:
            childStrctMdlNode = StrctMdlStructuralNode(strctMdlNode, relDefinitionNode)
            addRelationships(relDefinitionNode, rel, childStrctMdlNode)
        else:
            addRelationships(relDefinitionNode, rel, childStrctMdlNode)

def trimAbstractNodes(strctMdlParent):
    for childStrctMdlNode in strctMdlParent.strctMdlChildNodes:
        trimAbstractNodes(childStrctMdlNode)
    # remove childless abstract structural nodes by tail recursion
    abstractChildlessNodes = []
    for i, childStrctMdlNode in enumerate(strctMdlParent.strctMdlChildNodes):
        if childStrctMdlNode.isAbstract and not childStrctMdlNode.strctMdlChildNodes:
            abstractChildlessNodes.insert(0, i) # reversed list
    for i in abstractChildlessNodes:
        del strctMdlParent.strctMdlChildNodes[i]

def getDepth(strctMdlParent, depth=0):
    maxDepth = depth
    for childStrctMdlNode in strctMdlParent.strctMdlChildNodes:
        d = getDepth(childStrctMdlNode, depth+1)
        if d > maxDepth:
            maxDepth = d
    return maxDepth


def addDescendantRollups(strctMdlParent, maxDepth=None, depth=0):
    if maxDepth is None:
        maxDepth = getDepth(strctMdlParent)
    # add roll-up nodes after the children were populated from top level
    needsChildRollup = 0 < depth < maxDepth and (not strctMdlParent.isAbstract or strctMdlParent.rollup)
    for childStrctMdlNode in strctMdlParent.strctMdlChildNodes:
        addDescendantRollups(childStrctMdlNode, maxDepth, depth=depth+1)
    if needsChildRollup:
        rollUpStrctNode = StrctMdlStructuralNode(strctMdlParent, strctMdlParent.defnMdlNode)
        rollUpStrctNode.rollup = strctMdlParent.defnMdlNode.strctMdlRollupType
        strctMdlParent.hasChildRollup = True
        strctMdlParent.rollUpChildStrctMdlNode = rollUpStrctNode
        if len(strctMdlParent.strctMdlChildNodes) > 1 and strctMdlParent.parentChildOrder == "parent-first":
            strctMdlParent.strctMdlChildNodes = strctMdlParent.strctMdlChildNodes[-1:] + strctMdlParent.strctMdlChildNodes[0:-1]
        addDescendantRollups(rollUpStrctNode, maxDepth, depth=depth+1)

def addDefaultedDimensionsToLeafNodes(strctMdlNode, coveredDims=None, defaultedDims=None):
    if coveredDims is None:
        coveredDims = set()
        defaultedDims = set()
    coveredDims = coveredDims | strctMdlNode.aspectsCovered()
    if strctMdlNode.hasAspect(Aspect.OMIT_DIMENSIONS):
        coveredDims = coveredDims - set(strctMdlNode.aspectValue(Aspect.OMIT_DIMENSIONS))
    if hasattr(strctMdlNode.defnMdlNode, "deemedDefaultedDims"):
        defaultedDims = defaultedDims | getattr(strctMdlNode.defnMdlNode, "deemedDefaultedDims")
    if strctMdlNode.rollup == ROLLUP_IMPLIES_DEFAULT_MEMBER:
        deemedDefaultedDims = defaultedDims - coveredDims
        if deemedDefaultedDims:
            strctMdlNode.deemedDefaultedDims = deemedDefaultedDims
            defaultedDims -= deemedDefaultedDims
    if strctMdlNode.strctMdlChildNodes:
        for childStrctMdlNode in strctMdlNode.strctMdlChildNodes:
            addDefaultedDimensionsToLeafNodes(childStrctMdlNode, coveredDims, defaultedDims)
    else: # leaf node
        deemedDefaultedDims = defaultedDims - coveredDims
        if deemedDefaultedDims:
            strctMdlNode.deemedDefaultedDims = deemedDefaultedDims
