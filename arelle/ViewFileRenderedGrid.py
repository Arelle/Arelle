'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile
from lxml import etree
from arelle.ViewUtilRenderedGrid import (getTblAxes, inheritedAspectValue)
from arelle.ViewFile import HTML, XML
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect, aspectStr
from arelle.FormulaEvaluator import aspectMatches
from arelle.PrototypeInstanceObject import FactPrototype
from collections import defaultdict

emptySet = set()
emptyList = []

def viewRenderedGrid(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None, diffToFile=False):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, outfile, lang)
    
    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
        view.xAxisChildrenFirst.set(sourceView.xAxisChildrenFirst.get())
        view.yAxisChildrenFirst.set(sourceView.yAxisChildrenFirst.get())
    view.view(viewTblELR)
    if diffToFile:
        from arelle.ValidateInfoset import validateRenderingInfoset
        validateRenderingInfoset(modelXbrl, outfile, view.xmlDoc)
        view.close(noWrite=True)
    else:   
        view.close()
    
class ViewRenderedGrid(ViewFile.View):
    def __init__(self, modelXbrl, outfile, lang):
        super(ViewRenderedGrid, self).__init__(modelXbrl, outfile, 
                                               'tableModel xmlns="http://xbrl.org/2012/table/model"', 
                                               lang, style="rendering")
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
                tblAxisRelSet, xOrdCntx, yOrdCntx, zOrdCntx = getTblAxes(self, tblELR) 
                
                if tblAxisRelSet and self.tblElt is not None:
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
                                         ).text = self.roledefinition
                    elif self.type == XML:
                        self.ordCntxElts = []
                        if discriminator == 1:
                            tableSetElt = etree.SubElement(self.tblElt, "{http://xbrl.org/2012/table/model}tableSet")
                            tableSetElt.append(etree.Comment("TableSet linkbase file: {0}, line {1}".format(self.modelTable.modelDocument.basename, self.modelTable.sourceline)))
                            tableSetElt.append(etree.Comment("TableSet namespace: {0}".format(self.modelTable.namespaceURI)))
                            tableSetElt.append(etree.Comment("TableSet linkrole: {0}".format(tblELR)))
                            self.zHdrsElt = etree.SubElement(tableSetElt, "{http://xbrl.org/2012/table/model}headers")
                            zAspects = defaultdict(set)
                            self.zAxis(1, zOrdCntx, zAspects, True)
                        tableElt = etree.SubElement(tableSetElt, "{http://xbrl.org/2012/table/model}table",
                                                    attrib={"label": self.roledefinition})
                        hdrsElts = dict((disposition,
                                         etree.SubElement(tableElt, "{http://xbrl.org/2012/table/model}headers",
                                                          attrib={"disposition": disposition}))
                                        for disposition in ("y", "x"))
                        self.zHdrsElt = hdrsElts["y"]  # z-comments go before y subelement of tableElt
                        # new y,x cells on each Z combination
                        if yOrdCntx.subOrdinateContexts: # no row header element if no rows
                            self.rowHdrElts = [etree.SubElement(hdrsElts["y"], "{http://xbrl.org/2012/table/model}header")
                                               for i in range(self.rowHdrCols - 1 + self.rowHdrDocCol + self.rowHdrCodeCol)]
                        else:
                            hdrsElts["y"].append(etree.Comment("no rows in this table"))
                        if xOrdCntx.subOrdinateContexts: # no col header element if no cols
                            self.colHdrElts = [etree.SubElement(hdrsElts["x"], "{http://xbrl.org/2012/table/model}header")
                                               for i in range(self.colHdrRows - 1 + self.colHdrDocRow + self.colHdrCodeRow)]
                        else:
                            hdrsElts["x"].append(etree.Comment("no columns in this table"))
                        self.zCells = etree.SubElement(tableElt, "{http://xbrl.org/2012/table/model}cells",
                                                          attrib={"disposition": "z"})
                        self.yCells = etree.SubElement(self.zCells, "{http://xbrl.org/2012/table/model}cells",
                                                          attrib={"disposition": "y"})
                        ''' move into body cells, for entry row-by-row
                        self.xCells = etree.SubElement(self.yCells, "{http://xbrl.org/2012/table/model}cells",
                                                          attrib={"disposition": "x"})
                        '''
                    # rows/cols only on firstTime for infoset XML, but on each time for xhtml
                    zAspects = defaultdict(set)
                    self.zOrdsWithChoices = []
                    self.zAxis(1, zOrdCntx, zAspects, False)
                    xOrdCntxs = []
                    if self.type == HTML or (xOrdCntx.subOrdinateContexts):
                        self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                                   xOrdCntx, xOrdCntxs, self.xAxisChildrenFirst.get(), True, True)
                    if self.type == HTML: # table/tr goes by row
                        self.yAxisByRow(1, self.dataFirstRow,
                                        yOrdCntx, self.yAxisChildrenFirst.get(), True, True)
                    elif self.type == XML: # infoset goes by col of row header
                        if yOrdCntx.subOrdinateContexts: # no row header element if no rows
                            self.yAxisByCol(1, self.dataFirstRow,
                                            yOrdCntx, self.yAxisChildrenFirst.get(), True, True)
                        for ordCntx,elt in self.ordCntxElts: # must do after elements are all arragned
                            elt.addprevious(etree.Comment("{0}: label {1}, file {2}, line {3}"
                                                          .format(ordCntx._axisObject.localName,
                                                                  ordCntx._axisObject.xlinkLabel,
                                                                  ordCntx._axisObject.modelDocument.basename, 
                                                                  ordCntx._axisObject.sourceline)))
                            if ordCntx._axisObject.get('value'):
                                elt.addprevious(etree.Comment("   @value {0}".format(ordCntx._axisObject.get('value'))))
                            for aspect in sorted(ordCntx.aspectsCovered(), key=lambda a: aspectStr(a)):
                                if ordCntx.hasAspect(aspect) and aspect != Aspect.DIMENSIONS:
                                    aspectValue = ordCntx.aspectValue(aspect)
                                    if aspectValue is None: aspectValue = "(bound dynamically)"
                                    elt.addprevious(etree.Comment("   aspect {0}: {1}".format(aspectStr(aspect), aspectValue)))
                            for varName, varValue in ordCntx.variables.items():
                                    elt.addprevious(etree.Comment("   variable ${0}: {1}".format(varName, varValue)))
                            
                    self.bodyCells(self.dataFirstRow, yOrdCntx, xOrdCntxs, zAspects, self.yAxisChildrenFirst.get())
                # find next choice ord
                moreDiscriminators = False
                for zOrdWithChoice in self.zOrdsWithChoices:
                    currentIndex = zOrdWithChoice.choiceOrdinateIndex + 1
                    if currentIndex < len(zOrdWithChoice.choiceOrdinateContexts):
                        zOrdWithChoice.choiceOrdinateIndex = currentIndex
                        self.zOrdinateChoices[zOrdWithChoice._axisObject] = currentIndex
                        moreDiscriminators = True
                        break
                    else:
                        zOrdWithChoice.choiceOrdinateIndex = 0
                        self.zOrdinateChoices[zOrdWithChoice._axisObject] = 0
                        # continue incrementing next outermore z choices index
                if not moreDiscriminators:
                    break

            
    def zAxis(self, row, zOrdCntx, zAspects, discriminatorsTable):
        if zOrdCntx is not None:
            label = zOrdCntx.header(lang=self.lang)
            choiceLabel = None
            if zOrdCntx.choiceOrdinateContexts: # same as combo box selection in GUI mode
                if not discriminatorsTable:
                    self.zOrdsWithChoices.insert(0, zOrdCntx) # iteration from last is first
                try:
                    zChoiceOrdCntx = zOrdCntx.choiceOrdinateContexts[zOrdCntx.choiceOrdinateIndex]
                    choiceLabel = zChoiceOrdCntx.header(lang=self.lang)
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
                # per JS, no header elements inside each table
                if discriminatorsTable:
                    hdrElt = etree.SubElement(self.zHdrsElt, "{http://xbrl.org/2012/table/model}header")
                    self.ordCntxElts.append((zOrdCntx, hdrElt))
                    if zOrdCntx.choiceOrdinateContexts: # same as combo box selection in GUI mode
                        # hdrElt.set("label", label)
                        if discriminatorsTable:
                            for choiceOrdCntx in zOrdCntx.choiceOrdinateContexts:
                                choiceLabel = choiceOrdCntx.header(lang=self.lang)
                                etree.SubElement(hdrElt, "{http://xbrl.org/2012/table/model}label"
                                                 ).text = choiceLabel
                        #else: # choiceLabel from above 
                        #    etree.SubElement(hdrElt, "{http://xbrl.org/2012/table/model}label"
                        #                     ).text = choiceLabel
                    else: # no combo choices, single label
                        etree.SubElement(hdrElt, "{http://xbrl.org/2012/table/model}label"
                                         ).text = label
                else:
                    if choiceLabel: # same as combo box selection in GUI mode
                        comment = etree.Comment("Z axis {0}: {1}".format(label, choiceLabel))
                    else:
                        comment = etree.Comment("Z axis: {0}".format(label))
                    if isinstance(self.zHdrsElt, etree._Comment):
                        self.zHdrsElt.addnext(comment)
                    else:
                        self.zHdrsElt.addprevious(comment)
                    self.zHdrsElt = comment                    

            if zOrdCntx.subOrdinateContexts:
                for zOrdCntx in zOrdCntx.subOrdinateContexts:
                    self.zAxis(row + 1, zOrdCntx, zAspects, discriminatorsTable)
            else: # nested-nost element, aspects process inheritance
                for aspect in aspectModels[self.aspectModel]:
                    for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                        if zOrdCntx.hasAspect(ruleAspect): #implies inheriting from other z axes
                            if ruleAspect == Aspect.DIMENSIONS:
                                for dim in (zOrdCntx.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                    zAspects[dim].add(zOrdCntx)
                            else:
                                zAspects[ruleAspect].add(zOrdCntx)
    
    def xAxis(self, leftCol, topRow, rowBelow, xParentOrdCntx, xOrdCntxs, childrenFirst, renderNow, atTop):
        parentRow = rowBelow
        noDescendants = True
        rightCol = leftCol
        widthToSpanParent = 0
        sideBorder = not xOrdCntxs
        for xOrdCntx in xParentOrdCntx.subOrdinateContexts:
            noDescendants = False
            rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xOrdCntx, xOrdCntxs, # nested items before totals
                                                        childrenFirst, childrenFirst, False)
            if row - 1 < parentRow:
                parentRow = row - 1
            #if not leafNode: 
            #    rightCol -= 1
            nonAbstract = not xOrdCntx.isAbstract
            if nonAbstract:
                width += 100 # width for this label
            widthToSpanParent += width
            label = xOrdCntx.header(lang=self.lang)
            if childrenFirst:
                thisCol = rightCol
            else:
                thisCol = leftCol
            #print ( "thisCol {0} leftCol {1} rightCol {2} topRow{3} renderNow {4} label {5}".format(thisCol, leftCol, rightCol, topRow, renderNow, label))
            if renderNow:
                columnspan = rightCol - leftCol + (1 if nonAbstract else 0)
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
                        attrib["rowspan"] = str(row - topRow + 1)
                    elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                        attrib=attrib)
                    self.rowElts[topRow-1].insert(leftCol,elt)
                elif self.type == XML:
                    elt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                        attrib={"span": str(columnspan)} if columnspan > 1 else None)
                    self.colHdrElts[topRow - self.colHdrTopRow].insert(leftCol,elt)
                    self.ordCntxElts.append((xOrdCntx, elt))
                    if nonAbstract or (leafNode and row > topRow):
                        for rollUpCol in range(topRow - self.colHdrTopRow + 1, self.colHdrRows - 1):
                            rollUpElt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                                      attrib={"rollup":"true"})
                            if childrenFirst:
                                self.colHdrElts[rollUpCol].append(rollUpElt)
                            else:
                                self.colHdrElts[rollUpCol].insert(leftCol,rollUpElt)
                elt.text = label or "\u00A0" #produces &nbsp;
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
                    if self.colHdrDocRow:
                        doc = xOrdCntx.header(role="http://www.xbrl.org/2008/role/documentation", lang=self.lang)
                        if self.type == HTML:
                            elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                attrib={"class":"xAxisHdr",
                                                        "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                            self.rowElts[self.dataFirstRow - 2 - self.rowHdrCodeCol].insert(thisCol,elt)
                        elif self.type == XML:
                            elt = etree.Element("{http://xbrl.org/2012/table/model}label")
                            self.colHdrElts[self.colHdrRows - 1].insert(thisCol,elt)
                        elt.text = doc or "\u00A0"
                    if self.colHdrCodeRow:
                        code = xOrdCntx.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        if self.type == HTML:
                            elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                                attrib={"class":"xAxisHdr",
                                                        "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                            self.rowElts[self.dataFirstRow - 2].insert(thisCol,elt)
                        elif self.type == XML:
                            elt = etree.Element("{http://xbrl.org/2012/table/model}label")
                            self.colHdrElts[self.colHdrRows - 1 + self.colHdrDocRow].insert(thisCol,elt)
                        elt.text = code or "\u00A0"
                    xOrdCntxs.append(xOrdCntx)
            if nonAbstract:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xOrdCntx, xOrdCntxs, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxisByRow(self, leftCol, row, yParentOrdCntx, childrenFirst, renderNow, atLeft):
        nestedBottomRow = row
        for yOrdCntx in yParentOrdCntx.subOrdinateContexts:
            nestRow, nextRow = self.yAxisByRow(leftCol + 1, row, yOrdCntx,  # nested items before totals
                                    childrenFirst, childrenFirst, False)
            isAbstract = yOrdCntx.isAbstract
            isNonAbstract = not isAbstract
            label = yOrdCntx.header(lang=self.lang)
            topRow = row
            #print ( "row {0} topRow {1} nxtRow {2} col {3} renderNow {4} label {5}".format(row, topRow, nextRow, leftCol, renderNow, label))
            if renderNow:
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
                attrib = {"style":"text-align:{0};max-width:{1}em;{2}".format(
                                        "left" if isNonAbstract or nestRow == hdrRow else "center",
                                        # this is a wrap length max sidth in characters
                                        self.rowHdrColWidth[leftCol] if isAbstract else
                                        self.rowHdrWrapLength -
                                        sum(self.rowHdrColWidth[i] for i in range(leftCol)),
                                        edgeBorder),
                          "colspan": str(columnspan)}
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
                elt.text = label if label else "\u00A0"
                if isNonAbstract:
                    self.rowElts[hdrRow-1].append(elt)
                    if not childrenFirst and nestRow > hdrRow:   # add spanned left leg portion one row down
                        etree.SubElement(self.rowElts[hdrRow], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":"yAxisSpanLeg",
                                                 "style":"text-align:center;max-width:16pt;{0}".format(edgeBorder),
                                                 "rowspan": str(nestRow - hdrRow)}
                                         ).text = "\u00A0"
                    hdrClass = "yAxisHdr" if not childrenFirst else "yAxisHdrWithChildrenFirst"
                    if self.rowHdrDocCol:
                        docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                        doc = yOrdCntx.header(role="http://www.xbrl.org/2008/role/documentation")
                        etree.SubElement(self.rowElts[hdrRow - 1], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                         ).text = doc or "\u00A0"
                    if self.rowHdrCodeCol:
                        codeCol = self.dataFirstCol - 1
                        code = yOrdCntx.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        etree.SubElement(self.rowElts[hdrRow - 1], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:center;max-width:40pt;{0}".format(edgeBorder)}
                                         ).text = code or "\u00A0"
                    # gridBorder(self.gridRowHdr, leftCol, self.dataFirstRow - 1, BOTTOMBORDER)
                else:
                    self.rowElts[hdrRow-1].insert(leftCol - 1, elt)
            if isNonAbstract:
                row += 1
            elif childrenFirst:
                row = nextRow
            if nestRow > nestedBottomRow:
                nestedBottomRow = nestRow + (not childrenFirst)
            if row > nestedBottomRow:
                nestedBottomRow = row
            #if renderNow and not childrenFirst:
            #    dummy, row = self.yAxis(leftCol + 1, row, yAxisHdrObj, childrenFirst, True, False) # render on this pass            
            if not childrenFirst:
                dummy, row = self.yAxisByRow(leftCol + 1, row, yOrdCntx, childrenFirst, renderNow, False) # render on this pass
        return (nestedBottomRow, row)

    def yAxisByCol(self, leftCol, row, yParentOrdCntx, childrenFirst, renderNow, atTop):
        nestedBottomRow = row
        for yOrdCntx in yParentOrdCntx.subOrdinateContexts:
            nestRow, nextRow = self.yAxisByCol(leftCol + 1, row, yOrdCntx,  # nested items before totals
                                               childrenFirst, childrenFirst, False)
            isAbstract = yOrdCntx.isAbstract
            isNonAbstract = not isAbstract
            label = yOrdCntx.header(lang=self.lang)
            topRow = row
            if childrenFirst and isNonAbstract:
                row = nextRow
            #print ( "thisCol {0} leftCol {1} rightCol {2} topRow{3} renderNow {4} label {5}".format(thisCol, leftCol, rightCol, topRow, renderNow, label))
            if renderNow:
                rowspan= nestRow - row + 1
                elt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                    attrib={"span": str(rowspan)} if rowspan > 1 else None)
                elt.text = label
                self.rowHdrElts[leftCol - 1].append(elt)
                self.ordCntxElts.append((yOrdCntx, elt))
                for rollUpCol in range(leftCol, self.rowHdrCols - 1):
                    rollUpElt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                              attrib={"rollup":"true"})
                    self.rowHdrElts[rollUpCol].append(rollUpElt)
                if isNonAbstract:
                    if self.rowHdrDocCol:
                        elt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                            attrib={"span": str(rowspan)} if rowspan > 1 else None)
                        elt.text = yOrdCntx.header(role="http://www.xbrl.org/2008/role/documentation",
                                                   lang=self.lang)
                        self.rowHdrElts[self.rowHdrCols - 1].append(elt)
                    if self.rowHdrCodeCol:
                        elt = etree.Element("{http://xbrl.org/2012/table/model}label",
                                            attrib={"span": str(rowspan)} if rowspan > 1 else None)
                        elt.text = yOrdCntx.header(role="http://www.eurofiling.info/role/2010/coordinate-code",
                                                   lang=self.lang)
                        self.rowHdrElts[self.rowHdrCols - 1 + self.rowHdrDocCol].append(elt)
            if isNonAbstract:
                row += 1
            elif childrenFirst:
                row = nextRow
            if nestRow > nestedBottomRow:
                nestedBottomRow = nestRow + (not childrenFirst)
            if row > nestedBottomRow:
                nestedBottomRow = row
            #if renderNow and not childrenFirst:
            #    dummy, row = self.yAxis(leftCol + 1, row, yOrdCntx, childrenFirst, True, False) # render on this pass
            if not childrenFirst:
                dummy, row = self.yAxisByCol(leftCol + 1, row, yOrdCntx, childrenFirst, renderNow, False) # render on this pass
        return (nestedBottomRow, row)
            
    
    def bodyCells(self, row, yParentOrdCntx, xOrdCntxs, zAspects, yChildrenFirst):
        rendrCntx = getattr(self.modelXbrl, "rendrCntx", None) # none for EU 2010 tables
        dimDefaults = self.modelXbrl.qnameDimensionDefaults
        for yOrdCntx in yParentOrdCntx.subOrdinateContexts:
            if yChildrenFirst:
                row = self.bodyCells(row, yOrdCntx, xOrdCntxs, zAspects, yChildrenFirst)
            if not yOrdCntx.isAbstract:
                if self.type == XML:
                    self.xCells = etree.SubElement(self.yCells, "{http://xbrl.org/2012/table/model}cells",
                                                   attrib={"disposition": "x"})
                yAspects = defaultdict(set)
                for aspect in aspectModels[self.aspectModel]:
                    for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                        if yOrdCntx.hasAspect(ruleAspect):
                            if ruleAspect == Aspect.DIMENSIONS:
                                for dim in (yOrdCntx.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                    yAspects[dim].add(yOrdCntx)
                            else:
                                yAspects[ruleAspect].add(yOrdCntx)
                # data for columns of rows
                ignoreDimValidity = self.ignoreDimValidity.get()
                for i, xOrdCntx in enumerate(xOrdCntxs):
                    xAspects = defaultdict(set)
                    for aspect in aspectModels[self.aspectModel]:
                        for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                            if xOrdCntx.hasAspect(ruleAspect):
                                if ruleAspect == Aspect.DIMENSIONS:
                                    for dim in (xOrdCntx.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                        xAspects[dim].add(xOrdCntx)
                                else:
                                    xAspects[ruleAspect].add(xOrdCntx)
                    cellAspectValues = {}
                    matchableAspects = set()
                    for aspect in _DICT_SET(xAspects.keys()) | _DICT_SET(yAspects.keys()) | _DICT_SET(zAspects.keys()):
                        aspectValue = inheritedAspectValue(self, aspect, xAspects, yAspects, zAspects, xOrdCntx, yOrdCntx)
                        if dimDefaults.get(aspect) != aspectValue: # don't include defaulted dimensions
                            cellAspectValues[aspect] = aspectValue
                        matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                    cellDefaultedDims = _DICT_SET(dimDefaults) - _DICT_SET(cellAspectValues.keys())
                    priItemQname = cellAspectValues.get(Aspect.CONCEPT)
                        
                    concept = self.modelXbrl.qnameConcepts.get(priItemQname)
                    conceptNotAbstract = concept is not None and not concept.isAbstract
                    from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                    value = None
                    objectId = None
                    justify = None
                    fp = FactPrototype(self, cellAspectValues)
                    if conceptNotAbstract:
                        for fact in self.modelXbrl.factsByQname[priItemQname] if priItemQname else self.modelXbrl.facts:
                            if (all(aspectMatches(rendrCntx, fact, fp, aspect) 
                                    for aspect in matchableAspects) and
                                all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                    for dim in cellDefaultedDims)):
                                if yOrdCntx.hasValueExpression(xOrdCntx):
                                    value = yOrdCntx.evalValueExpression(fact, xOrdCntx)
                                else:
                                    value = fact.effectiveValue
                                justify = "right" if fact.isNumeric else "left"
                                break
                    if conceptNotAbstract:
                        if value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp):
                            if self.type == HTML:
                                etree.SubElement(self.rowElts[row - 1], 
                                                 "{http://www.w3.org/1999/xhtml}td",
                                                 attrib={"class":"cell",
                                                         "style":"text-align:{0};width:8em".format(justify)}
                                                 ).text = value or "\u00A0"
                            elif self.type == XML:
                                if value is not None and fact is not None:
                                    self.xCells.append(etree.Comment("{0}: context {1}, file {2}, line {3}"
                                                                     .format(fact.qname,
                                                                             fact.contextID,
                                                                             fact.modelDocument.basename, 
                                                                             fact.sourceline)))

                                etree.SubElement(self.xCells, "{http://xbrl.org/2012/table/model}cell"
                                                 ).text = value
                        else:
                            if self.type == HTML:
                                etree.SubElement(self.rowElts[row - 1], 
                                                 "{http://www.w3.org/1999/xhtml}td",
                                                 attrib={"class":"blockedCell",
                                                         "style":"text-align:{0};width:8em".format(justify)}
                                                 ).text = "\u00A0\u00A0"
                            elif self.type == XML:
                                etree.SubElement(self.xCells, "{http://xbrl.org/2012/table/model}cell",
                                                 attrib={"blocked":"true"})
                    else: # concept is abstract
                        if self.type == HTML:
                            etree.SubElement(self.rowElts[row - 1], 
                                             "{http://www.w3.org/1999/xhtml}td",
                                             attrib={"class":"abstractCell",
                                                     "style":"text-align:{0};width:8em".format(justify)}
                                             ).text = "\u00A0\u00A0"
                        elif self.type == XML:
                            etree.SubElement(self.xCells, "{http://xbrl.org/2012/table/model}cell",
                                             attrib={"abstract":"true"})
                    fp.clear()  # dereference
                row += 1
            if not yChildrenFirst:
                row = self.bodyCells(row, yOrdCntx, xOrdCntxs, zAspects, yChildrenFirst)
        return row
            