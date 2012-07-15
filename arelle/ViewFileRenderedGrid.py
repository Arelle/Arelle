'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewFile
from lxml import etree
from arelle.ViewUtilRenderedGrid import (setDefaults, getTblAxes, inheritedAspectValue)
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect
from arelle.FormulaEvaluator import aspectMatches
from arelle.PrototypeInstanceObject import FactPrototype
from collections import defaultdict

emptySet = set()
emptyList = []

def viewRenderedGrid(modelXbrl, outfile, lang=None, viewTblELR=None, sourceView=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, outfile, lang)
    
    setDefaults(view)
    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
        view.xAxisChildrenFirst.set(sourceView.xAxisChildrenFirst.get())
        view.yAxisChildrenFirst.set(sourceView.yAxisChildrenFirst.get())
    view.view(viewTblELR)    
    view.close()
    
class ViewRenderedGrid(ViewFile.View):
    def __init__(self, modelXbrl, outfile, lang):
        super(ViewRenderedGrid, self).__init__(modelXbrl, outfile, "Rendering", lang, style="rendering")
        self.zOrdinateChoices = {}
        
    def viewReloadDueToMenuAction(self, *args):
        self.view()
        
    def view(self, viewTblELR=None):
        if viewTblELR is None:
            tblRelSet = self.modelXbrl.relationshipSet("Table-rendering")
            for tblLinkroleUri in tblRelSet.linkRoleUris:
                viewTblELR = tblLinkroleUri # take first table
                break
        self.tblELR = viewTblELR

        tblAxisRelSet, xOrdCntx, yOrdCntx, zOrdCntx = getTblAxes(self, viewTblELR) 
        
        if tblAxisRelSet and self.tblElt is not None:
            self.rowElts = [etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
                            for r in range(self.dataFirstRow + self.dataRows - 1)]
            etree.SubElement(self.rowElts[0], "{http://www.w3.org/1999/xhtml}th",
                             attrib={"class":"tableHdr",
                                     "style":"max-width:100em;",
                                     "colspan": str(self.dataFirstCol - 1),
                                     "rowspan": str(self.dataFirstRow - 1)}
                             ).text = self.roledefinition
            zAspects = defaultdict(set)
            self.zAxis(1, zOrdCntx, zAspects, True)
            xOrdCntxs = []
            self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                       xOrdCntx, xOrdCntxs, self.xAxisChildrenFirst.get(), True, True)
            self.yAxis(1, self.dataFirstRow,
                       yOrdCntx, self.yAxisChildrenFirst.get(), True, True)
            self.bodyCells(self.dataFirstRow, yOrdCntx, xOrdCntxs, zAspects, self.yAxisChildrenFirst.get())

            
    def zAxis(self, row, zOrdCntx, zAspects, clearZchoices):
        if zOrdCntx is not None:
            label = zOrdCntx.header(lang=self.lang)
            choiceLabel = None
            if zOrdCntx.choiceOrdinateContexts: # same as combo box selection in GUI mode
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

            if zOrdCntx.subOrdinateContexts:
                for zOrdCntx in zOrdCntx.subOrdinateContexts:
                    self.zAxis(row + 1, zOrdCntx, zAspects, clearZchoices)
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
                columnspan = (rightCol - leftCol + (1 if nonAbstract else 0))
                if rightCol == self.dataFirstCol + self.dataCols - 1:
                    edgeBorder = "border-right:.5pt solid windowtext;"
                else:
                    edgeBorder = ""
                attrib = {"class":"xAxisHdr",
                          "style":"text-align:center;max-width:{0}pt;{1}".format(width,edgeBorder)}
                colspan = rightCol - leftCol + (1 if nonAbstract else 0)
                if colspan > 1:
                    attrib["colspan"] = str(colspan)
                if leafNode and row > topRow:
                    attrib["rowspan"] = str(row - topRow + 1)
                elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                    attrib=attrib)
                elt.text = label if label else "\u00A0" #produces &nbsp;
                self.rowElts[topRow-1].insert(leftCol,elt)
                if nonAbstract:
                    if colspan > 1 and rowBelow > topRow:   # add spanned left leg portion one row down
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
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib={"class":"xAxisHdr",
                                                    "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                        elt.text = doc if doc else "\u00A0"
                        self.rowElts[self.dataFirstRow - 2 - self.rowHdrCodeCol].insert(thisCol,elt)
                    if self.colHdrCodeRow:
                        code = xOrdCntx.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib={"class":"xAxisHdr",
                                                    "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                        self.rowElts[self.dataFirstRow - 2].insert(thisCol,elt)
                        elt.text = code if code else "\u00A0"
                    xOrdCntxs.append(xOrdCntx)
            if nonAbstract:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xOrdCntx, xOrdCntxs, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, leftCol, row, yParentOrdCntx, childrenFirst, renderNow, atLeft):
        nestedBottomRow = row
        for yOrdCntx in yParentOrdCntx.subOrdinateContexts:
            nestRow, nextRow = self.yAxis(leftCol + 1, row, yOrdCntx,  # nested items before totals
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
                                         ).text = doc if doc else "\u00A0"
                    if self.rowHdrCodeCol:
                        codeCol = self.dataFirstCol - 1
                        code = yOrdCntx.header(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        etree.SubElement(self.rowElts[hdrRow - 1], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:center;max-width:40pt;{0}".format(edgeBorder)}
                                         ).text = code if code else "\u00A0"
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
                dummy, row = self.yAxis(leftCol + 1, row, yOrdCntx, childrenFirst, renderNow, False) # render on this pass
        return (nestedBottomRow, row)

    
    def bodyCells(self, row, yParentOrdCntx, xOrdCntxs, zAspects, yChildrenFirst):
        dimDefaults = self.modelXbrl.qnameDimensionDefaults
        for yOrdCntx in yParentOrdCntx.subOrdinateContexts:
            if yChildrenFirst:
                row = self.bodyCells(row, yOrdCntx, xOrdCntxs, zAspects, yChildrenFirst)
            if not yOrdCntx.isAbstract:
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
                        aspectValue = inheritedAspectValue(self, aspect, xAspects, yAspects, zAspects)
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
                            if (all(aspectMatches(None, fact, fp, aspect) 
                                    for aspect in matchableAspects) and
                                all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                    for dim in cellDefaultedDims)):
                                value = fact.effectiveValue
                                justify = "right" if fact.isNumeric else "left"
                                break
                    if (conceptNotAbstract and
                        (value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp))):
                        etree.SubElement(self.rowElts[row - 1], 
                                         "{http://www.w3.org/1999/xhtml}td",
                                         attrib={"class":"cell",
                                                 "style":"text-align:{0};width:8em".format(justify)}
                                         ).text = value if value else "\u00A0"
                    else:
                        etree.SubElement(self.rowElts[row - 1], 
                                         "{http://www.w3.org/1999/xhtml}td",
                                         attrib={"class":"blockedCell",
                                                 "style":"text-align:{0};width:8em".format(justify)}
                                         ).text = "\u00A0\u00A0"
                    fp.clear()  # dereference
                row += 1
            if not yChildrenFirst:
                row = self.bodyCells(row, yOrdCntx, xOrdCntxs, zAspects, yChildrenFirst)
        return row
         
            