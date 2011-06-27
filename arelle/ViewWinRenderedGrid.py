'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from tkinter import Menu, constants, BooleanVar
from arelle import (ViewWinGrid, ModelObject, XbrlConst)
from arelle.UiUtil import (gridBorder, gridSpacer, gridHdr, gridCell, gridCombobox, 
                     label, checkbox, 
                     TOPBORDER, LEFTBORDER, RIGHTBORDER, BOTTOMBORDER, CENTERCELL)
from collections import defaultdict

def viewRenderedGrid(modelXbrl, tabWin, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, tabWin, lang)
    
    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions
    ValidateXbrlDimensions.loadDimensionDefaults(view)
    
    # context menu
    menu = view.contextMenu()
    optionsMenu = Menu(view.viewFrame, tearoff=0)
    view.ignoreDimValidity = BooleanVar(value=True)
    view.ignoreDimValidity.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("Ignore Dimensional Validity"), underline=0, variable=view.ignoreDimValidity, onvalue=True, offvalue=False)
    view.xAxisChildrenFirst = BooleanVar(value=True)
    view.xAxisChildrenFirst.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("X-Axis Children First"), underline=0, variable=view.xAxisChildrenFirst, onvalue=True, offvalue=False)
    view.yAxisChildrenFirst = BooleanVar(value=False)
    view.yAxisChildrenFirst.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("Y-Axis Children First"), underline=0, variable=view.yAxisChildrenFirst, onvalue=True, offvalue=False)
    menu.add_cascade(label=_("Options"), menu=optionsMenu, underline=0)
    view.tablesMenu = Menu(view.viewFrame, tearoff=0)
    menu.add_cascade(label=_("Tables"), menu=view.tablesMenu, underline=0)
    view.tablesMenuLength = 0
    view.menuAddLangs()
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
        self.zFilterIndex = 0
        
    @property
    def dimensionDefaults(self):
        return self.modelXbrl.qnameDimensionDefaults
    
    def loadTablesMenu(self):
        tblMenuEntries = {}             
        tblRelSet = self.modelXbrl.relationshipSet("EU-rendering")
        for tblLinkroleUri in tblRelSet.linkRoleUris:
            tblAxisRelSet = self.modelXbrl.relationshipSet(XbrlConst.euTableAxis, tblLinkroleUri)
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

        tblAxisRelSet = self.modelXbrl.relationshipSet(XbrlConst.euTableAxis, viewTblELR)
        self.axisMbrRelSet = self.modelXbrl.relationshipSet(XbrlConst.euAxisMember, viewTblELR)
        if tblAxisRelSet is None or len(tblAxisRelSet.modelRelationships) == 0:
            self.modelXbrl.modelManager.addToLog(_("no table relationships for {0}").format(self.arcrole))
            return False
        # remove old widgets
        self.viewFrame.clearGrid()

        # table name
        modelRoleTypes = self.modelXbrl.roleTypes.get(viewTblELR)
        if modelRoleTypes is not None and len(modelRoleTypes) > 0:
            roledefinition = modelRoleTypes[0].definition
            if roledefinition is None or roledefinition == "":
                roledefinition = os.path.basename(viewTblELR)       
        for table in tblAxisRelSet.rootConcepts:            
            self.dataCols = 0
            self.dataRows = 0
            self.colHdrDocRow = False
            self.colHdrCodeRow = False
            self.colHdrRows = 0
            self.dataRows = 0
            self.rowHdrMaxIndent = 0
            self.rowHdrDocRow = False
            self.rowHdrCodeRow = False
            self.zAxisRows = 0
            
            xAxisObj = yAxisObj = zAxisObj = None
            for tblAxisRel in tblAxisRelSet.fromModelObject(table):
                axisType = tblAxisRel.get("axisType")
                axisObj = tblAxisRel.toModelObject
                if axisType == "xAxis": xAxisObj = axisObj
                elif axisType == "yAxis": yAxisObj = axisObj
                elif axisType == "zAxis": zAxisObj = axisObj
                self.analyzeHdrs(axisObj, 1, axisType)
            self.colHdrTopRow = self.zAxisRows + (2 if self.zAxisRows else 1)
            self.dataFirstRow = self.colHdrTopRow + self.colHdrRows + self.colHdrDocRow + self.colHdrCodeRow
            self.dataFirstCol = 2 + self.rowHdrDocRow + self.rowHdrCodeRow
            #for i in range(self.dataFirstRow + self.dataRows):
            #    self.gridView.rowconfigure(i)
            #for i in range(self.dataFirstCol + self.dataCols):
            #    self.gridView.columnconfigure(i)
            
            gridHdr(self.gridTblHdr, 0, 0, 
                    roledefinition, 
                    anchor="nw",
                    #columnspan=(self.dataFirstCol - 1),
                    #rowspan=(self.dataFirstRow),
                    wraplength=200)
            zFilters = []
            self.zAxis(1, zAxisObj, zFilters)
            xFilters = []
            self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                       xAxisObj, xFilters, self.xAxisChildrenFirst.get(), True, True)
            self.yAxis(self.dataFirstRow, 0, yAxisObj, True, self.yAxisChildrenFirst.get())
            self.bodyCells(self.dataFirstRow, 0, yAxisObj, xFilters, zFilters, self.yAxisChildrenFirst.get())
                
            # data cells
                
        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))

                
    def analyzeHdrs(self, axisModelObj, depth, axisType):
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(axisModelObj):
            axisMbrModelObject = axisMbrRel.toModelObject
            if axisType == "zAxis":
                self.zAxisRows += 1 
                
                continue # no recursion
            elif axisType == "xAxis":
                self.dataCols += 1
                if depth > self.colHdrRows: self.colHdrRows = depth 
                if not self.colHdrDocRow:
                    if axisMbrModelObject.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                   lang=self.lang): 
                        self.colHdrDocRow = True
                if not self.colHdrCodeRow:
                    if axisMbrModelObject.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                        self.colHdrCodeRow = True
            elif axisType == "yAxis":
                self.dataRows += 1
                if depth > self.rowHdrMaxIndent: self.rowHdrMaxIndent = depth
                if not self.rowHdrDocRow:
                    if axisMbrModelObject.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                   lang=self.lang): 
                        self.rowHdrDocRow = True
                if not self.rowHdrCodeRow:
                    if axisMbrModelObject.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"): 
                        self.rowHdrCodeRow = True
            self.analyzeHdrs(axisMbrModelObject, depth+1, axisType) #recurse
            
    def zAxis(self, row, zAxisObj, zFilters):
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(zAxisObj):
            zAxisObj = axisMbrRel.toModelObject
            zFilters.append((self.inheritedPrimaryItemQname(zAxisObj),
                             self.inheritedExplicitDims(zAxisObj),
                             zAxisObj.genLabel(lang=self.lang)))
            priorZfilter = len(zFilters)
            self.zAxis(None, zAxisObj, zFilters)
            if row is not None:
                gridBorder(self.gridColHdr, self.dataFirstCol, row, TOPBORDER, columnspan=2)
                gridBorder(self.gridColHdr, self.dataFirstCol, row, LEFTBORDER)
                gridBorder(self.gridColHdr, self.dataFirstCol, row, RIGHTBORDER, columnspan=2)
                gridHdr(self.gridColHdr, self.dataFirstCol, row,
                        zAxisObj.genLabel(lang=self.lang), 
                        anchor="w", columnspan=2,
                        wraplength=200,
                        objectId=zAxisObj.objectId(),
                        onClick=self.onClick)
                nextZfilter = len(zFilters)
                if nextZfilter > priorZfilter:    # no combo box choices nested
                    self.combobox = gridCombobox(
                                 self.gridColHdr, self.dataFirstCol + 2, row,
                                 values=[zFilter[2] for zFilter in zFilters[priorZfilter:nextZfilter]],
                                 selectindex=self.zFilterIndex,
                                 comboboxselected=self.comboBoxSelected)
                    gridBorder(self.gridColHdr, self.dataFirstCol + 2, row, RIGHTBORDER)
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
                width += 100 # width for this label
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
                        wraplength=width,
                        objectId=xAxisHdrObj.objectId(),
                        onClick=self.onClick)
                if nonAbstract:
                    if self.colHdrDocRow:
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeRow, TOPBORDER)
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeRow, sideBorder)
                        gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeRow, 
                                xAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                       lang=self.lang), 
                                anchor="center",
                                wraplength=100,
                                objectId=xAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    if self.colHdrCodeRow:
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, TOPBORDER)
                        gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, sideBorder)
                        gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1, 
                                xAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                                anchor="w",
                                wraplength=100,
                                objectId=xAxisHdrObj.objectId(),
                                onClick=self.onClick)
                    gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, BOTTOMBORDER)
                    xFilters.append((self.inheritedPrimaryItemQname(xAxisHdrObj),
                                     self.inheritedExplicitDims(xAxisHdrObj)))
            if nonAbstract:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xAxisHdrObj, xFilters, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        if atTop and sideBorder and not childrenFirst:
            gridBorder(self.gridColHdr, rightCol - 1, 1, RIGHTBORDER, rowspan=self.dataFirstRow)
        return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, row, indent, yAxisParentObj, atLeft, childrenFirst):
        col = 0
        isEntirelyAbstract = True
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            if yAxisHdrObj.abstract == "false":
                isEntirelyAbstract= False
                break
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            if childrenFirst:
                row = self.yAxis(row, 
                                 indent + (0 if isEntirelyAbstract else 20), 
                                 yAxisHdrObj, atLeft and col == 0, 
                                 childrenFirst)
            if yAxisHdrObj.abstract == "false":
                gridBorder(self.gridRowHdr, 1, row, TOPBORDER)
                gridBorder(self.gridRowHdr, 1, row, LEFTBORDER)
                gridHdr(self.gridRowHdr, 1, row, 
                        yAxisHdrObj.genLabel(lang=self.lang), 
                        anchor="w",
                        padding=(indent,0,0,0) if indent is not None else None,
                        wraplength=200,
                        objectId=yAxisHdrObj.objectId(),
                        onClick=self.onClick)
                col = 2
                if self.rowHdrDocRow:
                    gridBorder(self.gridRowHdr, col, row, TOPBORDER)
                    gridBorder(self.gridRowHdr, col, row, LEFTBORDER)
                    gridHdr(self.gridRowHdr, col, row, 
                            yAxisHdrObj.genLabel(role="http://www.xbrl.org/2008/role/documentation",
                                                   lang=self.lang), 
                            anchor="w",
                            wraplength=100,
                            objectId=yAxisHdrObj.objectId(),
                            onClick=self.onClick)
                    col += 1
                if self.rowHdrCodeRow:
                    gridBorder(self.gridRowHdr, col, row, TOPBORDER)
                    gridBorder(self.gridRowHdr, col, row, LEFTBORDER)
                    gridHdr(self.gridRowHdr, col, row, 
                            yAxisHdrObj.genLabel(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                            anchor="w",
                            wraplength=40,
                            objectId=yAxisHdrObj.objectId(),
                            onClick=self.onClick)
                    col += 1
                gridBorder(self.gridRowHdr, col - 1, row, RIGHTBORDER)
                row += 1
            if not childrenFirst:
                row = self.yAxis(row, 
                                 indent + (0 if isEntirelyAbstract else 20), 
                                 yAxisHdrObj, atLeft and col == 0, 
                                 childrenFirst)
        if atLeft and col > 0:
            gridBorder(self.gridRowHdr, 1, row, BOTTOMBORDER, columnspan=col)
        return row
    
    def bodyCells(self, row, indent, yAxisParentObj, xFilters, zFilters, yChildrenFirst):
        for axisMbrRel in self.axisMbrRelSet.fromModelObject(yAxisParentObj):
            yAxisHdrObj = axisMbrRel.toModelObject
            if yChildrenFirst:
                row = self.bodyCells(row, indent + 20, yAxisHdrObj, xFilters, zFilters, yChildrenFirst)
            if yAxisHdrObj.abstract == "false":
                yAxisPriItemQname = self.inheritedPrimaryItemQname(yAxisHdrObj)
                yAxisExplicitDims = self.inheritedExplicitDims(yAxisHdrObj)
                    
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
                        if (fact.qname == fp.qname and
                            all(fact.context.dimMemberQname(dim,includeDefaults=True) == mem 
                                for dim, mem in fp.dims)):
                                value = fact.effectiveValue
                                objectId = fact.objectId()
                                justify = "right" if fact.isNumeric else "left"
                                break
                    if value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp):
                        gridCell(self.gridBody, self.dataFirstCol + i, row, value, justify=justify, width=12,
                                 objectId=objectId, onClick=self.onClick)
                    else:
                        gridSpacer(self.gridBody, self.dataFirstCol + i, row, CENTERCELL)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, RIGHTBORDER)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, BOTTOMBORDER)
                row += 1
            if not yChildrenFirst:
                row = self.bodyCells(row, indent + 20, yAxisHdrObj, xFilters, zFilters, yChildrenFirst)
        return row
    
    def inheritedPrimaryItemQname(self, axisMbrObj):
        primaryItemQname = axisMbrObj.primaryItemQname
        if primaryItemQname:
            return primaryItemQname
        for axisMbrRel in self.axisMbrRelSet.toModelObject(axisMbrObj):
            primaryItemQname = self.inheritedPrimaryItemQname(axisMbrRel.fromModelObject)
            if primaryItemQname:
                return primaryItemQname
        return None
            
    def inheritedExplicitDims(self, axisMbrObj, dims=None):
        if dims is None: dims = {}
        for axisMbrRel in self.axisMbrRelSet.toModelObject(axisMbrObj):
            self.inheritedExplicitDims(axisMbrRel.fromModelObject, dims=dims)
        for dim, mem in axisMbrObj.explicitDims:
            dims[dim] = mem
        return dims.items()
    
    def onClick(self, event):
        self.modelXbrl.viewModelObject(event.widget.objectId)
            
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
            
    def dimContextElement(self, dimConcept):
        try:
            return self.dimsContextElement[dimConcept]
        except KeyError:
            if self.hcDimRelSet:
                for dimHcRel in self.hcDimRelSet.toModelObject(dimConcept):
                    if dimHcRel.fromModelObject is not None:
                        for hcRel in self.hcDimRelSet.toModelObject(dimHcRel.fromModelObject):
                            contextElement = hcRel.contextElement
                            self.dimsContextElement[dimConcept] = contextElement
                            return contextElement
            return None
            

