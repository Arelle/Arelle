'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import os
from datetime import timedelta
from collections import OrderedDict
from copy import deepcopy
from lxml import etree
from arelle import ViewFile
from arelle.FormulaEvaluator import aspectMatches
from arelle.FunctionXs import xsString
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.PythonUtil import OrderedSet
from arelle.ModelRenderingObject import (StrctMdlBreakdown, StrctMdlStructuralNode,
                                         DefnMdlClosedDefinitionNode, DefnMdlRuleDefinitionNode, DefnMdlAspectNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE, ROLLUP_SPECIFIES_MEMBER, ROLLUP_FOR_DIMENSION_RELATIONSHIP_NODE,
                                         aspectStrctNodes)
from arelle.RenderingResolution import resolveTableStructure, RENDER_UNITS_PER_CHAR
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT
from arelle.ViewFile import HTML, XML
# change tableModel for namespace needed for consistency suite
'''
from arelle.XbrlConst import (tableModelMMDD as tableModelNamespace,
                              tableModelMMDDQName as tableModelQName)
'''
from arelle import XbrlConst
from arelle.XmlUtil import innerTextList, child, elementFragmentIdentifier, addQnameValue
from collections import defaultdict

emptySet = set()
emptyList = []

headerOmittedRollupAspects  = {
    Aspect.CONCEPT,
    Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO, Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO,
    Aspect.VALUE, Aspect.SCHEME,
    Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT,
    Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY}


def viewRenderedGrid(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None, diffToFile=False, cssExtras=""):
    modelXbrl.modelManager.showStatus(_("saving rendering"))
    view = ViewRenderedGrid(modelXbrl, outfile, lang, cssExtras)

    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
    view.view(viewTblELR)
    if diffToFile and outfile:
        from arelle.ValidateInfoset import validateRenderingInfoset
        validateRenderingInfoset(modelXbrl, outfile, view.xmlDoc)
        view.close(noWrite=True)
    else:
        view.close()
    modelXbrl.modelManager.showStatus(_("rendering saved to {0}").format(outfile), clearAfter=5000)

