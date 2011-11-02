'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from tkinter import Menu, constants
from arelle import ViewWinGrid, ModelObject, XbrlConst
from arelle.ViewUtilRenderedGrid import (setDefaults, getTblAxes, inheritedPrimaryItemQname,
                                         inheritedExplicitDims, dimContextElement,
                                         FactPrototype, ContextPrototype, DimValuePrototype)
from arelle.UiUtil import (gridBorder, gridSpacer, gridHdr, gridCell, gridCombobox, 
                     label, checkbox, 
                     TOPBORDER, LEFTBORDER, RIGHTBORDER, BOTTOMBORDER, CENTERCELL)
from collections import defaultdict
from itertools import repeat

def viewRenderedGrid(modelXbrl, tabWin, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, tabWin, lang)
    
    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions
    ValidateXbrlDimensions.loadDimensionDefaults(view)
    
    # context menu
    setDefaults(view)
    menu = view.contextMenu()
    optionsMenu = Menu(view.viewFrame, tearoff=0)
    view.ignoreDimValidity.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("Ignore Dimensional Validity"), underline=0, variable=view.ignoreDimValidity, onvalue=True, offvalue=False)
    view.xAxisChildrenFirst.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("X-Axis Children First"), underline=0, variable=view.xAxisChildrenFirst, onvalue=True, offvalue=False)
    view.yAxisChildrenFirst.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("Y-Axis Children First"), underline=0, variable=view.yAxisChildrenFirst, onvalue=True, offvalue=False)
    menu.add_cascade(label=_("Options"), menu=optionsMenu, underline=0)
    view.tablesMenu = Menu(view.viewFrame, tearoff=0)
    menu.add_cascade(label=_("Tables"), menu=view.tablesMenu, underline=0)
    view.tablesMenuLength = 0
    view.menuAddLangs()
    view.menu.add_command(label=_("Save html file"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(view=view))
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.viewFrame.bind("<Enter>", view.cellEnter, '+')
    view.viewFrame.bind("<Leave>", view.cellLeave, '+')
            
class ViewRenderedGrid(ViewWinGrid.ViewGrid):
    def __init__(self, modelXbrl, tabWin, lang):
        super().__init__(modelXbrl, tabWin, "Rendering", True, lang)
        self.dimsContextElement = {}
        self.hcDimRelSet = self.modelXbrl.relationshipSet("XBRL-dimensions")
        self.zComboBoxIndex = None
        
    def loadTablesMenu(self):
        tblMenuEntries = {}             
        tblRelSet = self.modelXbrl.relationshipSet("Table-rendering")
        for tblLinkroleUri in tblRelSet.linkRoleUris:
            for tableAxisArcrole in (XbrlConst.euTableAxis, XbrlConst.tableAxis):
                tblAxisRelSet = self.modelXbrl.relationshipSet(tableAxisArcrole, tblLinkroleUri)
                if tblAxisRelSet and len(tblAxisRelSet.modelRelationships) > 0:
                    # table name
                    modelRoleTypes = self.modelXbrl.roleTypes.get(tblLinkroleUri)
                    if modelRoleTypes is not None and len(modelRoleTypes) > 0:
                        roledefinition = modelRoleTypes[0].definition
                        if roledefinition is None or roledefinition == "":
                            roledefinition = os.path.basename(tblLinkroleUri)       
                        for table in tblAxisRelSet.rootConcepts:
                            # add table to menu if there's any entry
                            tblMenuEntries[roledefinition] = tblLinkroleUri
                            break
        self.tablesMenu.delete(0, self.tablesMenuLength)
        self.tablesMenuLength = 0
        for tblMenuEntry in sorted(tblMenuEntries.items()):
            tbl,elr = tblMenuEntry
            self.tablesMenu.add_command(label=tbl, command=lambda e=elr: self.view(viewTblELR=e))
            self.tablesMenuLength += 1
            if not hasattr(self,"tblELR") or self.tblELR is None: 
                self.tblELR = elr # start viewing first ELR
        
    def viewReloadDueToMenuAction(self, *args):
        self.view()
        
    def view(self, viewTblELR=None):
        if viewTblELR:  # specific table selection
            self.tblELR = viewTblELR
        else:   # first or subsequenct reloading (language, dimensions, other change)
            self.loadTablesMenu()  # load menus (and initialize if first time
            viewTblELR = self.tblELR

        # remove old widgets
        self.viewFrame.clearGrid()

        tblAxisRelSet, xAxisObj, yAxisObj, zAxisObjs = getTblAxes(self, viewTblELR) 
        if self.zComboBoxIndex is None:
            self.zComboBoxIndex = list(repeat(0, len(zAxisObjs))) # start with 0 indices
            self.zFilterIndex = list(repeat(0, len(zAxisObjs)))
        
        if tblAxisRelSet:
            
            gridHdr(self.gridTblHdr, 0, 0, 
                    self.roledefinition, 
                    anchor="nw",
                    #columnspan=(self.dataFirstCol - 1),
                    #rowspan=(self.dataFirstRow),
                    wraplength=200) # in screen units
            zFilters = []
            for i, zAxisObj in enumerate(zAxisObjs):
                self.zAxis(1 + i, zAxisObj, zFilters)
            xFilters = []
            self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                       xAxisObj, xFilters, self.xAxisChildrenFirst.get(), True, True)
            self.yAxis(1, self.dataFirstRow,
                       yAxisObj, self.yAxisChildrenFirst.get(), True, True)
            self.factPrototypes = []
            self.bodyCells(self.dataFirstRow, yAxisObj, xFilters, zFilters, self.yAxisChildrenFirst.get())
                
            # data cells
                
        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))

            
    def zAxis(self, row, zAxisObj, zFilters):
        priorZfilter = len(zFilters)
        
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(zAxisObj):
            zAxisObj = axisMbrRel.toModelObject
            zFilters.append((inheritedPrimaryItemQname(self, zAxisObj),
                             inheritedExplicitDims(self, zAxisObj),
                             zAxisObj.genLabel(lang=self.lang),
                             zAxisObj.objectId()))
            self.zAxis(None, zAxisObj, zFilters)
            
        if row is not None:
            nextZfilter = len(zFilters)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, TOPBORDER, columnspan=2)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, LEFTBORDER)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, RIGHTBORDER, columnspan=2)
            if nextZfilter > priorZfilter + 1:  # combo box, use header on zAxis
                label = axisMbrRel.fromModelObject.genLabel(lang=self.lang)
            else: # no combo box, use label on coord
                label = zAxisObj.genLabel(lang=self.lang)
            hdr = gridHdr(self.gridColHdr, self.dataFirstCol, row,
                          label, 
                          anchor="w", columnspan=2,
                          wraplength=200, # in screen units
                          objectId=zAxisObj.objectId(),
                          onClick=self.onClick)
            if nextZfilter > priorZfilter + 1:    # multiple choices, use combo box
                zIndex = row - 1
                selectIndex = self.zComboBoxIndex[zIndex]
                combobox = gridCombobox(
                             self.gridColHdr, self.dataFirstCol + 2, row,
                             values=[zFilter[2] for zFilter in zFilters[priorZfilter:nextZfilter]],
                             selectindex=selectIndex,
                             columnspan=2,
                             comboboxselected=self.comboBoxSelected)
                combobox.zIndex = zIndex
                zFilterIndex = priorZfilter + selectIndex
                self.zFilterIndex[zIndex] = zFilterIndex
                combobox.objectId = hdr.objectId = zFilters[zFilterIndex][3]
                gridBorder(self.gridColHdr, self.dataFirstCol + 3, row, RIGHTBORDER)
                row += 1

        if not zFilters:
            zFilters.append( (None,set()) )  # allow empty set operations
        
    def comboBoxSelected(self, *args):
        combobox = args[0].widget
        self.zComboBoxIndex[combobox.zIndex] = combobox.valueIndex
        self.view() # redraw grid
            
    def xAxis(self, leftCol, topRow, rowBelow, xAxisParentObj, xFilters, childrenFirst, renderNow, atTop):
        parentRow = rowBelow
        noDescendants = True
        rightCol = leftCol
        widthToSpanParent = 0
        sideBorder = not xFilters
        if atTop and sideBorder and childrenFirst:
            gridBorder(self.gridColHdr, self.dataFirstCol, 1, LEFTBORDER, rowspan=self.dataFirstRow)
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
                width += 100 # width for this label, in screen units
            widthToSpanParent += width
            label = xAxisHdrObj.genLabel(lang=self.lang)
            if childrenFirst:
                thisCol = rightCol
                sideBorder = RIGHTBORDER
            else:
                thisCol = leftCol
                sideBorder = LEFTBORDER
            if renderNow:
                columnspan = (rightCol - leftCol + (1 if nonAbstract else 0))
                gridBorder(self.gridColHdr, leftCol, topRow, TOPBORDER, columnspan=columnspan)
                gridBorder(self.gridColHdr, leftCol, topRow, 
                           sideBorder, columnspan=columnspan,
                           rowspan=(rowBelow - topRow + 1) )
                gridHdr(self.gridColHdr, leftCol, topRow, 
                        label if label else "         ", 
                        anchor="center",
                        columnspan=(rightCol - leftCol + (1 if nonAbstract else 0)),
                        rowspan=(row - topRow + 1) if leafNode else 1,
                        wraplength=width, # screen units
                        objectId=xAxisHdrObj.objectId(),
                        onClick=self.onClick)
                if nonAbstract:
                    if self.colHdrDocRow:
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, TOPBORDER)
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, sideBorder)
                        gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, 
                                xAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                       lang=self.lang), 
                                anchor="center",
                                wraplength=100, # screen units
                                objectId=xAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    if self.colHdrCodeRow:
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, TOPBORDER)
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, sideBorder)
                        gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1, 
                                xAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                                anchor="center",
                                wraplength=100, # screen units
                                objectId=xAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, BOTTOMBORDER)
                    xFilters.append((inheritedPrimaryItemQname(self, xAxisHdrObj),
                                     inheritedExplicitDims(self, xAxisHdrObj)))
            if nonAbstract:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xAxisHdrObj, xFilters, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        if atTop and sideBorder and not childrenFirst:
            gridBorder(self.gridColHdr, rightCol - 1, 1, RIGHTBORDER, rowspan=self.dataFirstRow)
        return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, leftCol, row, yAxisParentObj, childrenFirst, renderNow, atLeft):
        nestedBottomRow = row
        if atLeft:
            gridBorder(self.gridRowHdr, self.rowHdrCols + self.rowHdrDocCol + self.rowHdrCodeCol, 
                       self.dataFirstRow, 
                       RIGHTBORDER, 
                       rowspan=self.dataRows)
            gridBorder(self.gridRowHdr, 1, self.dataFirstRow + self.dataRows - 1, 
                       BOTTOMBORDER, 
                       columnspan=(self.rowHdrCols + self.rowHdrDocCol + self.rowHdrCodeCol))
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            nestRow, nextRow = self.yAxis(leftCol + 1, row, yAxisHdrObj,  # nested items before totals
                                    childrenFirst, childrenFirst, False)
            
            isNonAbstract = yAxisHdrObj.abstract == "false"
            isAbstract = not isNonAbstract
            label = yAxisHdrObj.genLabel(lang=self.lang)
            topRow = row
            if childrenFirst and isNonAbstract:
                row = nextRow
            if renderNow:
                columnspan = self.rowHdrCols - leftCol + 1 if isNonAbstract or nextRow == row else None
                gridBorder(self.gridRowHdr, leftCol, topRow, LEFTBORDER, 
                           rowspan=(nestRow - topRow + 1) )
                gridBorder(self.gridRowHdr, leftCol, topRow, TOPBORDER, 
                           columnspan=(1 if childrenFirst and nextRow > row else columnspan))
                if childrenFirst and row > topRow:
                    gridBorder(self.gridRowHdr, leftCol + 1, row, TOPBORDER, 
                               columnspan=(self.rowHdrCols - leftCol))
                gridHdr(self.gridRowHdr, leftCol, row, 
                        label if label else "         ", 
                        anchor=("w" if isNonAbstract or nestRow == row else "center"),
                        columnspan=columnspan,
                        rowspan=(nestRow - row if isAbstract else None),
                        # wraplength is in screen units
                        wraplength=(self.rowHdrColWidth[leftCol] if isAbstract else
                                    self.rowHdrWrapLength -
                                      sum(self.rowHdrColWidth[i] for i in range(leftCol))),
                        minwidth=(16 if isNonAbstract and nextRow > topRow else None),
                        objectId=yAxisHdrObj.objectId(),
                        onClick=self.onClick)
                if isNonAbstract:
                    if self.rowHdrDocCol:
                        docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                        gridBorder(self.gridRowHdr, docCol, row, TOPBORDER)
                        gridBorder(self.gridRowHdr, docCol, row, LEFTBORDER)
                        gridHdr(self.gridRowHdr, docCol, row, 
                                yAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                     lang=self.lang), 
                                anchor="w",
                                wraplength=100, # screen units
                                objectId=yAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    if self.rowHdrCodeCol:
                        codeCol = self.dataFirstCol - 1
                        gridBorder(self.gridRowHdr, codeCol, row, TOPBORDER)
                        gridBorder(self.gridRowHdr, codeCol, row, LEFTBORDER)
                        gridHdr(self.gridRowHdr, codeCol, row, 
                                yAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                                anchor="center",
                                wraplength=40, # screen units
                                objectId=yAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    # gridBorder(self.gridRowHdr, leftCol, self.dataFirstRow - 1, BOTTOMBORDER)
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
                    
                gridSpacer(self.gridBody, self.dataFirstCol, row, LEFTBORDER)
                # data for columns of row
                ignoreDimValidity = self.ignoreDimValidity.get()
                zPriItemQname = None
                zDims = set()
                for zIndex in self.zFilterIndex:
                    zFilter = zFilters[zIndex]
                    if zFilter[0]: zPriItemQname = zFilter[0] # inherit pri item
                    zDims |= zFilter[1] # or in z-dims
                for i, colFilter in enumerate(xFilters):
                    colPriItemQname = colFilter[0] # y axis pri item
                    if not colPriItemQname: colPriItemQname = yAxisPriItemQname # y axis
                    if not colPriItemQname: colPriItemQname = zPriItemQname # z axis
                    fp = FactPrototype(self,
                                       colPriItemQname,
                                       yAxisExplicitDims | colFilter[1] | zDims)
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
                        if objectId is None:
                            objectId = "f{0}".format(len(self.factPrototypes))
                            self.factPrototypes.append(fp)  # for property views
                        gridCell(self.gridBody, self.dataFirstCol + i, row, value, justify=justify, 
                                 width=12, # width is in characters, not screen units
                                 objectId=objectId, onClick=self.onClick)
                    else:
                        gridSpacer(self.gridBody, self.dataFirstCol + i, row, CENTERCELL)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, RIGHTBORDER)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, BOTTOMBORDER)
                row += 1
            if not yChildrenFirst:
                row = self.bodyCells(row, yAxisHdrObj, xFilters, zFilters, yChildrenFirst)
        return row
    def onClick(self, event):
        objId = event.widget.objectId
        if objId and objId[0] == "f":
            viewableObject = self.factPrototypes[int(objId[1:])]
        else:
            viewableObject = objId
        self.modelXbrl.viewModelObject(viewableObject)
            
    def cellEnter(self, *args):
        self.blockSelectEvent = 0

    def cellLeave(self, *args):
        self.blockSelectEvent = 1

    def cellSelect(self, *args):
        if self.blockSelectEvent == 0 and self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            #self.modelXbrl.viewModelObject(self.nodeToObjectId[self.treeView.selection()[0]])
            #self.modelXbrl.viewModelObject(self.treeView.selection()[0])
            self.blockViewModelObject -= 1
        
    def viewModelObject(self, modelObject):
        if self.blockViewModelObject == 0:
            self.blockViewModelObject += 1
            '''
            try:
                if isinstance(modelObject, ModelObject.ModelRelationship):
                    conceptId = modelObject.toModelObject.objectId()
                elif isinstance(modelObject, ModelObject.ModelFact):
                    conceptId = self.modelXbrl.qnameConcepts[modelObject.qname].objectId()
                else:
                    conceptId = modelObject.objectId()
                #node = self.objectIdToNode[conceptId]
                node = conceptId
                if self.treeView.exists(node):
                    self.treeView.see(node)
                    self.treeView.selection_set(node)
            except KeyError:
                    self.treeView.selection_set(())
            '''
            self.blockViewModelObject -= 1
            
            