class FactPrototype():      # behaves like a fact for dimensional validity testing
    def __init__(self, v, qname, dims):
        self.qname = qname
        self.concept = v.modelXbrl.qnameConcepts.get(qname)
        self.context = ContextPrototype(v, dims)
        self.dims = dims

class ContextPrototype():  # behaves like a context
    def __init__(self, v, dims):
        self.segDimVals = {}
        self.scenDimVals = {}
        for dimQname,mem in dims:
            if v.modelXbrl.qnameDimensionDefaults.get(dimQname) != mem: # not a default
                try:
                    dimConcept = v.modelXbrl.qnameConcepts[dimQname]
                    dimValPrototype = DimValuePrototype(v, dimConcept, dimQname, mem)
                    if v.dimContextElement(dimConcept) == "segment":
                        self.segDimVals[dimConcept] = dimValPrototype
                    else:
                        self.scenDimVals[dimConcept] = dimValPrototype
                except KeyError:
                    pass
        
    def dimValues(self, contextElement):
        return self.segDimVals if contextElement == "segment" else self.scenDimVals
    
    def nonDimValues(self, contextElement):
        return []
    
class DimValuePrototype():
    def __init__(self, v, dimConcept, dimQname, mem):
        from arelle.ModelValue import QName
        self.dimension = dimConcept
        self.dimensionQname = dimQname
        if isinstance(mem,QName):
            self.isExplicit = True
            self.isTyped = False
            self.memberQname = mem
            self.member = v.modelXbrl.qnameConcepts[mem]

        else:
            self.isExplicit = False
            self.isTyped = True
            self.typedMember = mem
            