class ViewRenderedGrid(ViewFile.View):
    def __init__(self, modelXbrl, outfile, lang, cssExtras):
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedGrid, self).__init__(modelXbrl, outfile,
                                               f'tableModel xmlns="{self.tableModelNamespace}" xmlns:xbrli="http://www.xbrl.org/2003/instance"',
                                               lang,
                                               style="rendering",
                                               cssExtras=cssExtras)
        class nonTkBooleanVar():
            def __init__(self, value=True):
                self.value = value
            def set(self, value):
                self.value = value
            def get(self):
                return self.value
        # context menu boolean vars (non-tkinter boolean
        self.ignoreDimValidity = nonTkBooleanVar(value=True)
        self.openBreakdownLines = 0 # layout model conformance suite requires no open entry lines


    def tableModelQName(self, localName):
        return '{' + self.tableModelNamespace + '}' + localName

    def viewReloadDueToMenuAction(self, *args):
        self.view()

    def view(self, viewTblELR=None):
        if viewTblELR is not None:
            tblELRs = (viewTblELR,)
        else:
            tblELRs = self.modelXbrl.relationshipSet("Table-rendering").linkRoleUris

        if self.type == XML:
            self.tblElt.append(etree.Comment("Entry point file: {0}".format(self.modelXbrl.modelDocument.basename)))

        for tblELR in tblELRs:
            self.zOrdinateChoices = {}

            strctMdlTable = resolveTableStructure(self, tblELR)
            zDiscrimAspectNodes = [{}]
            for discriminator in range(1, 65535):
                # each table z production
                defnMdlTable = strctMdlTable.defnMdlNode
                self.hasTableFilters = bool(self.defnMdlTable.filterRelationships)

                self.zStrNodesWithChoices = []
                xTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("x")
                yTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("y")
                zTopStrctNode = strctMdlTable.strctMdlFirstAxisBreakdown("z")
                if self.tblBrkdnRels and self.tblElt is not None:
                    tableLabel = (defnMdlTable.genLabel(lang=self.lang, strip=True) or  # use table label, if any
                                  self.roledefinition)
                    if self.type == HTML: # table on each Z
                        # each Z is a separate table in the outer table
                        zTableRow = etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
                        zRowCell = etree.SubElement(zTableRow, "{http://www.w3.org/1999/xhtml}td")
                        zCellTable = etree.SubElement(zRowCell, "{http://www.w3.org/1999/xhtml}table",
                                                      attrib={"border":"1", "cellspacing":"0", "cellpadding":"4", "style":"font-size:8pt;"})
                        self.rowElts = [etree.SubElement(zCellTable, "{http://www.w3.org/1999/xhtml}tr")
                                        for r in range(self.dataFirstRow + self.dataRows)]
                        etree.SubElement(self.rowElts[0], "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":"tableHdr",
                                                 "style":"max-width:100em;",
                                                 "colspan": str(self.dataFirstCol),
                                                 "rowspan": str(self.dataFirstRow)}
                                         ).text = tableLabel
                    elif self.type == XML:
                        self.StrctNodeModelElements = []
                        if discriminator == 1:
                            # headers structure only build once for table
                            tableSetElt = etree.SubElement(self.tblElt, self.tableModelQName("tableSet"))
                            tableSetElt.append(etree.Comment("TableSet linkbase file: {0}, line {1}".format(defnMdlTable.modelDocument.basename, defnMdlTable.sourceline)))
                            tableSetElt.append(etree.Comment("TableSet namespace: {0}".format(defnMdlTable.namespaceURI)))
                            tableSetElt.append(etree.Comment("TableSet linkrole: {0}".format(tblELR)))
                            etree.SubElement(tableSetElt, self.tableModelQName("label")
                                             ).text = tableLabel
                            zAspectStrctNodes = defaultdict(set)

                            tableElt = etree.SubElement(tableSetElt, self.tableModelQName("table"))
                            self.groupElts = {}
                            self.headerElts = {}
                            self.headerCells = defaultdict(list) # order #: (breakdownNode, xml element)
                            for axis in ("z", "y", "x", ):
                                def listBreakdown(strctMdl, breakdownNodes):
                                    if isinstance(strctMdl, StrctMdlBreakdown) and \
                                            all(strctMdl.defnMdlNode is not None and strctMdl.defnMdlNode.id != bdn.defnMdlNode.id for bdn in breakdownNodes):
                                        breakdownNodes.append(strctMdl)

                                    for node in strctMdl.strctMdlChildNodes:
                                        listBreakdown(node, breakdownNodes)

                                breakdownNodes = list()
                                breakdownNodesTop = [s for s in strctMdlTable.strctMdlChildNodes if s._axis == axis and s.defnMdlNode is not None]
                                for breakdownNode in breakdownNodesTop:
                                    listBreakdown(breakdownNode, breakdownNodes)
                                if breakdownNodes:
                                    hdrsElt = etree.SubElement(tableElt, self.tableModelQName("headers"),
                                                               attrib={"axis": axis})
                                    for brkdownNode in breakdownNodes:
                                        groupElt = etree.SubElement(hdrsElt, self.tableModelQName("group"))
                                        groupElt.append(etree.Comment("Breakdown node file: {0}, line {1}".format(brkdownNode.defnMdlNode.modelDocument.basename, brkdownNode.defnMdlNode.sourceline)))
                                        label = brkdownNode.defnMdlNode.genLabel(lang=self.lang, strip=True)
                                        if label:
                                            etree.SubElement(groupElt, self.tableModelQName("label")).text=label
                                        self.groupElts[brkdownNode] = groupElt
                                        # HF TODO omit header if zero cardinality on breakdown
                                        self.headerElts[brkdownNode] = etree.SubElement(groupElt, self.tableModelQName("header"))
                                else:
                                    tableElt.append(etree.Comment("No breakdown group for \"{0}\" axis".format(axis)))
                            zStrctNodes = []
                            self.layoutMdlAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                                       zTopStrctNode, zStrctNodes, True, True, self.colHdrNonStdRoles)
                            # lay out choices for each discriminator
                            zCounts = [1]
                            for _position, layoutMdlBrkdnCells in sorted(self.headerCells.items()):
                                if layoutMdlBrkdnCells:
                                    zCounts.append(sum((int(headerCell.get("span","1"))
                                                        for _brkdnNode, _strNode, headerCell in layoutMdlBrkdnCells)))
                            zDiscrimAspectNodes = [{} for i in range(max(zCounts))]
                            for _position, layoutMdlBrkdnCells in sorted(self.headerCells.items()):
                                if layoutMdlBrkdnCells:
                                    i = 0
                                    for _brkdnNode, strctNode, headerCell in layoutMdlBrkdnCells:
                                        for j in range(int(headerCell.get("span","1"))):
                                            if not headerCell.get("rollup"):
                                                zDiscrimAspectNodes[i] = aspectStrctNodes(strctNode)
                                            i += 1

                            zColumns = self.headerCells
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
                            #self.zAxis(1, strctMdlTable.strctMdlFirstAxisBreakdown("z"), zAspectStrctNodes, True)
                            self.cellsTableElt = tableElt
                            self.cellsZElt = etree.SubElement(self.cellsTableElt, self.tableModelQName("cells"),
                                                                   attrib={"axis": "z"})
                        self.cellsYElt = etree.SubElement(self.cellsZElt, self.tableModelQName("cells"),
                                                               attrib={"axis": "y"})
                    # rows/cols only on firstTime for infoset XML, but on each time for xhtml
                    #self.zAxis(1, zTopStrctNode, zAspectStrctNodes, False)
                    xStrctNodes = []
                    yStrctNodes = []
                    zStrctNodes = []
                    zAspectStrctNodes = defaultdict(list)

                    if zTopStrctNode.strctMdlChildNodes:  # same as combo box selection in GUI mode
                        self.zStrNodesWithChoices.insert(0, zTopStrctNode)  # iteration from last is first
                    if self.type == XML:
                        # try to set zStrctNodes
                        pass
                        '''
                        for aspect, i in zAspectChoiceIndx.items():
                            strctNode = zAspectStrctNodes[aspect][i]
                            if strctNode not in zStrctNodes:
                                zStrctNodes.append(strctNode)
                        '''
                    else:
                        self.zAxis(1, zTopStrctNode, zAspectStrctNodes, False)
                    if self.type == XML and (xTopStrctNode and xTopStrctNode.strctMdlChildNodes):
                        self.layoutMdlAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                                   xTopStrctNode, xStrctNodes, True, True, self.colHdrNonStdRoles)
                    elif self.type == HTML and (xTopStrctNode and xTopStrctNode.strctMdlChildNodes):
                        self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                                   xTopStrctNode, xStrctNodes, True, True)
                    if self.type == HTML: # table/tr goes by row
                        self.yAxis(0, self.dataFirstRow, yTopStrctNode, yStrctNodes, True, True)
                    elif self.type == XML and discriminator == 1: # infoset goes by col of row header
                        if yTopStrctNode and yTopStrctNode.strctMdlChildNodes: # no row header element if no rows
                            self.layoutMdlAxis(self.dataFirstRow, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                                       yTopStrctNode, yStrctNodes, True, True, self.rowHdrNonStdRoles)
                        # add header cells to header elements cycling through nested repeats
                        headerByPos = {}
                        for _position, breakdownCellElts in sorted(self.headerCells.items(), reverse=True):
                            if breakdownCellElts:
                                for breakdownNode, _strctNode, headerCell in breakdownCellElts:
                                    if breakdownNode in self.headerElts:
                                        if _position != 0: # TODO this need reworks
                                            if _position not in headerByPos or breakdownNode not in headerByPos[_position]:
                                                headerElt = etree.Element(self.tableModelQName("header"))
                                                if _position not in headerByPos:
                                                    headerByPos[_position] = {breakdownNode: headerElt}
                                                else:
                                                    headerByPos[_position][breakdownNode] = headerElt
                                                self.headerElts[breakdownNode].addnext(headerElt)
                                            else:
                                                headerElt = headerByPos[_position][breakdownNode]
                                            headerElt.append(headerCell)
                                        else:
                                            self.headerElts[breakdownNode].append(headerCell)
                            self.headerCells[_position] = []

                        for StrctNode,modelElt in self.StrctNodeModelElements: # must do after elements are all arragned
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
                        for headerElt in self.headerElts.values(): # remove empty header elements
                            if not any(e is not None for e in headerElt.iterchildren()):
                                if headerElt.getparent() is not None:
                                    headerElt.getparent().remove(headerElt)
                    # if no x axis nodes put a dummy one in
                    if len(xStrctNodes) == 0:
                        xStrctNodes.append(StrctMdlStructuralNode(strctMdlTable, None))
                    hasRows = self.bodyCells(self.dataFirstRow, yStrctNodes, xStrctNodes, zDiscrimAspectNodes[discriminator-1]) # zAspectStrctNodes)
                    if self.type == XML and not hasRows:
                        self.cellsZElt.remove(self.cellsYElt)

                # find next choice structural node
                '''
                moreDiscriminators = False
                if self.type == XML:
                    for aspect in reversed(zAspectChoiceIndx.keys()):
                        zAspectChoiceIndx[aspect] += 1
                        if zAspectChoiceIndx[aspect] < zAspectChoiceLens[aspect]:
                            moreDiscriminators = True
                            break
                        else:
                            zAspectChoiceIndx[aspect] = 0
                else:
                    for zStrNodeWithChoices in self.zStrNodesWithChoices:
                        currentIndex = zStrNodeWithChoices.choiceNodeIndex + 1
                        if currentIndex < len(zStrNodeWithChoices.strctMdlChildNodes):
                            zStrNodeWithChoices.choiceNodeIndex = currentIndex
                            self.zOrdinateChoices[zStrNodeWithChoices.defnMdlNode] = currentIndex
                            moreDiscriminators = True
                            break
                        else:
                            zStrNodeWithChoices.choiceNodeIndex = 0
                            self.zOrdinateChoices[zStrNodeWithChoices.defnMdlNode] = 0
                            # continue incrementing next outermore z choices index
                if not moreDiscriminators:
                    break
                '''
                if discriminator >= len(zDiscrimAspectNodes):
                    break


    def layoutMdlAxis(self, leftCol, topRow, rowBelow, parentStrctNode, strctNodes, renderNow, atTop, HdrNonStdRoles):
        # axis handling for xml export
        if parentStrctNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            colsToSpanParent = 0
            widthToSpanParent = 0
            rowsForThisBreakdown = 1 + parentStrctNode.hasRollUpChild
            for i, strctNode in enumerate(parentStrctNode.strctMdlChildNodes): # strctMdlEffectiveChildNodes:
                noDescendants = False
                if isinstance(strctNode, StrctMdlBreakdown) and not strctNode.isLabeled:
                    rowsForThisStrctNode = 0
                else:
                    rowsForThisStrctNode = rowsForThisBreakdown
                rightCol, row, cols, width, leafNode = self.layoutMdlAxis(leftCol, topRow + rowsForThisStrctNode, rowBelow, strctNode, strctNodes, # nested items before totals
                                                                  True, False, HdrNonStdRoles)
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
                    label, source = strctNode.headerAndSource(lang=self.lang,
                                    returnGenLabel=isinstance(strctNode.defnMdlNode, DefnMdlClosedDefinitionNode),
                                    returnStdLabel=not isinstance(strctNode.defnMdlNode, DefnMdlAspectNode))
                    if cols:
                        columnspan = cols
                    else:
                        columnspan = rightCol - leftCol
                    brkdownNode = strctNode.strctMdlAncestorBreakdownNode
                    attrib = {}
                    if columnspan > 1:
                        attrib["span"] = str(columnspan)
                    if isRollUpCell:
                        attrib["rollup"] = "true"
                    cellElt = etree.Element(self.tableModelQName("cell"), attrib)

                    self.headerCells[topRow].append((brkdownNode, strctNode, cellElt))
                    if isRollUpCell == ROLLUP_SPECIFIES_MEMBER:
                        continue # leave rollup's dimension out of structural model
                    elt = None
                    if not isRollUpCell:
                        cellElt.append(etree.Comment("Cell id {0}".format(strctNode.defnMdlNode.id, )))
                        if label:
                            elt = etree.SubElement(cellElt, self.tableModelQName("label"))
                        for i, role in enumerate(HdrNonStdRoles):
                            roleLabel, source = strctNode.headerAndSource(role=role, lang=self.lang, recurseParent=False) # infoset does not move parent label to decscndant
                            if roleLabel is not None:
                                cellElt.append(etree.Comment("Label role: {0}, lang {1}"
                                                             .format(os.path.basename(role), self.lang)))
                                labelElt = etree.SubElement(cellElt, self.tableModelQName("label"))
                                labelElt.text = roleLabel

                    orderKeys = {}
                    for tag in strctNode.constraintTags():  # TODO try to order tags
                        if tag is None:
                            orderKeys[tag] = 2
                        elif "start" in tag:
                            orderKeys[tag] = 1
                        elif "end" in tag:
                            orderKeys[tag] = 3
                        else:
                            orderKeys[tag] = 0

                    for tag in sorted(strctNode.constraintTags(), key=lambda s: orderKeys[s]):
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
                                if tag:
                                    attrib = {"tag": tag}

                                constraintElt = etree.SubElement(cellElt, self.tableModelQName("constraint"), attrib)
                                aspElt = etree.SubElement(constraintElt, self.tableModelQName("aspect"))
                                valueElt = etree.SubElement(constraintElt, self.tableModelQName("value"))

                                if aspect in aspectRuleAspects[Aspect.PERIOD]:
                                    aspectProcessed.update(aspectRuleAspects[Aspect.PERIOD])

                                    periodType = getAspectValue(Aspect.PERIOD_TYPE)
                                    if periodType == "duration":
                                        start = getAspectValue(Aspect.START)
                                        end = getAspectValue(Aspect.END)

                                        aspectValue = etree.Element("{http://www.xbrl.org/2003/instance}startDate")
                                        aspectValue.text = f"{start.strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                        valueElt.append(aspectValue)

                                        aspectValueEnd = etree.Element("{http://www.xbrl.org/2003/instance}endDate")
                                        aspectValueEnd.text = f"{(end + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                        valueElt.append(aspectValueEnd)
                                    elif periodType == "instant":
                                        instant = getAspectValue(Aspect.INSTANT)
                                        aspectValue = etree.Element("{http://www.xbrl.org/2003/instance}instant")
                                        aspectValue.text = f"{(instant + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%f')}Z"
                                        valueElt.append(aspectValue)
                                    else:  # "forever":
                                        aspectValue = etree.Element("{http://www.xbrl.org/2003/instance}forever")
                                        valueElt.append(aspectValue)
                                    aspect = Aspect.PERIOD
                                elif aspect in aspectRuleAspects[Aspect.ENTITY_IDENTIFIER]:
                                    aspectProcessed.add(Aspect.SCHEME)
                                    aspectProcessed.add(Aspect.VALUE)

                                    scheme = getAspectValue(Aspect.SCHEME)
                                    value = getAspectValue(Aspect.VALUE)

                                    aspectValue = etree.Element("{http://www.xbrl.org/2003/instance}identifier", {"scheme": scheme})
                                    aspectValue.text = str(value)
                                    aspect = Aspect.ENTITY_IDENTIFIER
                                    valueElt.append(aspectValue)
                                elif aspect in aspectRuleAspects[Aspect.UNIT]:
                                    aspectProcessed.update(aspectRuleAspects[Aspect.UNIT])

                                    unit = getAspectValue(aspect)

                                    aspectValue = etree.Element("{http://www.xbrl.org/2003/instance}unit")
                                    measure = etree.SubElement(aspectValue, "{http://www.xbrl.org/2003/instance}measure")
                                    measure.text = str(unit[0])
                                    valueElt.append(aspectValue)
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
                                                aspectValue = self.modelXbrl.qnameConcepts[aspectValue].qname # usually has a prefix
                                            except KeyError:
                                                pass
                                        return aspectValue

                                    if isinstance(aspectValue, list):
                                        # TODO for now take the fist will see later how to handle correctly
                                        aspectValue = aspectValue[0]
                                    else:
                                        aspectValue = format_aspect_value(aspectValue)
                                    if (not isRollUpCell and
                                            self.modelXbrl.qnameDimensionDefaults.get(aspect) != aspectValue and
                                            aspectValue != XbrlConst.qnFormulaOccEmpty):
                                        if aspect == Aspect.PERIOD and isinstance(aspectValue, ModelObject):
                                            for perElt in aspectValue.iterchildren():
                                                valueElt.append(deepcopy(perElt))
                                        elif isinstance(aspect, QName) and aspectValue == "(bound dynamically)": # absent dimension
                                            valueElt.text = ""
                                        elif not isinstance(aspectValue, etree._Element):
                                            valueElt.text = xsString(None, None, addQnameValue(self.xmlDoc, aspectValue if not label or label != OPEN_ASPECT_ENTRY_SURROGATE else "\u00A0"))
                                        else:
                                            valueElt.append(deepcopy(aspectValue))
                                aspElt.text = aspectStr(aspect)
                    for aspect in getattr(strctNode.defnMdlNode, "deemedDefaultedDims", ()):
                        # deemed defaulted explicit dimensions when present in sibling str mdl nodes
                        aspElt = etree.SubElement(cellElt, self.tableModelQName("constraint"))
                        etree.SubElement(aspElt, self.tableModelQName("aspect")
                                         ).text = aspectStr(aspect)
                        valueElt = etree.SubElement(aspElt, self.tableModelQName("value"))

                    if elt is not None:
                        elt.text = label if bool(label) and label != OPEN_ASPECT_ENTRY_SURROGATE else "\u00A0" #produces &nbsp;
                        if source:
                            elt.set("source", source)
                    if nonAbstract and not strctNode.hasChildRollup:
                        strctNodes.append(strctNode)
                if nonAbstract:
                    rightCol += 1
            return (rightCol, parentRow, colsToSpanParent, widthToSpanParent, noDescendants)

    def zAxis(self, row, zStrctNode, zAspectStrctNodes, discriminatorsTable):
        if zStrctNode is not None and zStrctNode.defnMdlNode is not None:
            zDefnMdlNode = zStrctNode.defnMdlNode
            label, source = zStrctNode.headerAndSource(lang=self.lang)
            choiceLabel = None
            effectiveStrctNode = zStrctNode
            isRollUpParent = zDefnMdlNode.childrenCoverSameAspects
            span = 1
            if zStrctNode.strctMdlChildNodes: # same as combo box selection in GUI mode
                if not discriminatorsTable:
                    self.zStrNodesWithChoices.insert(0, zStrctNode) # iteration from last is first
                try:
                    effectiveStrctNode = zStrctNode.strctMdlChildNodes[zStrctNode.choiceNodeIndex]
                    choiceLabel = effectiveStrctNode.header(lang=self.lang)
                    if not label and choiceLabel:
                        label = choiceLabel # no header for choice
                        choiceLabel = None
                except KeyError:
                    pass
            if choiceLabel:
                if self.dataCols > 3:
                    zLabelSpan = 2
                else:
                    zLabelSpan = 1
                zChoiceLabelSpan = self.dataCols - zLabelSpan
            else:
                zLabelSpan = self.dataCols
                
            etree.SubElement(self.rowElts[row-1], "{http://www.w3.org/1999/xhtml}th",
                             attrib={"class":"zAxisHdr",
                                     "style":"max-width:200pt;text-align:left;border-bottom:.5pt solid windowtext",
                                     "colspan": str(zLabelSpan)} # "2"}
                             ).text = label
            if choiceLabel:
                etree.SubElement(self.rowElts[row-1], "{http://www.w3.org/1999/xhtml}th",
                                 attrib={"class":"zAxisHdr",
                                         "style":"max-width:200pt;text-align:left;border-bottom:.5pt solid windowtext",
                                         "colspan": str(zChoiceLabelSpan)} # "2"}
                                 ).text = choiceLabel

            for aspect in aspectModels["dimensional"]:
                if effectiveStrctNode.hasAspect(aspect, inherit=True): #implies inheriting from other z axes
                    if aspect == Aspect.DIMENSIONS:
                        for dim in (effectiveStrctNode.aspectValue(Aspect.DIMENSIONS, inherit=True) or emptyList):
                            zAspectStrctNodes[dim].add(effectiveStrctNode)
                    else:
                        zAspectStrctNodes[aspect].add(effectiveStrctNode)
            for i in range(span):
                for zChildStrctNode in zStrctNode.strctMdlChildNodes:
                    self.zAxis(row + 1, zChildStrctNode, zAspectStrctNodes, discriminatorsTable)

    def xAxis(self, leftCol, topRow, rowBelow, xParentStrctNode, xStrctNodes, renderNow, atTop):
        if xParentStrctNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            colsToSpanParent = 0
            widthToSpanParent = 0
            sideBorder = not xStrctNodes
            rowsForThisBreakdown = 1 + xParentStrctNode.hasRollUpChild
            for xStrctNode in xParentStrctNode.strctMdlChildNodes: # strctMdlEffectiveChildNodes:
                xDefnMdlNode = xStrctNode.defnMdlNode
                noDescendants = False
                if isinstance(xStrctNode, StrctMdlBreakdown) and not xStrctNode.isLabeled:
                    rowsForThisStrctNode = 0
                else:
                    rowsForThisStrctNode = rowsForThisBreakdown
                rightCol, row, cols, width, leafNode = self.xAxis(leftCol, topRow + rowsForThisStrctNode, rowBelow, xStrctNode, xStrctNodes, # nested items before totals
                                                                  True, False)
                if row - 1 < parentRow:
                    parentRow = row - 1
                #if not leafNode:
                #    rightCol -= 1
                nonAbstract = not xStrctNode.isAbstract
                if nonAbstract:
                    width += 100 # width for this label
                widthToSpanParent += width
                if cols:
                    colsToSpanParent += cols
                else:
                    colsToSpanParent += rightCol + 1 - leftCol
                thisCol = leftCol
                isRollUpParent = xDefnMdlNode.childrenCoverSameAspects
                 #print ( "thisCol {0} leftCol {1} rightCol {2} topRow{3} renderNow {4} label {5}".format(thisCol, leftCol, rightCol, topRow, renderNow, label))
                if renderNow:
                    label, source = xStrctNode.headerAndSource(lang=self.lang,
                                    returnGenLabel=isinstance(xStrctNode.defnMdlNode, DefnMdlClosedDefinitionNode))
                    if cols:
                        columnspan = cols
                    else:
                        columnspan = rightCol - leftCol
                    # if columnspan > 0 and nonAbstract: columnspan += 1
                    elt = None
                    if xStrctNode.isLabeled or not isinstance(xStrctNode, StrctMdlBreakdown):
                        if rightCol == self.dataFirstCol + self.dataCols - 1:
                            edgeBorder = "border-right:.5pt solid windowtext;"
                        else:
                            edgeBorder = ""
                        attrib = {"class":"xAxisHdr",
                                  "style":"text-align:center;max-width:{0}pt;{1}".format(width,edgeBorder)}
                        if columnspan > 1:
                            attrib["colspan"] = str(columnspan)
                        if leafNode and row > topRow:
                            rowspan = row - topRow + 1
                            if rowspan > 1:
                                attrib["rowspan"] = str(rowspan)
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib=attrib)
                        if isRollUpParent:
                            rollUpCellElt = elt
                        self.rowElts[topRow-1+rowsForThisBreakdown-isRollUpParent].insert(leftCol,elt)
                    if elt is not None:
                        elt.text = label if bool(label) and label != OPEN_ASPECT_ENTRY_SURROGATE else "\u00A0" #produces &nbsp;
                        if source:
                            elt.set("source", source)
                    if nonAbstract or isRollUpParent:
                        if xStrctNode.isLabeled or not isinstance(xStrctNode, StrctMdlBreakdown):
                            if isRollUpParent:   # add spanned left leg portion one row down
                                attrib= {"class":"xAxisSpanLeg",
                                         "rowspan": str(rowBelow - row)}
                                if columnspan > 1:
                                    attrib["colspan"] = str(columnspan)
                                if edgeBorder:
                                    attrib["style"] = edgeBorder
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib=attrib)
                                elt.text = "\u00A0"
                                self.rowElts[topRow].append(elt)
                            for i, role in enumerate(self.colHdrNonStdRoles):
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib={"class":"xAxisHdr",
                                                            "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                                self.rowElts[self.dataFirstRow - len(self.colHdrNonStdRoles) + i].insert(thisCol,elt)
                                elt.text = xStrctNode.header(role=role, lang=self.lang) or "\u00A0"
                        '''
                        if self.colHdrDocRow:
                            doc = xStrctNode.header(role="http://www.xbrl.org/2008/role/documentation", lang=self.lang)
                            if self.type == HTML:
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib={"class":"xAxisHdr",
                                                            "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                                self.rowElts[self.dataFirstRow - 2 - self.rowHdrCodeCol].insert(thisCol,elt)
                            elif self.type == XML:
                                elt = etree.Element(self.tableModelQName("label"))
                                self.colHdrElts[self.colHdrRows - 1].insert(thisCol,elt)
                            elt.text = doc or "\u00A0"
                        if self.colHdrCodeRow:
                            code = xStrctNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                            if self.type == HTML:
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib={"class":"xAxisHdr",
                                                            "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                                self.rowElts[self.dataFirstRow - 2].insert(thisCol,elt)
                            elif self.type == XML:
                                elt = etree.Element(self.tableModelQName("label"))
                                self.colHdrElts[self.colHdrRows - 1 + self.colHdrDocRow].insert(thisCol,elt)
                            elt.text = code or "\u00A0"
                        '''
                    if nonAbstract:
                        xStrctNodes.append(xStrctNode)
                if nonAbstract:
                    rightCol += 1
            if xParentStrctNode.hasRollUpChild:
                # insert roll up span header
                label = xParentStrctNode.header(lang=self.lang,
                                               returnGenLabel=isinstance(xStrctNode.defnMdlNode, DefnMdlClosedDefinitionNode))
                columnspan = colsToSpanParent
                if columnspan > 1:
                    rollUpCellElt.set("colspan", str(columnspan))
            return (rightCol, parentRow, colsToSpanParent, widthToSpanParent, noDescendants)

    def yAxis(self, leftCol, row, yParentStrctNode, yStrctNodes, renderNow, atLeft):
        noDescendants = True
        nestedBottomRow = row
        rowspan = 1
        columnspan = 1
        nestedBottomRow = row
        for yOrdinal, yStrctNode in enumerate(yParentStrctNode.strctMdlChildNodes): # strctMdlEffectiveChildNodes:
            yDefnMdlNode = yStrctNode.defnMdlNode
            childrenFirst = yDefnMdlNode.parentChildOrder == "children-first"
            noDescendants = False
            isAbstract = (yStrctNode.isAbstract or
                          (yStrctNode.strctMdlChildNodes and
                           not isinstance(yDefnMdlNode, DefnMdlClosedDefinitionNode)))
            isNonAbstract = not isAbstract
            isLabeled = yStrctNode.isLabeled
            nestRow, nextRow = self.yAxis(leftCol + isLabeled, row, yStrctNode, yStrctNodes,  # nested items before totals
                                               childrenFirst, False)

            topRow = row
            #if childrenFirst and isNonAbstract:
            #    row = nextRow
            if renderNow and isLabeled:
                label = yStrctNode.header(lang=self.lang,
                                               returnGenLabel=isinstance(yStrctNode.defnMdlNode, DefnMdlClosedDefinitionNode),
                                               recurseParent=not isinstance(yStrctNode.defnMdlNode, DefnMdlRuleDefinitionNode))
                columnspan = self.rowHdrCols - len(self.rowHdrNonStdRoles) - leftCol + 1 if isNonAbstract or nextRow == row else 1
                if childrenFirst and isNonAbstract and nextRow > row:
                    elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                        attrib={"class":"yAxisSpanArm",
                                                "style":"text-align:center;min-width:2em;",
                                                "rowspan": str(nextRow - topRow)}
                                        )
                    insertPosition = self.rowElts[nextRow].__len__()
                    self.rowElts[row].insert(insertPosition, elt)
                    elt.text = "\u00A0"
                    hdrRow = nextRow # put nested stuff on bottom row
                    row = nextRow    # nested header still goes on this row
                else:
                    hdrRow = row
                # provide top or bottom borders
                edgeBorder = ""

                if childrenFirst:
                    if hdrRow == self.dataFirstRow:
                        edgeBorder = "border-top:.5pt solid windowtext;"
                else:
                    if hdrRow == len(self.rowElts):
                        edgeBorder = "border-bottom:.5pt solid windowtext;"
                depth = yStrctNode.depth
                attrib = {"style":"text-align:{0};max-width:{1}em;{2}".format(
                                        self.langAlign if isNonAbstract or nestRow == hdrRow else "center",
                                        # this is a wrap length max width in characters
                                        self.rowHdrColWidth[depth] if isAbstract else
                                        self.rowHdrWrapLength - sum(self.rowHdrColWidth[0:depth]),
                                        edgeBorder),
                          "colspan": str(columnspan)}
                if label == OPEN_ASPECT_ENTRY_SURROGATE: # entry of dimension
                    attrib["style"] += ";background:#fff" # override for white background
                if isAbstract:
                    attrib["rowspan"] = str(nestRow - hdrRow)
                    attrib["class"] = "yAxisHdrAbstractChildrenFirst" if childrenFirst else "yAxisHdrAbstract"
                elif nestRow > hdrRow:
                    attrib["class"] = "yAxisHdrWithLeg"
                elif childrenFirst:
                    attrib["class"] = "yAxisHdrWithChildrenFirst"
                else:
                    attrib["class"] = "yAxisHdr"
                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                    attrib=attrib
                                    )
                elt.text = label if bool(label) and label != OPEN_ASPECT_ENTRY_SURROGATE else "\u00A0"
                if isNonAbstract:
                    self.rowElts[hdrRow].append(elt)
                    if not childrenFirst and nestRow > hdrRow:   # add spanned left leg portion one row down
                        etree.SubElement(self.rowElts[hdrRow],
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":"yAxisSpanLeg",
                                                 "style":"text-align:center;max-width:{0}pt;{1}".format(RENDER_UNITS_PER_CHAR, edgeBorder),
                                                 "rowspan": str(nestRow - hdrRow)}
                                         ).text = "\u00A0"
                    hdrClass = "yAxisHdr" if not childrenFirst else "yAxisHdrWithChildrenFirst"
                    for i, role in enumerate(self.rowHdrNonStdRoles):
                        hdr = yStrctNode.header(role=role, lang=self.lang)
                        etree.SubElement(self.rowElts[hdrRow],
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                         ).text = hdr or "\u00A0"
                    '''
                    if self.rowHdrDocCol:
                        docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                        doc = yStrctNode.header(role="http://www.xbrl.org/2008/role/documentation")
                        etree.SubElement(self.rowElts[hdrRow],
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                         ).text = doc or "\u00A0"
                    if self.rowHdrCodeCol:
                        codeCol = self.dataFirstCol - 1
                        code = yStrctNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        etree.SubElement(self.rowElts[hdrRow],
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:center;max-width:40pt;{0}".format(edgeBorder)}
                                         ).text = code or "\u00A0"
                    # gridBorder(self.gridRowHdr, leftCol, self.dataFirstRow - 1, BOTTOMBORDER)
                    '''
                else:
                    self.rowElts[hdrRow].insert(leftCol, elt)
                if isNonAbstract:
                    yStrctNodes.append(yStrctNode)
            else: # no nodes
                childrenFirst = False
            if isNonAbstract:
                row += 1
            elif childrenFirst:
                row = nextRow
            if nestRow > nestedBottomRow:
                nestedBottomRow = nestRow + (isNonAbstract and not childrenFirst)
            if row > nestedBottomRow:
                nestedBottomRow = row
            if not childrenFirst:
                dummy, row = self.yAxis(leftCol + isLabeled, row, yStrctNode, yStrctNodes, renderNow, False) # render on this pass
        return (nestedBottomRow, row)


    def bodyCells(self, row, yStrctNodes, xStrctNodes, zAspectStrctNodes):
        hasRows = False
        if True: # yParentStrctNode is not None:
            dimDefaults = self.modelXbrl.qnameDimensionDefaults
            for yStrctNode in yStrctNodes: # yParentStrctNode.strctMdlChildNodes: # strctMdlEffectiveChildNodes:
                #row = self.bodyCells(row, yStrctNode, xStrctNodes, zAspectStrctNodes)
                if not (yStrctNode.isAbstract or
                        (yStrctNode.strctMdlChildNodes and
                         not isinstance(yStrctNode.defnMdlNode, DefnMdlClosedDefinitionNode))) and yStrctNode.isLabeled:
                    hasColCells = False
                    if self.type == XML:
                        cellsParentElt = etree.SubElement(self.cellsYElt, self.tableModelQName("cells"),
                                                       attrib={"axis": "x"})
                    isEntryPrototype = yStrctNode.isEntryPrototype(default=False) # row to enter open aspects
                    yAspectStrctNodes = aspectStrctNodes(yStrctNode)
                    yTagSelectors = yStrctNode.tagSelectors
                    # data for columns of rows
                    ignoreDimValidity = self.ignoreDimValidity.get()
                    for i, xStrctNode in enumerate(xStrctNodes):
                        xAspectStrctNodes = aspectStrctNodes(xStrctNode)
                        cellTagSelectors = yTagSelectors | xStrctNode.tagSelectors
                        cellAspectValues = {}
                        matchableAspects = set()
                        for aspect in _DICT_SET(xAspectStrctNodes.keys()) | _DICT_SET(yAspectStrctNodes.keys()) | _DICT_SET(zAspectStrctNodes.keys()):
                            aspectValue = yStrctNode.inheritedAspectValue(xStrctNode,
                                               self, aspect, cellTagSelectors,
                                               xAspectStrctNodes, yAspectStrctNodes, zAspectStrctNodes)
                            # value is None for a dimension whose value is to be not reported in this slice
                            if ((isinstance(aspect, _INT) and aspectValue is not None) or  # not a dimension
                                dimDefaults.get(aspect) != aspectValue or # explicit dim defaulted will equal the value
                                aspectValue is not None): # typed dim absent will be none
                                cellAspectValues[aspect] = aspectValue
                            matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                        cellDefaultedDims = _DICT_SET(dimDefaults) - _DICT_SET(cellAspectValues.keys())
                        priItemQname = cellAspectValues.get(Aspect.CONCEPT)
                        if priItemQname == OPEN_ASPECT_ENTRY_SURROGATE:
                            priItemQname = None # open concept aspect

                        concept = self.modelXbrl.qnameConcepts.get(priItemQname)
                        conceptNotAbstract = concept is None or not concept.isAbstract
                        from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                        fact = None
                        factsVals = [] # matched / filtered [(fact, value, justify), ...]
                        value = None # last of the facts matched
                        justify = "left"
                        fp = FactPrototype(self, cellAspectValues)
                        if conceptNotAbstract:
                            # Reuse already computed facts partition in case of open Y axis
                            if hasattr(yStrctNode, "factsPartition"):
                                facts = set(yStrctNode.factsPartition)
                            else:
                                # reduce set of matchable facts to those with pri item qname and have dimension aspects
                                facts = self.modelXbrl.factsByQname[priItemQname] if priItemQname else self.modelXbrl.factsInInstance
                                if self.hasTableFilters:
                                    facts = self.defnMdlTable.filteredFacts(self.rendrCntx, facts)
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
                                    facts = facts & self.modelXbrl.factsByDimMemQname(aspect, dimMemQname)
                            for fact in sorted(facts, key=lambda f:f.objectIndex):
                                if (all(aspectMatches(self.rendrCntx, fact, fp, aspect)
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
                            hasColCells = True
                        if justify is None:
                            justify = "right" if fp.isNumeric else "left"
                        if conceptNotAbstract:
                            if self.type == XML and factsVals:
                                cellsParentElt.append(etree.Comment("Cell concept {0}: segDims {1}, scenDims {2}"
                                                                    .format(str(fp.qname).replace(OPEN_ASPECT_ENTRY_SURROGATE, '\u00a0'),
                                                                         ', '.join("({}={})".format(dimVal.dimensionQname, dimVal.memberQname)
                                                                                   for dimVal in sorted(fp.context.segDimVals.values(), key=lambda d: d.dimensionQname)),
                                                                         ', '.join("({}={})".format(dimVal.dimensionQname, dimVal.memberQname)
                                                                                   for dimVal in sorted(fp.context.scenDimVals.values(), key=lambda d: d.dimensionQname)),
                                                                         )))
                            if factsVals or ignoreDimValidity or isFactDimensionallyValid(self, fp) or isEntryPrototype:
                                if self.type == HTML and not isinstance(xStrctNode, StrctMdlBreakdown):
                                    elt = etree.SubElement(self.rowElts[row],
                                                           "{http://www.w3.org/1999/xhtml}td",
                                                           attrib={"class":"cell",
                                                                   "style":"text-align:{0};width:8em".format(justify)}
                                                           )
                                    if len(factsVals) == 0:
                                        elt.text = "\u00A0"
                                    elif len(factsVals) == 1:
                                        elt.text = factsVals[0][1] or "\u00A0"
                                    else:
                                        for i, (_f, v, _j) in enumerate(factsVals):
                                            if i > 0:
                                                elt = etree.SubElement(elt, "{http://www.w3.org/1999/xhtml}br")
                                            elt.text = v or "\u00A0"
                                elif self.type == XML:
                                    if not factsVals and fact is not None:
                                        cellsParentElt.append(etree.Comment("Fact was not matched {0}: context {1}, value {2}, file {3}, line {4}, aspects not matched: {5}, dimensions expected to have been defaulted: {6}"
                                                                            .format(fact.qname,
                                                                                 fact.contextID,
                                                                                 fact.effectiveValue[:32],
                                                                                 fact.modelDocument.basename,
                                                                                 fact.sourceline,
                                                                                 ', '.join(str(aspect)
                                                                                           for aspect in matchableAspects
                                                                                           if not aspectMatches(self.rendrCntx, fact, fp, aspect)),
                                                                                 ', '.join(str(dim)
                                                                                           for dim in cellDefaultedDims
                                                                                           if fact.context.dimMemberQname(dim,includeDefaults=True) not in (dimDefaults[dim], None))
                                                                                 )))
                                    cellElt = etree.SubElement(cellsParentElt, self.tableModelQName("cell"))
                                    for f, v, _j in factsVals:
                                        cellElt.append(etree.Comment("{0}: context {1}, value {2}, file {3}, line {4}"
                                                                            .format(f.qname,
                                                                                 f.contextID,
                                                                                 v[:32], # no more than 32 characters
                                                                                 f.modelDocument.basename,
                                                                                 f.sourceline)))
                                        if v is not None:
                                            etree.SubElement(cellElt, self.tableModelQName("fact")
                                                             ).text = '{}#{}'.format(f.modelDocument.basename,
                                                                                         elementFragmentIdentifier(f))
                            else:
                                if self.type == HTML:
                                    etree.SubElement(self.rowElts[row],
                                                     "{http://www.w3.org/1999/xhtml}td",
                                                     attrib={"class":"blockedCell",
                                                             "style":"text-align:{0};width:8em".format(justify)}
                                                     ).text = "\u00A0\u00A0"
                                elif self.type == XML:
                                    etree.SubElement(cellsParentElt, self.tableModelQName("cell"),
                                                     attrib={"blocked":"true"})
                        else: # concept is abstract
                            if self.type == HTML:
                                etree.SubElement(self.rowElts[row],
                                                 "{http://www.w3.org/1999/xhtml}td",
                                                 attrib={"class":"abstractCell",
                                                         "style":"text-align:{0};width:8em".format(justify)}
                                                 ).text = "\u00A0\u00A0"
                            elif self.type == XML:
                                etree.SubElement(cellsParentElt, self.tableModelQName("cell"),
                                                 attrib={"abstract":"true"})
                        fp.clear()  # dereference
                    row += 1
                    if self.type == XML:
                        if hasColCells:
                            hasRows = True
                        else:
                            cellsParentElt.getparent().remove(cellsParentElt) # remove empty element

        return hasRows