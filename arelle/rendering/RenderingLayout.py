'''
See COPYRIGHT.md for copyright information.
'''
import os
from collections import OrderedDict
from lxml import etree
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.Aspect import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.PythonUtil import OrderedSet
from arelle.ModelRenderingObject import (StrctMdlBreakdown, StrctMdlStructuralNode,
                                         DefnMdlClosedDefinitionNode, DefnMdlRuleDefinitionNode, DefnMdlAspectNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         aspectStrctNodes,
                                         LytMdlTableModel, LytMdlTableSet, LytMdlTable, LytMdlHeaders, LytMdlGroup,
                                         LytMdlHeader, LytMdlCell, LytMdlConstraint, LytMdlBodyCells, LytMdlBodyCell)
from arelle.rendering.RenderingResolution import resolveTableStructure
from arelle.formula.FormulaEvaluator import aspectMatches
from arelle.PythonUtil import flattenSequence
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT
from arelle import XbrlConst
from arelle.XbrlConst import tableModel as tableModelNamespace
from arelle.XmlUtil import innerTextList, child, elementFragmentIdentifier, addQnameValue
from collections import defaultdict
from numbers import Number

emptySet = set()
emptyList = []

headerOmittedRollupAspects  = {
    Aspect.CONCEPT,
    Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO, Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO,
    Aspect.VALUE, Aspect.SCHEME,
    Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT,
    Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY}

