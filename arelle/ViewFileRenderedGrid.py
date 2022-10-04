'''
See COPYRIGHT.md for copyright information.
'''
import os
from arelle import ViewFile
from lxml import etree
from arelle.RenderingResolver import resolveAxesStructure, RENDER_UNITS_PER_CHAR
from arelle.ViewFile import HTML, XML
from arelle.ModelObject import ModelObject
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.FormulaEvaluator import aspectMatches
from arelle.FunctionXs import xsString
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT
from arelle.ModelRenderingObject import (ModelClosedDefinitionNode, ModelEuAxisCoord, ModelFilterDefinitionNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE)
from arelle.PrototypeInstanceObject import FactPrototype
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

def viewRenderedGrid(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None, diffToFile=False, cssExtras=""):
    modelXbrl.modelManager.showStatus(_("saving rendering"))
    view = ViewRenderedGrid(modelXbrl, outfile, lang, cssExtras)

    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
        view.xAxisChildrenFirst.set(sourceView.xAxisChildrenFirst.get())
        view.yAxisChildrenFirst.set(sourceView.yAxisChildrenFirst.get())
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
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table, XbrlConst.table201305, XbrlConst.table201301, XbrlConst.table2011):
                self.tableModelNamespace = xsdNs + "/model"
                break
        super(ViewRenderedGrid, self).__init__(modelXbrl, outfile,
                                               'tableModel xmlns="{0}"'.format(self.tableModelNamespace),
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
        self.xAxisChildrenFirst = nonTkBooleanVar(value=True)
        self.yAxisChildrenFirst = nonTkBooleanVar(value=False)


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


            for discriminator in range(1, 65535):
                # each table z production
                tblAxisRelSet, xTopStructuralNode, yTopStructuralNode, zTopStructuralNode = resolveAxesStructure(self, tblELR)
                self.hasTableFilters = bool(self.modelTable.filterRelationships)

                self.zStrNodesWithChoices = []
                if tblAxisRelSet and self.tblElt is not None:
                    tableLabel = (self.modelTable.genLabel(lang=self.lang, strip=True) or  # use table label, if any
                                  self.roledefinition)
                    if self.type == HTML: # table on each Z
                        # each Z is a separate table in the outer table
                        zTableRow = etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
                        zRowCell = etree.SubElement(zTableRow, "{http://www.w3.org/1999/xhtml}td")
                        zCellTable = etree.SubElement(zRowCell, "{http://www.w3.org/1999/xhtml}table",
                                                      attrib={"border":"1", "cellspacing":"0", "cellpadding":"4", "style":"font-size:8pt;"})
                        self.rowElts = [etree.SubElement(zCellTable, "{http://www.w3.org/1999/xhtml}tr")
                                        for r in range(self.dataFirstRow + self.dataRows - 1)]
                        etree.SubElement(self.rowElts[0], "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":"tableHdr",
                                                 "style":"max-width:100em;",
                                                 "colspan": str(self.dataFirstCol - 1),
                                                 "rowspan": str(self.dataFirstRow - 1)}
                                         ).text = tableLabel
                    elif self.type == XML:
                        self.structuralNodeModelElements = []
                        if discriminator == 1:
                            # headers structure only build once for table
                            tableSetElt = etree.SubElement(self.tblElt, self.tableModelQName("tableSet"))
                            tableSetElt.append(etree.Comment("TableSet linkbase file: {0}, line {1}".format(self.modelTable.modelDocument.basename, self.modelTable.sourceline)))
                            tableSetElt.append(etree.Comment("TableSet namespace: {0}".format(self.modelTable.namespaceURI)))
                            tableSetElt.append(etree.Comment("TableSet linkrole: {0}".format(tblELR)))
                            etree.SubElement(tableSetElt, self.tableModelQName("label")
                                             ).text = tableLabel
                            zAspectStructuralNodes = defaultdict(set)

                            tableElt = etree.SubElement(tableSetElt, self.tableModelQName("table"))
                            self.groupElts = {}
                            self.headerElts = {}
                            self.headerCells = defaultdict(list) # order #: (breakdownNode, xml element)
                            for axis in ("z", "y", "x"):
                                breakdownNodes = self.breakdownNodes.get(axis)
                                if breakdownNodes:
                                    hdrsElt = etree.SubElement(tableElt, self.tableModelQName("headers"),
                                                               attrib={"axis": axis})
                                    for brkdownNode in self.breakdownNodes.get(axis):
                                        groupElt = etree.SubElement(hdrsElt, self.tableModelQName("group"))
                                        groupElt.append(etree.Comment("Breakdown node file: {0}, line {1}".format(brkdownNode.modelDocument.basename, brkdownNode.sourceline)))
                                        label = brkdownNode.genLabel(lang=self.lang, strip=True)
                                        if label:
                                            etree.SubElement(groupElt, self.tableModelQName("label")).text=label
                                        self.groupElts[brkdownNode] = groupElt
                                        # HF TODO omit header if zero cardinality on breakdown
                                        self.headerElts[brkdownNode] = etree.SubElement(groupElt, self.tableModelQName("header"))
                                else:
                                    tableElt.append(etree.Comment("No breakdown group for \"{0}\" axis".format(axis)))
                            self.zAxis(1, zTopStructuralNode, zAspectStructuralNodes, True)
                            self.cellsParentElt = tableElt
                            self.cellsParentElt = etree.SubElement(self.cellsParentElt, self.tableModelQName("cells"),
                                                                   attrib={"axis": "z"})
                            self.cellsParentElt = etree.SubElement(self.cellsParentElt, self.tableModelQName("cells"),
                                                                   attrib={"axis": "y"})
                            ''' move into body cells, for entry row-by-row
                            self.cellsParentElt = etree.SubElement(self.cellsParentElt, self.tableModelQName("cells"),
                                                                  attrib={"axis": "x"})
                            '''
                    # rows/cols only on firstTime for infoset XML, but on each time for xhtml
                    zAspectStructuralNodes = defaultdict(set)
                    self.zAxis(1, zTopStructuralNode, zAspectStructuralNodes, False)
                    xStructuralNodes = []
                    if self.type == HTML or (xTopStructuralNode and xTopStructuralNode.childStructuralNodes):
                        self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                                   xTopStructuralNode, xStructuralNodes, self.xAxisChildrenFirst.get(), True, True)
                    if self.type == HTML: # table/tr goes by row
                        self.yAxisByRow(1, self.dataFirstRow,
                                        yTopStructuralNode, self.yAxisChildrenFirst.get(), True, True)
                    elif self.type == XML: # infoset goes by col of row header
                        if yTopStructuralNode and yTopStructuralNode.childStructuralNodes: # no row header element if no rows
                            self.yAxisByCol(1, self.dataFirstRow,
                                            yTopStructuralNode, self.yAxisChildrenFirst.get(), True, True)
                        # add header cells to header elements
                        for position, breakdownCellElts in sorted(self.headerCells.items()):
                            for breakdownNode, headerCell in breakdownCellElts:
                                self.headerElts[breakdownNode].append(headerCell)
                        for structuralNode,modelElt in self.structuralNodeModelElements: # must do after elements are all arragned
                            modelElt.addprevious(etree.Comment("{0}: label {1}, file {2}, line {3}"
                                                          .format(structuralNode.definitionNode.localName,
                                                                  structuralNode.definitionNode.xlinkLabel,
                                                                  structuralNode.definitionNode.modelDocument.basename,
                                                                  structuralNode.definitionNode.sourceline)))
                            if structuralNode.definitionNode.get('value'):
                                modelElt.addprevious(etree.Comment("   @value {0}".format(structuralNode.definitionNode.get('value'))))
                            for aspect in sorted(structuralNode.aspectsCovered(), key=lambda a: aspectStr(a)):
                                if structuralNode.hasAspect(aspect) and aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS):
                                    aspectValue = structuralNode.aspectValue(aspect)
                                    if aspectValue is None: aspectValue = "(bound dynamically)"
                                    modelElt.addprevious(etree.Comment("   aspect {0}: {1}".format(aspectStr(aspect), xsString(None,None,aspectValue))))
                            for varName, varValue in structuralNode.variables.items():
                                    modelElt.addprevious(etree.Comment("   variable ${0}: {1}".format(varName, varValue)))
                        for headerElt in self.headerElts.values(): # remove empty header elements
                            if not any(e is not None for e in headerElt.iterchildren()):
                                if headerElt.getparent() is not None:
                                    headerElt.getparent().remove(headerElt)
                    self.bodyCells(self.dataFirstRow, yTopStructuralNode, xStructuralNodes, zAspectStructuralNodes, self.yAxisChildrenFirst.get())
                # find next choice structural node
                moreDiscriminators = False
                for zStrNodeWithChoices in self.zStrNodesWithChoices:
                    currentIndex = zStrNodeWithChoices.choiceNodeIndex + 1
                    if currentIndex < len(zStrNodeWithChoices.choiceStructuralNodes):
                        zStrNodeWithChoices.choiceNodeIndex = currentIndex
                        self.zOrdinateChoices[zStrNodeWithChoices.definitionNode] = currentIndex
                        moreDiscriminators = True
                        break
                    else:
                        zStrNodeWithChoices.choiceNodeIndex = 0
                        self.zOrdinateChoices[zStrNodeWithChoices.definitionNode] = 0
                        # continue incrementing next outermore z choices index
                if not moreDiscriminators:
                    break


    def zAxis(self, row, zStructuralNode, zAspectStructuralNodes, discriminatorsTable):
        if zStructuralNode is not None:
            label = zStructuralNode.header(lang=self.lang)
            choiceLabel = None
            effectiveStructuralNode = zStructuralNode
            if zStructuralNode.choiceStructuralNodes: # same as combo box selection in GUI mode
                if not discriminatorsTable:
                    self.zStrNodesWithChoices.insert(0, zStructuralNode) # iteration from last is first
                try:
                    effectiveStructuralNode = zStructuralNode.choiceStructuralNodes[zStructuralNode.choiceNodeIndex]
                    choiceLabel = effectiveStructuralNode.header(lang=self.lang)
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
            if self.type == HTML:
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
            elif self.type == XML:
                # headers element built for first pass on z axis
                if discriminatorsTable:
                    brkdownNode = zStructuralNode.breakdownNode
                    if zStructuralNode.choiceStructuralNodes: # same as combo box selection in GUI mode
                        # hdrElt.set("label", label)
                        if discriminatorsTable:
                            def zSpan(zNode, startNode=False):
                                if startNode:
                                    thisSpan = 0
                                elif zStructuralNode.choiceStructuralNodes:
                                    thisSpan = len(zStructuralNode.choiceStructuralNodes)
                                else:
                                    thisSpan = 1
                                return sum(zSpan(z) for z in zNode.childStructuralNodes) + thisSpan
                            span = zSpan(zStructuralNode, True)
                            for i, choiceStructuralNode in enumerate(zStructuralNode.choiceStructuralNodes):
                                choiceLabel = choiceStructuralNode.header(lang=self.lang)
                                cellElt = etree.Element(self.tableModelQName("cell"),
                                                        attrib={"span": str(span)} if span > 1 else None)
                                self.headerCells[i].append((brkdownNode, cellElt))
                                # self.structuralNodeModelElements.append((zStructuralNode, cellElt))
                                elt = etree.SubElement(cellElt, self.tableModelQName("label"))
                                if choiceLabel:
                                    elt.text = choiceLabel
                        #else: # choiceLabel from above
                        #    etree.SubElement(hdrElt, self.tableModelQName("label")
                        #                     ).text = choiceLabel
                    else: # no combo choices, single label
                        cellElt = etree.Element(self.tableModelQName("cell"))
                        self.headerCells[0].append((brkdownNode, cellElt))
                        # self.structuralNodeModelElements.append((zStructuralNode, cellElt))
                        elt = etree.SubElement(cellElt, self.tableModelQName("label"))
                        if label:
                            elt.text = label

            for aspect in aspectModels[self.aspectModel]:
                if effectiveStructuralNode.hasAspect(aspect, inherit=True): #implies inheriting from other z axes
                    if aspect == Aspect.DIMENSIONS:
                        for dim in (effectiveStructuralNode.aspectValue(Aspect.DIMENSIONS, inherit=True) or emptyList):
                            zAspectStructuralNodes[dim].add(effectiveStructuralNode)
                    else:
                        zAspectStructuralNodes[aspect].add(effectiveStructuralNode)
            for zStructuralNode in zStructuralNode.childStructuralNodes:
                self.zAxis(row + 1, zStructuralNode, zAspectStructuralNodes, discriminatorsTable)

    def xAxis(self, leftCol, topRow, rowBelow, xParentStructuralNode, xStructuralNodes, childrenFirst, renderNow, atTop):
        if xParentStructuralNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            widthToSpanParent = 0
            sideBorder = not xStructuralNodes
            for xStructuralNode in xParentStructuralNode.childStructuralNodes:
                noDescendants = False
                rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, # nested items before totals
                                                            childrenFirst, childrenFirst, False)
                if row - 1 < parentRow:
                    parentRow = row - 1
                #if not leafNode:
                #    rightCol -= 1
                nonAbstract = not xStructuralNode.isAbstract
                if nonAbstract:
                    width += 100 # width for this label
                widthToSpanParent += width
                if childrenFirst:
                    thisCol = rightCol
                else:
                    thisCol = leftCol
                #print ( "thisCol {0} leftCol {1} rightCol {2} topRow{3} renderNow {4} label {5}".format(thisCol, leftCol, rightCol, topRow, renderNow, label))
                if renderNow:
                    label = xStructuralNode.header(lang=self.lang,
                                                   returnGenLabel=isinstance(xStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))
                    columnspan = rightCol - leftCol
                    if columnspan > 0 and nonAbstract: columnspan += 1
                    elt = None
                    if self.type == HTML:
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
                        self.rowElts[topRow-1].insert(leftCol,elt)
                    elif (self.type == XML and # is leaf or no sub-breakdown cardinality
                          # TBD: determine why following clause is needed
                          (True or xStructuralNode.childStructuralNodes is None or columnspan > 0)): # ignore no-breakdown situation
                        brkdownNode = xStructuralNode.breakdownNode
                        cellElt = etree.Element(self.tableModelQName("cell"),
                                            attrib={"span": str(columnspan)} if columnspan > 1 else None)
                        self.headerCells[thisCol].append((brkdownNode, cellElt))
                        # self.structuralNodeModelElements.append((xStructuralNode, cellElt))
                        elt = etree.SubElement(cellElt, self.tableModelQName("label"))
                        if nonAbstract or (leafNode and row > topRow):
                            for rollUpCol in range(topRow - self.colHdrTopRow + 1, self.colHdrRows - 1):
                                rollUpElt = etree.Element(self.tableModelQName("cell"),
                                                          attrib={"rollup":"true"})
                                self.headerCells[thisCol].append((brkdownNode, cellElt))
                        for i, role in enumerate(self.colHdrNonStdRoles):
                            roleLabel = xStructuralNode.header(role=role, lang=self.lang, recurseParent=False) # infoset does not move parent label to decscndant
                            if roleLabel is not None:
                                cellElt.append(etree.Comment("Label role: {0}, lang {1}"
                                                             .format(os.path.basename(role), self.lang)))
                                labelElt = etree.SubElement(cellElt, self.tableModelQName("label"),
                                                            #attrib={"role": role,
                                                            #        "lang": self.lang}
                                                            )
                                labelElt.text = roleLabel

                        for aspect in sorted(xStructuralNode.aspectsCovered(), key=lambda a: aspectStr(a)):
                            if xStructuralNode.hasAspect(aspect) and aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS):
                                aspectValue = xStructuralNode.aspectValue(aspect)
                                if aspectValue is None: aspectValue = "(bound dynamically)"
                                if isinstance(aspectValue, ModelObject): # typed dimension value
                                    aspectValue = innerTextList(aspectValue)
                                if isinstance(aspectValue, QName) and aspectValue.prefix is None: # may be dynamic
                                    try:
                                        aspectValue = self.modelXbrl.qnameConcepts[aspectValue].qname # usually has a prefix
                                    except KeyError:
                                        pass
                                aspElt = etree.SubElement(cellElt, self.tableModelQName("constraint"))
                                etree.SubElement(aspElt, self.tableModelQName("aspect")
                                                 ).text = aspectStr(aspect)
                                etree.SubElement(aspElt, self.tableModelQName("value")
                                                 ).text = xsString(None,None,addQnameValue(self.xmlDoc, aspectValue))
                    if elt is not None:
                        elt.text = label if bool(label) and label != OPEN_ASPECT_ENTRY_SURROGATE else "\u00A0" #produces &nbsp;
                    if nonAbstract:
                        if columnspan > 1 and rowBelow > topRow:   # add spanned left leg portion one row down
                            if self.type == HTML:
                                attrib= {"class":"xAxisSpanLeg",
                                         "rowspan": str(rowBelow - row)}
                                if edgeBorder:
                                    attrib["style"] = edgeBorder
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib=attrib)
                                elt.text = "\u00A0"
                                if childrenFirst:
                                    self.rowElts[topRow].append(elt)
                                else:
                                    self.rowElts[topRow].insert(leftCol,elt)
                        if self.type == HTML:
                            for i, role in enumerate(self.colHdrNonStdRoles):
                                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                    attrib={"class":"xAxisHdr",
                                                            "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                                self.rowElts[self.dataFirstRow - 1 - len(self.colHdrNonStdRoles) + i].insert(thisCol,elt)
                                elt.text = xStructuralNode.header(role=role, lang=self.lang) or "\u00A0"
                        '''
                        if self.colHdrDocRow:
                            doc = xStructuralNode.header(role="http://www.xbrl.org/2008/role/documentation", lang=self.lang)
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
                            code = xStructuralNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
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
                        xStructuralNodes.append(xStructuralNode)
                if nonAbstract:
                    rightCol += 1
                if renderNow and not childrenFirst:
                    self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, childrenFirst, True, False) # render on this pass
                leftCol = rightCol
            return (rightCol, parentRow, widthToSpanParent, noDescendants)

    def yAxisByRow(self, leftCol, row, yParentStructuralNode, childrenFirst, renderNow, atLeft):
        if yParentStructuralNode is not None:
            nestedBottomRow = row
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                nestRow, nextRow = self.yAxisByRow(leftCol + 1, row, yStructuralNode,  # nested items before totals
                                        childrenFirst, childrenFirst, False)
                isAbstract = (yStructuralNode.isAbstract or
                              (yStructuralNode.childStructuralNodes and
                               not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord))))
                isNonAbstract = not isAbstract
                isLabeled = yStructuralNode.isLabeled
                topRow = row
                #print ( "row {0} topRow {1} nxtRow {2} col {3} renderNow {4} label {5}".format(row, topRow, nextRow, leftCol, renderNow, label))
                if renderNow and isLabeled:
                    label = yStructuralNode.header(lang=self.lang,
                                                   returnGenLabel=isinstance(yStructuralNode.definitionNode, ModelClosedDefinitionNode),
                                                   recurseParent=not isinstance(yStructuralNode.definitionNode, ModelFilterDefinitionNode))
                    columnspan = self.rowHdrCols - leftCol + 1 if isNonAbstract or nextRow == row else 1
                    if childrenFirst and isNonAbstract and nextRow > row:
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib={"class":"yAxisSpanArm",
                                                    "style":"text-align:center;min-width:2em;",
                                                    "rowspan": str(nextRow - topRow)}
                                            )
                        insertPosition = self.rowElts[nextRow-1].__len__()
                        self.rowElts[row - 1].insert(insertPosition, elt)
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
                    depth = yStructuralNode.depth
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
                        self.rowElts[hdrRow-1].append(elt)
                        if not childrenFirst and nestRow > hdrRow:   # add spanned left leg portion one row down
                            etree.SubElement(self.rowElts[hdrRow],
                                             "{http://www.w3.org/1999/xhtml}th",
                                             attrib={"class":"yAxisSpanLeg",
                                                     "style":"text-align:center;max-width:{0}pt;{1}".format(RENDER_UNITS_PER_CHAR, edgeBorder),
                                                     "rowspan": str(nestRow - hdrRow)}
                                             ).text = "\u00A0"
                        hdrClass = "yAxisHdr" if not childrenFirst else "yAxisHdrWithChildrenFirst"
                        for i, role in enumerate(self.rowHdrNonStdRoles):
                            hdr = yStructuralNode.header(role=role, lang=self.lang)
                            etree.SubElement(self.rowElts[hdrRow - 1],
                                             "{http://www.w3.org/1999/xhtml}th",
                                             attrib={"class":hdrClass,
                                                     "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                             ).text = hdr or "\u00A0"
                        '''
                        if self.rowHdrDocCol:
                            docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                            doc = yStructuralNode.header(role="http://www.xbrl.org/2008/role/documentation")
                            etree.SubElement(self.rowElts[hdrRow - 1],
                                             "{http://www.w3.org/1999/xhtml}th",
                                             attrib={"class":hdrClass,
                                                     "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                             ).text = doc or "\u00A0"
                        if self.rowHdrCodeCol:
                            codeCol = self.dataFirstCol - 1
                            code = yStructuralNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                            etree.SubElement(self.rowElts[hdrRow - 1],
                                             "{http://www.w3.org/1999/xhtml}th",
                                             attrib={"class":hdrClass,
                                                     "style":"text-align:center;max-width:40pt;{0}".format(edgeBorder)}
                                             ).text = code or "\u00A0"
                        # gridBorder(self.gridRowHdr, leftCol, self.dataFirstRow - 1, BOTTOMBORDER)
                        '''
                    elif nestRow > hdrRow:
                        self.rowElts[hdrRow-1].insert(leftCol - 1, elt)
                if isNonAbstract:
                    row += 1
                elif childrenFirst:
                    row = nextRow
                if nestRow > nestedBottomRow:
                    nestedBottomRow = nestRow + (isNonAbstract and not childrenFirst)
                if row > nestedBottomRow:
                    nestedBottomRow = row
                #if renderNow and not childrenFirst:
                #    dummy, row = self.yAxis(leftCol + 1, row, yAxisHdrObj, childrenFirst, True, False) # render on this pass
                if not childrenFirst:
                    dummy, row = self.yAxisByRow(leftCol + 1, row, yStructuralNode, childrenFirst, renderNow, False) # render on this pass
            return (nestedBottomRow, row)

    def yAxisByCol(self, leftCol, row, yParentStructuralNode, childrenFirst, renderNow, atTop):
        if yParentStructuralNode is not None:
            nestedBottomRow = row
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                nestRow, nextRow = self.yAxisByCol(leftCol + 1, row, yStructuralNode,  # nested items before totals
                                                   childrenFirst, childrenFirst, False)
                isAbstract = (yStructuralNode.isAbstract or
                              (yStructuralNode.childStructuralNodes and
                               not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord))))
                isNonAbstract = not isAbstract
                isLabeled = yStructuralNode.isLabeled
                topRow = row
                if childrenFirst and isNonAbstract:
                    row = nextRow
                #print ( "thisCol {0} leftCol {1} rightCol {2} topRow{3} renderNow {4} label {5}".format(thisCol, leftCol, rightCol, topRow, renderNow, label))
                if renderNow and isLabeled:
                    label = yStructuralNode.header(lang=self.lang,
                                                   returnGenLabel=isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)),
                                                   recurseParent=not isinstance(yStructuralNode.definitionNode, ModelFilterDefinitionNode))
                    brkdownNode = yStructuralNode.breakdownNode
                    rowspan= nestRow - row + 1
                    cellElt = etree.Element(self.tableModelQName("cell"),
                                            attrib={"span": str(rowspan)} if rowspan > 1 else None)
                    elt = etree.SubElement(cellElt, self.tableModelQName("label"))
                    elt.text = label if label != OPEN_ASPECT_ENTRY_SURROGATE else ""
                    self.headerCells[leftCol].append((brkdownNode, cellElt))
                    # self.structuralNodeModelElements.append((yStructuralNode, cellElt))
                    for rollUpCol in range(leftCol, self.rowHdrCols - 1):
                        rollUpElt = etree.Element(self.tableModelQName("cell"),
                                                  attrib={"rollup":"true"})
                        self.headerCells[leftCol].append((brkdownNode, rollUpElt))
                    #if isNonAbstract:
                    i = -1 # for case where no enumeration takes place
                    for i, role in enumerate(self.rowHdrNonStdRoles):
                        roleLabel = yStructuralNode.header(role=role, lang=self.lang, recurseParent=False)
                        if roleLabel is not None:
                            cellElt.append(etree.Comment("Label role: {0}, lang {1}"
                                                         .format(os.path.basename(role), self.lang)))
                            labelElt = etree.SubElement(cellElt, self.tableModelQName("label"),
                                                        #attrib={"role":role,
                                                        #        "lang":self.lang}
                                ).text = roleLabel
                            self.headerCells[leftCol].append((brkdownNode, cellElt))
                    for aspect in sorted(yStructuralNode.aspectsCovered(), key=lambda a: aspectStr(a)):
                        if yStructuralNode.hasAspect(aspect) and aspect not in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS):
                            aspectValue = yStructuralNode.aspectValue(aspect)
                            if aspectValue is None: aspectValue = "(bound dynamically)"
                            if isinstance(aspectValue, ModelObject): # typed dimension value
                                aspectValue = innerTextList(aspectValue)
                            if isinstance(aspectValue, QName) and aspectValue.prefix is None: # may be dynamic
                                try:
                                    aspectValue = self.modelXbrl.qnameConcepts[aspectValue].qname # usually has a prefix
                                except KeyError:
                                    pass
                            if isinstance(aspectValue, str) and aspectValue.startswith(OPEN_ASPECT_ENTRY_SURROGATE):
                                continue  # not an aspect, position for a new entry
                            elt = etree.SubElement(cellElt, self.tableModelQName("constraint"))
                            etree.SubElement(elt, self.tableModelQName("aspect")
                                             ).text = aspectStr(aspect)
                            etree.SubElement(elt, self.tableModelQName("value")
                                             ).text = xsString(None,None,addQnameValue(self.xmlDoc, aspectValue))
                        '''
                        if self.rowHdrDocCol:
                            labelElt = etree.SubElement(cellElt, self.tableModelQName("label"),
                                                        attrib={"span": str(rowspan)} if rowspan > 1 else None)
                            elt.text = yStructuralNode.header(role="http://www.xbrl.org/2008/role/documentation",
                                                       lang=self.lang)
                            self.rowHdrElts[self.rowHdrCols - 1].append(elt)
                        if self.rowHdrCodeCol:
                            elt = etree.Element(self.tableModelQName("label"),
                                                attrib={"span": str(rowspan)} if rowspan > 1 else None)
                            elt.text = yStructuralNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code",
                                                       lang=self.lang)
                            self.rowHdrElts[self.rowHdrCols - 1 + self.rowHdrDocCol].append(elt)
                        '''
                if isNonAbstract:
                    row += 1
                elif childrenFirst:
                    row = nextRow
                if nestRow > nestedBottomRow:
                    nestedBottomRow = nestRow + (isNonAbstract and not childrenFirst)
                if row > nestedBottomRow:
                    nestedBottomRow = row
                #if renderNow and not childrenFirst:
                #    dummy, row = self.yAxis(leftCol + 1, row, yStructuralNode, childrenFirst, True, False) # render on this pass
                if not childrenFirst:
                    dummy, row = self.yAxisByCol(leftCol + 1, row, yStructuralNode, childrenFirst, renderNow, False) # render on this pass
            return (nestedBottomRow, row)


    def bodyCells(self, row, yParentStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst):
        if yParentStructuralNode is not None:
            dimDefaults = self.modelXbrl.qnameDimensionDefaults
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                if yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst)
                if not (yStructuralNode.isAbstract or
                        (yStructuralNode.childStructuralNodes and
                         not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))) and yStructuralNode.isLabeled:
                    if self.type == XML:
                        if self.breakdownNodes.get("x"):
                            cellsParentElt = etree.SubElement(self.cellsParentElt, self.tableModelQName("cells"),
                                                           attrib={"axis": "x"})
                        else:
                            cellsParentElt = self.cellsParentElt
                    isEntryPrototype = yStructuralNode.isEntryPrototype(default=False) # row to enter open aspects
                    yAspectStructuralNodes = defaultdict(set)
                    for aspect in aspectModels[self.aspectModel]:
                        if yStructuralNode.hasAspect(aspect):
                            if aspect == Aspect.DIMENSIONS:
                                for dim in (yStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                    yAspectStructuralNodes[dim].add(yStructuralNode)
                            else:
                                yAspectStructuralNodes[aspect].add(yStructuralNode)
                    yTagSelectors = yStructuralNode.tagSelectors
                    # data for columns of rows
                    ignoreDimValidity = self.ignoreDimValidity.get()
                    for i, xStructuralNode in enumerate(xStructuralNodes):
                        xAspectStructuralNodes = defaultdict(set)
                        for aspect in aspectModels[self.aspectModel]:
                            if xStructuralNode.hasAspect(aspect):
                                if aspect == Aspect.DIMENSIONS:
                                    for dim in (xStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                        xAspectStructuralNodes[dim].add(xStructuralNode)
                                else:
                                    xAspectStructuralNodes[aspect].add(xStructuralNode)
                        cellTagSelectors = yTagSelectors | xStructuralNode.tagSelectors
                        cellAspectValues = {}
                        matchableAspects = set()
                        for aspect in xAspectStructuralNodes.keys() | yAspectStructuralNodes.keys() | zAspectStructuralNodes.keys():
                            aspectValue = xStructuralNode.inheritedAspectValue(yStructuralNode,
                                               self, aspect, cellTagSelectors,
                                               xAspectStructuralNodes, yAspectStructuralNodes, zAspectStructuralNodes)
                            # value is None for a dimension whose value is to be not reported in this slice
                            if (isinstance(aspect, int) or  # not a dimension
                                dimDefaults.get(aspect) != aspectValue or # explicit dim defaulted will equal the value
                                aspectValue is not None): # typed dim absent will be none
                                cellAspectValues[aspect] = aspectValue
                            matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                        cellDefaultedDims = dimDefaults - cellAspectValues.keys()
                        priItemQname = cellAspectValues.get(Aspect.CONCEPT)

                        concept = self.modelXbrl.qnameConcepts.get(priItemQname)
                        conceptNotAbstract = concept is None or not concept.isAbstract
                        from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                        fact = None
                        value = None
                        objectId = None
                        justify = None
                        fp = FactPrototype(self, cellAspectValues)
                        if conceptNotAbstract:
                            # reduce set of matchable facts to those with pri item qname and have dimension aspects
                            facts = self.modelXbrl.factsByQname[priItemQname] if priItemQname else self.modelXbrl.factsInInstance
                            if self.hasTableFilters:
                                facts = self.modelTable.filterFacts(self.rendrCntx, facts)
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
                            for fact in facts:
                                if (all(aspectMatches(self.rendrCntx, fact, fp, aspect)
                                        for aspect in matchableAspects) and
                                    all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                        for dim in cellDefaultedDims) and
                                        len(fp.context.qnameDims) == len(fact.context.qnameDims)):
                                    if yStructuralNode.hasValueExpression(xStructuralNode):
                                        value = yStructuralNode.evalValueExpression(fact, xStructuralNode)
                                    else:
                                        value = fact.effectiveValue
                                    justify = "right" if fact.isNumeric else "left"
                                    break
                        if justify is None:
                            justify = "right" if fp.isNumeric else "left"
                        if conceptNotAbstract:
                            if self.type == XML:
                                cellsParentElt.append(etree.Comment("Cell concept {0}: segDims {1}, scenDims {2}"
                                                                    .format(fp.qname,
                                                                         ', '.join("({}={})".format(dimVal.dimensionQname, dimVal.memberQname)
                                                                                   for dimVal in sorted(fp.context.segDimVals.values(), key=lambda d: d.dimensionQname)),
                                                                         ', '.join("({}={})".format(dimVal.dimensionQname, dimVal.memberQname)
                                                                                   for dimVal in sorted(fp.context.scenDimVals.values(), key=lambda d: d.dimensionQname)),
                                                                         )))
                            if value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp) or isEntryPrototype:
                                if self.type == HTML:
                                    etree.SubElement(self.rowElts[row - 1],
                                                     "{http://www.w3.org/1999/xhtml}td",
                                                     attrib={"class":"cell",
                                                             "style":"text-align:{0};width:8em".format(justify)}
                                                     ).text = value or "\u00A0"
                                elif self.type == XML:
                                    if value is not None and fact is not None:
                                        cellsParentElt.append(etree.Comment("{0}: context {1}, value {2}, file {3}, line {4}"
                                                                            .format(fact.qname,
                                                                                 fact.contextID,
                                                                                 value[:32], # no more than 32 characters
                                                                                 fact.modelDocument.basename,
                                                                                 fact.sourceline)))
                                    elif fact is not None:
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
                                    if value is not None and fact is not None:
                                        etree.SubElement(cellElt, self.tableModelQName("fact")
                                                         ).text = '{}#{}'.format(fact.modelDocument.basename,
                                                                                 elementFragmentIdentifier(fact))
                            else:
                                if self.type == HTML:
                                    etree.SubElement(self.rowElts[row - 1],
                                                     "{http://www.w3.org/1999/xhtml}td",
                                                     attrib={"class":"blockedCell",
                                                             "style":"text-align:{0};width:8em".format(justify)}
                                                     ).text = "\u00A0\u00A0"
                                elif self.type == XML:
                                    etree.SubElement(cellsParentElt, self.tableModelQName("cell"),
                                                     attrib={"blocked":"true"})
                        else: # concept is abstract
                            if self.type == HTML:
                                etree.SubElement(self.rowElts[row - 1],
                                                 "{http://www.w3.org/1999/xhtml}td",
                                                 attrib={"class":"abstractCell",
                                                         "style":"text-align:{0};width:8em".format(justify)}
                                                 ).text = "\u00A0\u00A0"
                            elif self.type == XML:
                                etree.SubElement(cellsParentElt, self.tableModelQName("cell"),
                                                 attrib={"abstract":"true"})
                        fp.clear()  # dereference
                    row += 1
                if not yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst)
        return row
