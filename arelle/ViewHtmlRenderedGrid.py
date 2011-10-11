'''
Created on Sep 13, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import ViewHtml, XbrlConst
from lxml import etree
from arelle.ViewUtilRenderedGrid import (setDefaults, getTblAxes, inheritedPrimaryItemQname,
                                         inheritedExplicitDims, dimContextElement,
                                         FactPrototype, ContextPrototype, DimValuePrototype)

def viewRenderedGrid(modelXbrl, htmlfile, lang=None, viewTblELR=None, sourceView=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, htmlfile, lang)
    
    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions
    ValidateXbrlDimensions.loadDimensionDefaults(view)
    setDefaults(view)
    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
        view.xAxisChildrenFirst.set(sourceView.xAxisChildrenFirst.get())
        view.yAxisChildrenFirst.set(sourceView.yAxisChildrenFirst.get())
    view.view(viewTblELR)    
    view.write()
    view.close()
    
class ViewRenderedGrid(ViewHtml.View):
    def __init__(self, modelXbrl, htmlfile, lang):
        super().__init__(modelXbrl, htmlfile, "Rendering", lang)
        self.dimsContextElement = {}
        self.hcDimRelSet = self.modelXbrl.relationshipSet("XBRL-dimensions")
        self.zFilterIndex = 0
        
    @property
    def dimensionDefaults(self):
        return self.modelXbrl.qnameDimensionDefaults
    
        
    def viewReloadDueToMenuAction(self, *args):
        self.view()
        
    def view(self, viewTblELR=None):
        if viewTblELR is None:
            tblRelSet = self.modelXbrl.relationshipSet("Table-rendering")
            for tblLinkroleUri in tblRelSet.linkRoleUris:
                viewTblELR = tblLinkroleUri # take first table
                break
        self.tblELR = viewTblELR

        tblAxisRelSet, xAxisObj, yAxisObj, zAxisObj = getTblAxes(self, viewTblELR) 
        
        self.tblElt = None
        for self.tblElt in self.htmlDoc.iter(tag="{http://www.w3.org/1999/xhtml}table"):
            break
        
        if tblAxisRelSet and self.tblElt is not None:
            self.rowElts = [etree.SubElement(self.tblElt, "{http://www.w3.org/1999/xhtml}tr")
                            for r in range(self.dataFirstRow + self.dataRows - 1)]
            etree.SubElement(self.rowElts[0], "{http://www.w3.org/1999/xhtml}th",
                             attrib={"class":"tableHdr",
                                     "style":"max-width:100em;",
                                     "colspan": str(self.dataFirstCol - 1),
                                     "rowspan": str(self.dataFirstRow - 1)}
                             ).text = self.roledefinition
            
            zFilters = []
            self.zAxis(1, zAxisObj, zFilters)
            xFilters = []
            self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                       xAxisObj, xFilters, self.xAxisChildrenFirst.get(), True, True)
            self.yAxis(1, self.dataFirstRow,
                       yAxisObj, self.yAxisChildrenFirst.get(), True, True)
            self.bodyCells(self.dataFirstRow, yAxisObj, xFilters, zFilters, self.yAxisChildrenFirst.get())
                
            # data cells
                
        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))

            
    def zAxis(self, row, zAxisObj, zFilters):
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(zAxisObj):
            zAxisObj = axisMbrRel.toModelObject
            zFilters.append((inheritedPrimaryItemQname(self, zAxisObj),
                             inheritedExplicitDims(self, zAxisObj),
                             zAxisObj.genLabel(lang=self.lang)))
            priorZfilter = len(zFilters)
            self.zAxis(None, zAxisObj, zFilters)
            if row is not None:
                etree.SubElement(self.rowElts[row-1], "{http://www.w3.org/1999/xhtml}th",
                                 attrib={"class":"zAxisHdr",
                                         "style":"max-width:200pt;text-align:left;border-bottom:.5pt solid windowtext",
                                         "colspan": str(self.dataCols)} # "2"}
                                 ).text = zAxisObj.genLabel(lang=self.lang)
                nextZfilter = len(zFilters)
                if nextZfilter > priorZfilter:    # no combo box choices nested
                    '''
                    self.combobox = gridCombobox(
                                 self.gridColHdr, self.dataFirstCol + 2, row,
                                 values=[zFilter[2] for zFilter in zFilters[priorZfilter:nextZfilter]],
                                 selectindex=self.zFilterIndex,
                                 comboboxselected=self.comboBoxSelected)
                    gridBorder(self.gridColHdr, self.dataFirstCol + 2, row, RIGHTBORDER)
                    '''
                    row += 1

        if not zFilters:
            zFilters.append( (None,set()) )  # allow empty set operations
        
    def comboBoxSelected(self, *args):
        self.zFilterIndex = self.combobox.valueIndex
        self.view() # redraw grid
            
    def xAxis(self, leftCol, topRow, rowBelow, xAxisParentObj, xFilters, childrenFirst, renderNow, atTop):
        parentRow = rowBelow
        noDescendants = True
        rightCol = leftCol
        widthToSpanParent = 0
        sideBorder = not xFilters
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(xAxisParentObj):
            noDescendants = False
            xAxisHdrObj = axisMbrRel.toModelObject
            rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xAxisHdrObj, xFilters, # nested items before totals
                                                        childrenFirst, childrenFirst, False)
            if row - 1 < parentRow:
                parentRow = row - 1
            #if not leafNode: 
            #    rightCol -= 1
            nonAbstract = xAxisHdrObj.abstract == "false"
            if nonAbstract:
                width += 100 # width for this label
            widthToSpanParent += width
            label = xAxisHdrObj.genLabel(lang=self.lang)
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
                elt.text = label if label else "&nbsp;"
                self.rowElts[topRow-1].insert(leftCol,elt)
                if nonAbstract:
                    if colspan > 1 and rowBelow > topRow:   # add spanned left leg portion one row down
                        attrib= {"class":"xAxisSpanLeg",
                                 "rowspan": str(rowBelow - row)}
                        if edgeBorder:
                            attrib["style"] = edgeBorder
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib=attrib)
                        elt.text = "&nbsp;"
                        if childrenFirst:
                            self.rowElts[topRow].append(elt)
                        else:
                            self.rowElts[topRow].insert(leftCol,elt)
                    if self.colHdrDocRow:
                        doc = xAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation", lang=self.lang)
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib={"class":"xAxisHdr",
                                                    "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                        elt.text = doc if doc else "&nbsp;"
                        self.rowElts[self.dataFirstRow - 2 - self.rowHdrCodeCol].insert(thisCol,elt)
                    if self.colHdrCodeRow:
                        code = xAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        elt = etree.Element("{http://www.w3.org/1999/xhtml}th",
                                            attrib={"class":"xAxisHdr",
                                                    "style":"text-align:center;max-width:100pt;{0}".format(edgeBorder)})
                        self.rowElts[self.dataFirstRow - 2].insert(thisCol,elt)
                        elt.text = code if code else "&nbsp;"
                    xFilters.append((inheritedPrimaryItemQname(self, xAxisHdrObj),
                                     inheritedExplicitDims(self, xAxisHdrObj)))
            if nonAbstract:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xAxisHdrObj, xFilters, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, leftCol, row, yAxisParentObj, childrenFirst, renderNow, atLeft):
        nestedBottomRow = row
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            nestRow, nextRow = self.yAxis(leftCol + 1, row, yAxisHdrObj,  # nested items before totals
                                    childrenFirst, childrenFirst, False)
            
            isNonAbstract = yAxisHdrObj.abstract == "false"
            isAbstract = not isNonAbstract
            label = yAxisHdrObj.genLabel(lang=self.lang)
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
                    elt.text = "&nbsp;"
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
                elt.text = label if label else "&nbsp;"
                if isNonAbstract:
                    self.rowElts[hdrRow-1].append(elt)
                    if not childrenFirst and nestRow > hdrRow:   # add spanned left leg portion one row down
                        etree.SubElement(self.rowElts[hdrRow], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":"yAxisSpanLeg",
                                                 "style":"text-align:center;max-width:16pt;{1}".format(edgeBorder),
                                                 "rowspan": str(nestRow - hdrRow)}
                                         ).text = "&nbsp;"
                    hdrClass = "yAxisHdr" if not childrenFirst else "yAxisHdrWithChildrenFirst"
                    if self.rowHdrDocCol:
                        docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                        doc = yAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation")
                        etree.SubElement(self.rowElts[hdrRow - 1], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:left;max-width:100pt;{0}".format(edgeBorder)}
                                         ).text = doc if doc else "&nbsp;"
                    if self.rowHdrCodeCol:
                        codeCol = self.dataFirstCol - 1
                        code = yAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code")
                        etree.SubElement(self.rowElts[hdrRow - 1], 
                                         "{http://www.w3.org/1999/xhtml}th",
                                         attrib={"class":hdrClass,
                                                 "style":"text-align:center;max-width:40pt;{0}".format(edgeBorder)}
                                         ).text = code if code else "&nbsp;"
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
                dummy, row = self.yAxis(leftCol + 1, row, yAxisHdrObj, childrenFirst, renderNow, False) # render on this pass
        return (nestedBottomRow, row)

    
    def bodyCells(self, row, yAxisParentObj, xFilters, zFilters, yChildrenFirst):
        dimDefaults = self.modelXbrl.qnameDimensionDefaults
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            if yChildrenFirst:
                row = self.bodyCells(row, yAxisHdrObj, xFilters, zFilters, yChildrenFirst)
            if yAxisHdrObj.abstract == "false":
                yAxisPriItemQname = inheritedPrimaryItemQname(self, yAxisHdrObj)
                yAxisExplicitDims = inheritedExplicitDims(self, yAxisHdrObj)
                    
                # data for columns of row
                ignoreDimValidity = self.ignoreDimValidity.get()
                zFilter = zFilters[self.zFilterIndex]
                for i, colFilter in enumerate(xFilters):
                    colPriItemQname = colFilter[0] # y axis pri item
                    if not colPriItemQname: colPriItemQname = yAxisPriItemQname # y axis
                    if not colPriItemQname: colPriItemQname = zFilter[0] # z axis
                    fp = FactPrototype(self,
                                       colPriItemQname,
                                       yAxisExplicitDims | colFilter[1] | zFilter[1])
                    from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                    value = None
                    objectId = None
                    justify = None
                    for fact in self.modelXbrl.facts:
                        if fact.qname == fp.qname:
                            factDimMem = fact.context.dimMemberQname
                            defaultedDims = dimDefaults.keys() - fp.dimKeys
                            if (all(factDimMem(dim,includeDefaults=True) == mem 
                                    for dim, mem in fp.dims) and
                                all(factDimMem(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                    for dim in defaultedDims)):
                                value = fact.effectiveValue
                                objectId = fact.objectId()
                                justify = "right" if fact.isNumeric else "left"
                                break
                    if value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp):
                        etree.SubElement(self.rowElts[row - 1], 
                                         "{http://www.w3.org/1999/xhtml}td",
                                         attrib={"class":"cell",
                                                 "style":"text-align:{0};width:8em".format(justify)}
                                         ).text = value if value else "&nbsp;"
                    else:
                        etree.SubElement(self.rowElts[row - 1], 
                                         "{http://www.w3.org/1999/xhtml}td",
                                         attrib={"class":"blockedCell",
                                                 "style":"text-align:{0};width:8em".format(justify)}
                                         ).text = "&nbsp;&nbsp;"
                row += 1
            if not yChildrenFirst:
                row = self.bodyCells(row, yAxisHdrObj, xFilters, zFilters, yChildrenFirst)
        return row
         
            