def layoutTable(view):
    view.modelXbrl.modelManager.showStatus(_("layout model generation"))
    viewTblELR = getattr(view, "tblELR", None)

    if viewTblELR is not None:
        tblELRs = (viewTblELR,)
    else:
        tblELRs = sorted(view.modelXbrl.relationshipSet("Table-rendering").linkRoleUris)

    view.lytMdlTblMdl = LytMdlTableModel(view.modelXbrl.modelDocument.basename)

    for tblELR in tblELRs:
        strctMdlTableSet = resolveTableStructure(view, tblELR)
        # each table z production
        defnMdlTable = strctMdlTableSet.defnMdlNode
        view.hasTableFilters = bool(view.defnMdlTable.filterRelationships)

        if view.tblBrkdnRels:
            tableSetLabel = (defnMdlTable.genLabel(lang=view.lang, strip=True) or  # use table label, if any
                          view.roledefinition)
            # headers structure only build once for table
            lytMdlTblSet = LytMdlTableSet(view.lytMdlTblMdl, strctMdlTableSet, tableSetLabel, defnMdlTable.modelDocument.basename, defnMdlTable.sourceline, tblELR)

            for strctMdlTable in strctMdlTableSet.strctMdlChildNodes:
                xTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("x")
                yTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("y")
                zTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("z")
                xHasBreakdownWithoutNodes = xTopStrctNode.hasBreakdownWithoutNodes
                yHasBreakdownWithoutNodes = yTopStrctNode.hasBreakdownWithoutNodes

                # set table parameters to sequence value for this table
                lytMdlTbl = LytMdlTable(lytMdlTblSet, strctMdlTable)
                for name, seqVal in strctMdlTable.tblParamValues.items():
                    view.rendrCntx.inScopeVars[name] = [seqVal]

                zDiscrimAspectNodes = [{}]
                for discriminator in range(1, 65535):
                    view.StrctNodeModelElements = []
                    if discriminator == 1:
                        zAspectStrctNodes = defaultdict(set)

                        brkdownNodeLytMdlGrp = {}
                        view.headerCells = defaultdict(list) # order #: (breakdownNode, xml element)
                        for axis in ("z", "y", "x", ):
                            def listBreakdown(strctMdl, breakdownNodes):
                                if isinstance(strctMdl, StrctMdlBreakdown) and \
                                        all(strctMdl.defnMdlNode is not None and strctMdl.defnMdlNode.id != bdn.defnMdlNode.id for bdn in breakdownNodes):
                                    breakdownNodes.append(strctMdl)

                                for node in strctMdl.strctMdlChildNodes:
                                    listBreakdown(node, breakdownNodes)

                            breakdownNodes = []
                            breakdownNodesTop = [s for s in strctMdlTable.strctMdlChildNodes if s._axis == axis and s.defnMdlNode is not None]
                            for breakdownNode in breakdownNodesTop:
                                listBreakdown(breakdownNode, breakdownNodes)
                            if breakdownNodes:
                                lytMdlHdrs = LytMdlHeaders(lytMdlTbl, axis)
                                for brkdownNode in breakdownNodes:
                                    label = brkdownNode.defnMdlNode.genLabel(lang=view.lang, strip=True)
                                    lytMdlGrp = LytMdlGroup(lytMdlHdrs, label, brkdownNode.defnMdlNode.modelDocument.basename, brkdownNode.defnMdlNode.sourceline)
                                    brkdownNodeLytMdlGrp[brkdownNode] = lytMdlGrp
                        zStrctNodes = []
                        layoutAxis(view, view.dataFirstCol, view.colHdrTopRow, view.colHdrTopRow + view.colHdrRows - 1,
                                   zTopStrctNode, zStrctNodes, True, True, view.colHdrNonStdRoles, False)
                        # lay out choices for each discriminator
                        zCounts = []
                        for _position, layoutMdlBrkdnCells in sorted(view.headerCells.items()):
                            if layoutMdlBrkdnCells:
                                zCounts.append(sum((int(headerCell.span)
                                                    for _brkdnNode, _strNode, headerCell in layoutMdlBrkdnCells)))
                        if not zCounts:
                            zCounts = [1] # allow single z iteration
                        zDiscrimAspectNodes = [{} for i in range(max(zCounts))]
                        for _position, layoutMdlBrkdnCells in sorted(view.headerCells.items()):
                            if layoutMdlBrkdnCells:
                                i = 0
                                for _brkdnNode, strctNode, headerCell in layoutMdlBrkdnCells:
                                    for j in range(int(headerCell.span)):
                                        if not headerCell.rollup:
                                            zDiscrimAspectNodes[i] = aspectStrctNodes(strctNode)
                                        i += 1

                        zColumns = view.headerCells
                        zAspects = OrderedSet()
                        zAspectStrctNodeChoices = defaultdict(list)
                        for effectiveStrctNode in zStrctNodes:
                            for aspect in aspectModels["dimensional"]:
                                if effectiveStrctNode.hasAspect(aspect, inherit=True): #implies inheriting from other z axes
                                    if aspect == Aspect.DIMENSIONS:
                                        for dim in (effectiveStrctNode.aspectValue(Aspect.DIMENSIONS, inherit=True) or emptyList):
                                            zAspects.add(dim)
                                            zAspectStrctNodeChoices[dim].append(effectiveStrctNode)
                                    else:
                                        zAspects.add(aspect)
                                        zAspectStrctNodeChoices[aspect].append(effectiveStrctNode)
                        zAspectChoiceLens = dict((aspect, len(zAspectStrctNodeChoices[aspect]))
                                                 for aspect in zAspects)
                        zAspectChoiceIndx = OrderedDict((aspect,0) for aspect in zAspects)
                        #view.zAxis(1, strctMdlTable.strctMdlFirstAxisBreakdown("z"), zAspectStrctNodes, True)
                        view.cellsTableElt = lytMdlTbl
                        lytMdlZCells = LytMdlBodyCells(view.cellsTableElt, "z")
                        # rows/cols only on firstTime for infoset XML, but on each time for xhtml
                        #view.zAxis(1, zTopStrctNode, zAspectStrctNodes, False)
                        xStrctNodes = []
                        yStrctNodes = []
                        zStrctNodes = []
                        zAspectStrctNodes = defaultdict(list)

                        if xTopStrctNode and xTopStrctNode.strctMdlChildNodes:
                            layoutAxis(view, view.dataFirstCol, view.colHdrTopRow, view.colHdrTopRow + view.colHdrRows - 1,
                                       xTopStrctNode, xStrctNodes, True, True, view.colHdrNonStdRoles, xHasBreakdownWithoutNodes)
                        if yTopStrctNode and yTopStrctNode.strctMdlChildNodes: # no row header element if no rows
                            layoutAxis(view, view.dataFirstRow, view.colHdrTopRow, view.colHdrTopRow + view.colHdrRows - 1,
                                       yTopStrctNode, yStrctNodes, True, True, view.rowHdrNonStdRoles, yHasBreakdownWithoutNodes)
                        # add header cells to header elements cycling through nested repeats
                        headerByPos = {}
                        for _position, breakdownCellElts in sorted(view.headerCells.items()): # , reverse=True):
                            if breakdownCellElts:
                                for breakdownNode, _strctNode, lytMdlCell in breakdownCellElts:
                                    if breakdownNode in brkdownNodeLytMdlGrp:
                                        lytMdlGrp = brkdownNodeLytMdlGrp[breakdownNode]
                                        if True: #_position != 0: # TODO this need reworks
                                            if _position not in headerByPos or breakdownNode not in headerByPos[_position]:
                                                lytMdlHdr = LytMdlHeader(lytMdlGrp)
                                                if _position not in headerByPos:
                                                    headerByPos[_position] = {breakdownNode: lytMdlHdr}
                                                else:
                                                    headerByPos[_position][breakdownNode] = lytMdlHdr
                                            else:
                                                lytMdlHdr = headerByPos[_position][breakdownNode]
                                            lytMdlHdr.lytMdlCells.append(lytMdlCell)
                                        #else:
                                        #    brkdownNodeLytMdlGrp[breakdownNode].lytMdlHeaders[-1].lytMdlCells.append(lytMdlCell)
                            view.headerCells[_position] = []

                        for StrctNode,modelElt in view.StrctNodeModelElements: # must do after elements are all arragned
                            modelElt.addprevious(etree.Comment("{0}: label {1}, file {2}, line {3}"
                                                          .format(StrctNode.defnMdlNode.localName,
                                                                  StrctNode.defnMdlNode.xlinkLabel,
                                                                  StrctNode.defnMdlNode.modelDocument.basename,
                                                                  StrctNode.defnMdlNode.sourceline)))
                            if StrctNode.defnMdlNode.get('value'):
                                modelElt.addprevious(etree.Comment("   @value {0}".format(StrctNode.defnMdlNode.get('value'))))
                            for aspect in sorted(StrctNode.aspectsCovered(), key=lambda a: aspectStr(a)):
                                if StrctNode.hasAspect(aspect) and aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS):
                                    aspectValue = StrctNode.aspectValue(aspect)
                                    if aspectValue is None: aspectValue = "(bound dynamically)"
                                    modelElt.addprevious(etree.Comment("   aspect {0}: {1}".format(aspectStr(aspect), xsString(None,None,aspectValue))))
                            for varName, varValue in StrctNode.variables.items():
                                    modelElt.addprevious(etree.Comment("   variable ${0}: {1}".format(varName, varValue)))
                        for lytMdlGrp in brkdownNodeLytMdlGrp.values(): # remove empty header elements
                            if not lytMdlGrp.lytMdlHeaders and not lytMdlGrp.label:
                                if lytMdlGrp.lytMdlParentHeaders is not None:
                                    lytMdlGrp.lytMdlParentHeaders.lytMdlGroups.remove(lytMdlGrp)
                    # if no x axis nodes put a dummy one in
                    if len(xStrctNodes) == 0:
                        xStrctNodes.append(StrctMdlStructuralNode(strctMdlTable, None))
                    lytMdlYCells = LytMdlBodyCells(lytMdlZCells, "y")
                    hasRows = bodyCells(view, view.dataFirstRow, yStrctNodes, xStrctNodes, zDiscrimAspectNodes[discriminator-1], lytMdlYCells) # zAspectStrctNodes)
                    if not hasRows or xHasBreakdownWithoutNodes or yHasBreakdownWithoutNodes:
                        lytMdlZCells.lytMdlBodyChildren.remove(lytMdlYCells)
                    if discriminator >= len(zDiscrimAspectNodes):
                        break

def layoutAxis(view, leftCol, topRow, rowBelow, parentStrctNode, strctNodes, renderNow, atTop, HdrNonStdRoles, noBreakdownNodes):
    # axis handling for xml export
    if parentStrctNode is not None:
        parentRow = rowBelow
        noDescendants = True
        rightCol = leftCol
        colsToSpanParent = 0
        widthToSpanParent = 0
        rowsForThisBreakdown = 1 + parentStrctNode.hasRollUpChild
        for strctNode in parentStrctNode.strctMdlChildNodes: # strctMdlEffectiveChildNodes:
            noDescendants = False
            if isinstance(strctNode, StrctMdlBreakdown) and not strctNode.isLabeled:
                rowsForThisStrctNode = 0
            else:
                rowsForThisStrctNode = rowsForThisBreakdown
            rightCol, row, cols, width, leafNode = layoutAxis(view, leftCol, topRow + rowsForThisStrctNode, rowBelow, strctNode, strctNodes, # nested items before totals
                                                              True, False, HdrNonStdRoles, noBreakdownNodes)
            if row - 1 < parentRow:
                parentRow = row - 1
            nonAbstract = not strctNode.isAbstract
            if nonAbstract:
                width += 100 # width for this label
            widthToSpanParent += width
            if cols:
                colsToSpanParent += cols
            else:
                colsToSpanParent += rightCol + 1 - leftCol
            isRollUpCell = strctNode.rollup
            if renderNow and not isinstance(strctNode, StrctMdlBreakdown):
                label, source = strctNode.headerAndSource(lang=view.lang,
                                returnGenLabel=isinstance(strctNode.defnMdlNode, DefnMdlClosedDefinitionNode),
                                returnStdLabel=not isinstance(strctNode.defnMdlNode, DefnMdlAspectNode))
                if cols:
                    columnspan = cols
                else:
                    columnspan = rightCol - leftCol
                brkdownNode = strctNode.strctMdlAncestorBreakdownNode
                lytMdlCell = LytMdlCell()
                if columnspan > 1:
                    lytMdlCell.span = columnspan
                if isRollUpCell:
                    lytMdlCell.rollup = True

                if not noBreakdownNodes:
                    view.headerCells[topRow].append((brkdownNode, strctNode, lytMdlCell))
                if isRollUpCell == ROLLUP_SPECIFIES_MEMBER:
                    continue # leave rollup's dimension out of structural model
                elt = None
                if not isRollUpCell:
                    lytMdlCell.id = strctNode.defnMdlNode.id
                    if label:
                        lytMdlCell.labels.append((label, None, None))
                        if label == OPEN_ASPECT_ENTRY_SURROGATE:
                            lytMdlCell.isOpenAspectEntrySurrogate = True
                    for role in HdrNonStdRoles:
                        roleLabel, source = strctNode.headerAndSource(role=role, lang=view.lang, recurseParent=False) # infoset does not move parent label to decscndant
                        if roleLabel is not None:
                            lytMdlCell.labels.append((roleLabel, os.path.basename(role), view.lang))

                orderKeys = {}

                for i, tag in enumerate(strctNode.constraintTags()):  # TODO try to order tags
                    if tag is None:
                        orderKeys[tag] = 2
                    elif "start" in tag.lower():
                        orderKeys[tag] = 1
                    elif "end" in tag.lower():
                        orderKeys[tag] = 3
                    else:
                        orderKeys[tag] = 0

                if noBreakdownNodes:
                    constraintTags = ()
                else:
                    constraintTags = strctNode.constraintTags()
                for tag in sorted(constraintTags, key=lambda s: orderKeys[s]):
                    aspectProcessed = set()
                    constraint = strctNode.constraintSet([tag])

                    def hasAspect(aspect):
                        if tag:
                            return constraint.hasAspect(strctNode, aspect)
                        return strctNode.hasAspect(aspect)
                    def getAspectValue(aspect):
                        if tag:
                            return constraint.aspectValue(strctNode._rendrCntx, aspect)
                        return strctNode.aspectValue(aspect)

                    def aspectsCovered():
                        ac = strctNode.aspectsCovered(inherit=False)
                        if tag:
                            ac |= constraint.aspectsCovered()
                        return ac

                    for aspect in sorted(aspectsCovered(), key=lambda a: aspectStr(a)):
                        if hasAspect(aspect) and aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS):
                            if aspect in aspectProcessed:
                                continue
                            if aspect == Aspect.AUGMENT: # TODO seems to be skipped for xml output
                                continue
                            if isRollUpCell == ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE:
                                continue
                            if isRollUpCell and aspect in headerOmittedRollupAspects:
                                continue
                            attrib = None

                            lytMdlCnstrt = LytMdlConstraint(lytMdlCell, tag)

                            if aspect in aspectRuleAspects[Aspect.PERIOD]:
                                aspectProcessed.update(aspectRuleAspects[Aspect.PERIOD])

                                periodType = getAspectValue(Aspect.PERIOD_TYPE)
                                if periodType == "duration":
                                    lytMdlCnstrt.value = {"periodType": "duration",
                                                          "startDate": getAspectValue(Aspect.START),
                                                          "endDate":   getAspectValue(Aspect.END)}
                                elif periodType == "instant":
                                    lytMdlCnstrt.value = {"periodType": "instant",
                                                          "instant":   getAspectValue(Aspect.INSTANT)}
                                else:  # "forever":
                                    lytMdlCnstrt.value = {"periodType": "forever"}
                                aspect = Aspect.PERIOD
                            elif aspect in aspectRuleAspects[Aspect.ENTITY_IDENTIFIER]:
                                aspectProcessed.add(Aspect.SCHEME)
                                aspectProcessed.add(Aspect.VALUE)
                                lytMdlCnstrt.value = {"scheme":     getAspectValue(Aspect.SCHEME),
                                                      "identifier": getAspectValue(Aspect.VALUE)}
                                aspect = Aspect.ENTITY_IDENTIFIER
                            elif aspect in aspectRuleAspects[Aspect.UNIT]:
                                aspectProcessed.update(aspectRuleAspects[Aspect.UNIT])
                                lytMdlCnstrt.value = {"measures": [str(u) for u in getAspectValue(aspect)]}
                                aspect = Aspect.UNIT
                            else:
                                aspectValue = getAspectValue(aspect)
                                def format_aspect_value(aspectValue):
                                    if aspectValue is None:
                                        aspectValue = "(bound dynamically)"
                                    elif isinstance(aspectValue, ModelDimensionValue): # typed dimension value
                                        if aspectValue.isExplicit:
                                            aspectValue = aspectValue.memberQname
                                        else:
                                            aspectValue = aspectValue.typedMember
                                    elif isinstance(aspectValue, QName) and aspectValue.prefix is None: # may be dynamic
                                        try:
                                            aspectValue = view.modelXbrl.qnameConcepts[aspectValue].qname # usually has a prefix
                                        except KeyError:
                                            pass
                                    return aspectValue

                                if isinstance(aspectValue, list):
                                    # TODO for now take the fist will see later how to handle correctly
                                    aspectValue = aspectValue[0] if aspectValue else None
                                else:
                                    aspectValue = format_aspect_value(aspectValue)
                                if (not isRollUpCell and
                                        view.modelXbrl.qnameDimensionDefaults.get(aspect) != aspectValue and
                                        aspectValue != XbrlConst.qnFormulaOccEmpty):
                                    lytMdlCnstrt.value = aspectValue
                            lytMdlCnstrt.aspect = aspect
                for aspect in getattr(strctNode, "deemedDefaultedDims", ()):
                    # deemed defaulted explicit dimensions when present in sibling str mdl nodes
                    lytMdlCnstrt = LytMdlConstraint(lytMdlCell, None)
                    lytMdlCnstrt.aspect = aspect
                    lytMdlCnstrt.value = ""

                if nonAbstract and not strctNode.hasChildRollup:
                    strctNodes.append(strctNode)
            if nonAbstract:
                rightCol += 1
        return (rightCol, parentRow, colsToSpanParent, widthToSpanParent, noDescendants)

def bodyCells(view, row, yStrctNodes, xStrctNodes, zAspectStrctNodes, lytMdlYCells):
    hasRows = False
    if True: # yParentStrctNode is not None:
        dimDefaults = view.modelXbrl.qnameDimensionDefaults
        for yStrctNode in yStrctNodes: # yParentStrctNode.strctMdlChildNodes: # strctMdlEffectiveChildNodes:
            #row = view.bodyCells(row, yStrctNode, xStrctNodes, zAspectStrctNodes)
            if not (yStrctNode.isAbstract or
                    (yStrctNode.strctMdlChildNodes and
                     not isinstance(yStrctNode.defnMdlNode, DefnMdlClosedDefinitionNode))) and yStrctNode.isLabeled:
                hasColCells = False
                lytMdlXCells = LytMdlBodyCells(lytMdlYCells, "x")
                isEntryPrototype = yStrctNode.isEntryPrototype(default=False) # row to enter open aspects
                yAspectStrctNodes = aspectStrctNodes(yStrctNode)
                yTagSelectors = yStrctNode.tagSelectors
                # data for columns of rows
                ignoreDimValidity = view.ignoreDimValidity.get()
                for i, xStrctNode in enumerate(xStrctNodes):
                    xAspectStrctNodes = aspectStrctNodes(xStrctNode)
                    cellTagSelectors = yTagSelectors | xStrctNode.tagSelectors
                    if {"table.periodStart","table.periodEnd"} & cellTagSelectors:
                        cellTagSelectors &= {"table.periodStart","table.periodEnd"}
                    cellAspectValues = {}
                    matchableAspects = set()
                    isOpenAspectEntrySurrogate = False
                    for aspect in xAspectStrctNodes.keys() | yAspectStrctNodes.keys() | zAspectStrctNodes.keys():
                        aspectValue = yStrctNode.inheritedAspectValue(xStrctNode,
                                           view, aspect, cellTagSelectors,
                                           xAspectStrctNodes, yAspectStrctNodes, zAspectStrctNodes)
                        # value is None for a dimension whose value is to be not reported in this slice
                        if ((isinstance(aspect, Number) and aspectValue is not None) or  # not a dimension
                            dimDefaults.get(aspect) != aspectValue or # explicit dim defaulted will equal the value
                            aspectValue is not None): # typed dim absent will be none
                            cellAspectValues[aspect] = aspectValue
                            if isinstance(aspectValue,str) and aspectValue.startswith(OPEN_ASPECT_ENTRY_SURROGATE):
                                isOpenAspectEntrySurrogate = True
                        matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                    cellDefaultedDims = dimDefaults - cellAspectValues.keys()
                    priItemQname = cellAspectValues.get(Aspect.CONCEPT)
                    if priItemQname == OPEN_ASPECT_ENTRY_SURROGATE:
                        priItemQname = None # open concept aspect

                    concept = view.modelXbrl.qnameConcepts.get(priItemQname)
                    conceptNotAbstract = concept is None or not concept.isAbstract
                    from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                    fact = None
                    factsVals = [] # matched / filtered [(fact, value, justify), ...]
                    value = None # last of the facts matched
                    justify = "left"
                    fp = FactPrototype(view, cellAspectValues)
                    if conceptNotAbstract:
                        # Reuse already computed facts partition in case of open Y axis
                        if hasattr(yStrctNode, "factsPartition"):
                            facts = set(yStrctNode.factsPartition)
                        else:
                            # reduce set of matchable facts to those with pri item qname and have dimension aspects
                            facts = view.modelXbrl.factsByQname[priItemQname] if priItemQname else view.modelXbrl.factsInInstance
                            if view.hasTableFilters:
                                facts = view.defnMdlTable.filteredFacts(view.rendrCntx, facts)
                        for aspect in matchableAspects:  # trim down facts with explicit dimensions match or just present
                            if isinstance(aspect, QName):
                                aspectValue = cellAspectValues.get(aspect, None)
                                if isinstance(aspectValue, ModelDimensionValue):
                                    if aspectValue.isExplicit:
                                        dimMemQname = aspectValue.memberQname # match facts with this explicit value
                                    else:
                                        dimMemQname = None  # match facts that report this dimension
                                elif isinstance(aspectValue, QName):
                                    dimMemQname = aspectValue  # match facts that have this explicit value
                                elif aspectValue is None: # match typed dims that don't report this value
                                    dimMemQname = DEFAULT
                                else:
                                    dimMemQname = None # match facts that report this dimension
                                facts = facts & view.modelXbrl.factsByDimMemQname(aspect, dimMemQname)
                        for fact in sorted(facts, key=lambda f:f.objectIndex):
                            if (all(aspectMatches(view.rendrCntx, fact, fp, aspect)
                                    for aspect in matchableAspects) and
                                all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                    for dim in cellDefaultedDims) and
                                    len(fp.context.qnameDims) == len(fact.context.qnameDims)):
                                if yStrctNode.hasValueExpression(xStrctNode):
                                    value = yStrctNode.evalValueExpression(fact, xStrctNode)
                                else:
                                    value = fact.effectiveValue
                                justify = "right" if fact.isNumeric else "left"
                                factsVals.append( (fact, value, justify) )
                        hasColCells = bool(matchableAspects) # True
                    if justify is None:
                        justify = "right" if fp.isNumeric else "left"
                    if conceptNotAbstract:
                        if factsVals or ignoreDimValidity or isFactDimensionallyValid(self, fp) or isEntryPrototype:
                            lytMdlCell = LytMdlBodyCell(lytMdlXCells, isOpenAspectEntrySurrogate)
                            lytMdlCell.facts = factsVals
                    fp.clear()  # dereference
                row += 1
                if hasColCells:
                    hasRows = True
                else:
                    lytMdlYCells.lytMdlBodyChildren.remove(lytMdlXCells)
    return hasRows
