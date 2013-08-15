'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, threading, time
from tkinter import Menu, BooleanVar
from arelle import (ViewWinGrid, ModelDocument, ModelInstanceObject, XbrlConst, 
                    ModelXbrl, XmlValidate, Locale)
from arelle.ModelValue import qname, QName
from arelle.ViewUtilRenderedGrid import (resolveAxesStructure, inheritedAspectValue)
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectRuleAspects, aspectModelAspect
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelRenderingObject import ModelClosedDefinitionNode, ModelEuAxisCoord
from arelle.FormulaEvaluator import aspectMatches

from arelle.PrototypeInstanceObject import FactPrototype
from arelle.UiUtil import (gridBorder, gridSpacer, gridHdr, gridCell, gridCombobox, 
                           label,  
                           TOPBORDER, LEFTBORDER, RIGHTBORDER, BOTTOMBORDER, CENTERCELL)
from arelle.DialogNewFactItem import getNewFactItemOptions
from collections import defaultdict

emptyList = []

def viewRenderedGrid(modelXbrl, tabWin, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, tabWin, lang)
        
    view.blockMenuEvents = 1

    menu = view.contextMenu()
    optionsMenu = Menu(view.viewFrame, tearoff=0)
    optionsMenu.add_command(label=_("New fact item options"), underline=0, command=lambda: getNewFactItemOptions(modelXbrl.modelManager.cntlr, view.newFactItemOptions))
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
    saveMenu = Menu(view.viewFrame, tearoff=0)
    saveMenu.add_command(label=_("HTML file"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(view=view, fileType="html"))
    saveMenu.add_command(label=_("Table layout infoset"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(view=view, fileType="xml"))
    saveMenu.add_command(label=_("XBRL instance"), underline=0, command=view.saveInstance)
    menu.add_cascade(label=_("Save"), menu=saveMenu, underline=0)
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.viewFrame.bind("<Enter>", view.cellEnter, '+')
    view.viewFrame.bind("<Leave>", view.cellLeave, '+')
    view.viewFrame.bind("<1>", view.onClick, '+')
    view.blockMenuEvents = 0
            
class ViewRenderedGrid(ViewWinGrid.ViewGrid):
    def __init__(self, modelXbrl, tabWin, lang):
        super(ViewRenderedGrid, self).__init__(modelXbrl, tabWin, "Rendering", True, lang)
        self.newFactItemOptions = ModelInstanceObject.NewFactItemOptions(xbrlInstance=modelXbrl)
        self.factPrototypes = []
        self.zOrdinateChoices = None
        # context menu Boolean vars
        self.options = self.modelXbrl.modelManager.cntlr.config.setdefault("viewRenderedGridOptions", {})
        self.ignoreDimValidity = BooleanVar(value=self.options.setdefault("ignoreDimValidity",True))
        self.xAxisChildrenFirst = BooleanVar(value=self.options.setdefault("xAxisChildrenFirst",True))
        self.yAxisChildrenFirst = BooleanVar(value=self.options.setdefault("yAxisChildrenFirst",False))
            
    def close(self):
        super(ViewRenderedGrid, self).close()
        if self.modelXbrl:
            for fp in self.factPrototypes:
                fp.clear()
            self.factPrototypes = None
        
    def loadTablesMenu(self):
        tblMenuEntries = {}             
        tblRelSet = self.modelXbrl.relationshipSet("Table-rendering")
        for tblLinkroleUri in tblRelSet.linkRoleUris:
            for tableAxisArcrole in (XbrlConst.euTableAxis, XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD, XbrlConst.tableBreakdown201301, XbrlConst.tableAxis2011):
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
        self.tblELR = None
        for tblMenuEntry in sorted(tblMenuEntries.items()):
            tbl,elr = tblMenuEntry
            self.tablesMenu.add_command(label=tbl, command=lambda e=elr: self.view(viewTblELR=e))
            self.tablesMenuLength += 1
            if self.tblELR is None: 
                self.tblELR = elr # start viewing first ELR
        
    def viewReloadDueToMenuAction(self, *args):
        if not self.blockMenuEvents:
            # update config (config saved when exiting)
            self.options["ignoreDimValidity"] = self.ignoreDimValidity.get()
            self.options["xAxisChildrenFirst"] = self.xAxisChildrenFirst.get()
            self.options["yAxisChildrenFirst"] = self.yAxisChildrenFirst.get()
            self.view()
        
    def view(self, viewTblELR=None, newInstance=None):
        startedAt = time.time()
        self.blockMenuEvents += 1
        if newInstance is not None:
            self.modelXbrl = newInstance # a save operation has created a new instance to use subsequently
            clearZchoices = False
        if viewTblELR:  # specific table selection
            self.tblELR = viewTblELR
            clearZchoices = True
        else:   # first or subsequenct reloading (language, dimensions, other change)
            clearZchoices = self.zOrdinateChoices is None
            if clearZchoices: # also need first time initialization
                self.loadTablesMenu()  # load menus (and initialize if first time
            viewTblELR = self.tblELR
            
        if not self.tblELR:
            return  # no table to display

        if clearZchoices:
            self.zOrdinateChoices = {}

        # remove old widgets
        self.viewFrame.clearGrid()

        tblAxisRelSet, xTopStructuralNode, yTopStructuralNode, zTopStructuralNode = resolveAxesStructure(self, viewTblELR) 
        
        if tblAxisRelSet:
            #print("tbl hdr width rowHdrCols {0}".format(self.rowHdrColWidth))
            self.gridTblHdr.tblHdrWraplength = 200 # to  adjust dynamically during configure callbacks
            self.gridTblHdr.tblHdrLabel = \
                gridHdr(self.gridTblHdr, 0, 0, 
                        (self.modelTable.genLabel(lang=self.lang, strip=True) or  # use table label, if any 
                         self.roledefinition),
                        anchor="nw",
                        #columnspan=(self.dataFirstCol - 1),
                        #rowspan=(self.dataFirstRow),
                        wraplength=200) # in screen units
                        #wraplength=sum(self.rowHdrColWidth)) # in screen units
            zAspects = defaultdict(set)
            self.zAxis(1, zTopStructuralNode, zAspects, clearZchoices)
            xStructuralNodes = []
            self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                       xTopStructuralNode, xStructuralNodes, self.xAxisChildrenFirst.get(), True, True)
            self.yAxis(1, self.dataFirstRow,
                       yTopStructuralNode, self.yAxisChildrenFirst.get(), True, True)
            for fp in self.factPrototypes: # dereference prior facts
                if fp is not None:
                    fp.clear()
            self.factPrototypes = []
            self.bodyCells(self.dataFirstRow, yTopStructuralNode, xStructuralNodes, zAspects, self.yAxisChildrenFirst.get())
                
            # data cells
            #print("body cells done")
                
        self.modelXbrl.profileStat("viewTable_" + os.path.basename(viewTblELR), time.time() - startedAt)

        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))
        self.blockMenuEvents -= 1

            
    def zAxis(self, row, zStructuralNode, zAspects, clearZchoices):
        if zStructuralNode is not None:
            gridBorder(self.gridColHdr, self.dataFirstCol, row, TOPBORDER, columnspan=2)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, LEFTBORDER)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, RIGHTBORDER, columnspan=2)
            label = zStructuralNode.header(lang=self.lang)
            hdr = gridHdr(self.gridColHdr, self.dataFirstCol, row,
                          label, 
                          anchor="w", columnspan=2,
                          wraplength=200, # in screen units
                          objectId=zStructuralNode.objectId(),
                          onClick=self.onClick)
    
            if zStructuralNode.choiceStructuralNodes: # combo box
                valueHeaders = [''.ljust(zChoiceStructuralNode.indent * 4) + # indent if nested choices 
                                (zChoiceStructuralNode.header(lang=self.lang) or '')
                                for zChoiceStructuralNode in zStructuralNode.choiceStructuralNodes]
                combobox = gridCombobox(
                             self.gridColHdr, self.dataFirstCol + 2, row,
                             values=valueHeaders,
                             selectindex=zStructuralNode.choiceNodeIndex,
                             columnspan=2,
                             comboboxselected=self.onComboBoxSelected)
                combobox.zStructuralNode = zStructuralNode
                combobox.zChoiceOrdIndex = row - 1
                combobox.objectId = hdr.objectId = zStructuralNode.objectId()
                gridBorder(self.gridColHdr, self.dataFirstCol + 3, row, RIGHTBORDER)
    
            if zStructuralNode.childStructuralNodes:
                for zStructuralNode in zStructuralNode.childStructuralNodes:
                    self.zAxis(row + 1, zStructuralNode, zAspects, clearZchoices)
            else: # nested-nost element, aspects process inheritance
                for aspect in aspectModels[self.aspectModel]:
                    for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                        if zStructuralNode.hasAspect(ruleAspect): #implies inheriting from other z axes
                            if ruleAspect == Aspect.DIMENSIONS:
                                for dim in (zStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                    zAspects[dim].add(zStructuralNode)
                            else:
                                zAspects[ruleAspect].add(zStructuralNode)
            
    def onComboBoxSelected(self, *args):
        combobox = args[0].widget
        self.zOrdinateChoices[combobox.zStructuralNode._definitionNode] = \
            combobox.zStructuralNode.choiceNodeIndex = combobox.valueIndex
        self.view() # redraw grid
            
    def xAxis(self, leftCol, topRow, rowBelow, xParentStructuralNode, xStructuralNodes, childrenFirst, renderNow, atTop):
        if xParentStructuralNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            widthToSpanParent = 0
            sideBorder = not xStructuralNodes
            if atTop and sideBorder and childrenFirst:
                gridBorder(self.gridColHdr, self.dataFirstCol, 1, LEFTBORDER, rowspan=self.dataFirstRow)
            for xStructuralNode in xParentStructuralNode.childStructuralNodes:
                if not xStructuralNode.isRollUp:
                    noDescendants = False
                    rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, # nested items before totals
                                                                childrenFirst, childrenFirst, False)
                    if row - 1 < parentRow:
                        parentRow = row - 1
                    #if not leafNode: 
                    #    rightCol -= 1
                    nonAbstract = not xStructuralNode.isAbstract
                    if nonAbstract:
                        width += 100 # width for this label, in screen units
                    widthToSpanParent += width
                    label = xStructuralNode.header(lang=self.lang,
                                                   returnGenLabel=isinstance(xStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))
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
                                objectId=xStructuralNode.objectId(),
                                onClick=self.onClick)
                        if nonAbstract:
                            for i, role in enumerate(self.colHdrNonStdRoles):
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - len(self.colHdrNonStdRoles) + i, TOPBORDER)
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - len(self.colHdrNonStdRoles) + i, sideBorder)
                                gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - len(self.colHdrNonStdRoles) + i, 
                                        xStructuralNode.header(role=role, lang=self.lang), 
                                        anchor="center",
                                        wraplength=100, # screen units
                                        objectId=xStructuralNode.objectId(),
                                        onClick=self.onClick)
                            ''' was
                            if self.colHdrDocRow:
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, TOPBORDER)
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, sideBorder)
                                gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1 - self.rowHdrCodeCol, 
                                        xStructuralNode.header(role="http://www.xbrl.org/2008/role/documentation",
                                                               lang=self.lang), 
                                        anchor="center",
                                        wraplength=100, # screen units
                                        objectId=xStructuralNode.objectId(),
                                        onClick=self.onClick)
                            if self.colHdrCodeRow:
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, TOPBORDER)
                                gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, sideBorder)
                                gridHdr(self.gridColHdr, thisCol, self.dataFirstRow - 1, 
                                        xStructuralNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                                        anchor="center",
                                        wraplength=100, # screen units
                                        objectId=xStructuralNode.objectId(),
                                        onClick=self.onClick)
                            '''
                            gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, BOTTOMBORDER)
                            xStructuralNodes.append(xStructuralNode)
                    if nonAbstract:
                        rightCol += 1
                    if renderNow and not childrenFirst:
                        self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, childrenFirst, True, False) # render on this pass
                    leftCol = rightCol
            if atTop and sideBorder and not childrenFirst:
                gridBorder(self.gridColHdr, rightCol - 1, 1, RIGHTBORDER, rowspan=self.dataFirstRow)
            return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, leftCol, row, yParentStructuralNode, childrenFirst, renderNow, atLeft):
        if yParentStructuralNode is not None:
            nestedBottomRow = row
            if atLeft:
                gridBorder(self.gridRowHdr, self.rowHdrCols + len(self.rowHdrNonStdRoles), # was: self.rowHdrDocCol + self.rowHdrCodeCol, 
                           self.dataFirstRow, 
                           RIGHTBORDER, 
                           rowspan=self.dataRows)
                gridBorder(self.gridRowHdr, 1, self.dataFirstRow + self.dataRows - 1, 
                           BOTTOMBORDER, 
                           columnspan=(self.rowHdrCols + len(self.rowHdrNonStdRoles))) # was: self.rowHdrDocCol + self.rowHdrCodeCol))
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                if not yStructuralNode.isRollUp:
                    nestRow, nextRow = self.yAxis(leftCol + 1, row, yStructuralNode,  # nested items before totals
                                            childrenFirst, childrenFirst, False)
                    
                    isAbstract = (yStructuralNode.isAbstract or 
                                  (yStructuralNode.childStructuralNodes and
                                   not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord))))
                    isNonAbstract = not isAbstract
                    label = yStructuralNode.header(lang=self.lang,
                                                   returnGenLabel=isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))
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
                        depth = yStructuralNode.depth
                        gridHdr(self.gridRowHdr, leftCol, row, 
                                label if label is not None else "         ", 
                                anchor=("w" if isNonAbstract or nestRow == row else "center"),
                                columnspan=columnspan,
                                rowspan=(nestRow - row if isAbstract else None),
                                # wraplength is in screen units
                                wraplength=(self.rowHdrColWidth[depth] if isAbstract else
                                            self.rowHdrWrapLength - sum(self.rowHdrColWidth[0:depth])),
                                #minwidth=self.rowHdrColWidth[leftCol],
                                minwidth=(16 if isNonAbstract and nextRow > topRow else None),
                                objectId=yStructuralNode.objectId(),
                                onClick=self.onClick)
                        if isNonAbstract:
                            for i, role in enumerate(self.rowHdrNonStdRoles):
                                isCode = "code" in role
                                docCol = self.dataFirstCol - len(self.rowHdrNonStdRoles) + i
                                gridBorder(self.gridRowHdr, docCol, row, TOPBORDER)
                                gridBorder(self.gridRowHdr, docCol, row, LEFTBORDER)
                                gridHdr(self.gridRowHdr, docCol, row, 
                                        yStructuralNode.header(role=role, lang=self.lang), 
                                        anchor="c" if isCode else "w",
                                        wraplength=40 if isCode else 100, # screen units
                                        objectId=yStructuralNode.objectId(),
                                        onClick=self.onClick)
                            ''' was:
                            if self.rowHdrDocCol:
                                docCol = self.dataFirstCol - 1 - self.rowHdrCodeCol
                                gridBorder(self.gridRowHdr, docCol, row, TOPBORDER)
                                gridBorder(self.gridRowHdr, docCol, row, LEFTBORDER)
                                gridHdr(self.gridRowHdr, docCol, row, 
                                        yStructuralNode.header(role="http://www.xbrl.org/2008/role/documentation",
                                                             lang=self.lang), 
                                        anchor="w",
                                        wraplength=100, # screen units
                                        objectId=yStructuralNode.objectId(),
                                        onClick=self.onClick)
                            if self.rowHdrCodeCol:
                                codeCol = self.dataFirstCol - 1
                                gridBorder(self.gridRowHdr, codeCol, row, TOPBORDER)
                                gridBorder(self.gridRowHdr, codeCol, row, LEFTBORDER)
                                gridHdr(self.gridRowHdr, codeCol, row, 
                                        yStructuralNode.header(role="http://www.eurofiling.info/role/2010/coordinate-code"),
                                        anchor="center",
                                        wraplength=40, # screen units
                                        objectId=yStructuralNode.objectId(),
                                        onClick=self.onClick)
                            # gridBorder(self.gridRowHdr, leftCol, self.dataFirstRow - 1, BOTTOMBORDER)
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
                        dummy, row = self.yAxis(leftCol + 1, row, yStructuralNode, childrenFirst, renderNow, False) # render on this pass
            return (nestedBottomRow, row)
    
    def bodyCells(self, row, yParentStructuralNode, xStructuralNodes, zAspects, yChildrenFirst):
        if yParentStructuralNode is not None:
            rendrCntx = getattr(self.modelXbrl, "rendrCntx", None) # none for EU 2010 tables
            dimDefaults = self.modelXbrl.qnameDimensionDefaults
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                if yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspects, yChildrenFirst)
                if not yStructuralNode.isAbstract:
                    yAspects = defaultdict(set)
                    for aspect in aspectModels[self.aspectModel]:
                        for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                            if yStructuralNode.hasAspect(ruleAspect):
                                if ruleAspect == Aspect.DIMENSIONS:
                                    for dim in (yStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                        yAspects[dim].add(yStructuralNode)
                                else:
                                    yAspects[ruleAspect].add(yStructuralNode)
                        
                    gridSpacer(self.gridBody, self.dataFirstCol, row, LEFTBORDER)
                    # data for columns of row
                    ignoreDimValidity = self.ignoreDimValidity.get()
                    for i, xStructuralNode in enumerate(xStructuralNodes):
                        xAspects = defaultdict(set)
                        for aspect in aspectModels[self.aspectModel]:
                            for ruleAspect in aspectRuleAspects.get(aspect, (aspect,)):
                                if xStructuralNode.hasAspect(ruleAspect):
                                    if ruleAspect == Aspect.DIMENSIONS:
                                        for dim in (xStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                            xAspects[dim].add(xStructuralNode)
                                    else:
                                        xAspects[ruleAspect].add(xStructuralNode)
                        cellAspectValues = {}
                        matchableAspects = set()
                        for aspect in _DICT_SET(xAspects.keys()) | _DICT_SET(yAspects.keys()) | _DICT_SET(zAspects.keys()):
                            aspectValue = inheritedAspectValue(self, aspect, xAspects, yAspects, zAspects, xStructuralNode, yStructuralNode)
                            if dimDefaults.get(aspect) != aspectValue: # don't include defaulted dimensions
                                cellAspectValues[aspect] = aspectValue
                            matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                        cellDefaultedDims = _DICT_SET(dimDefaults) - _DICT_SET(cellAspectValues.keys())
                        priItemQname = cellAspectValues.get(Aspect.CONCEPT)
                            
                        concept = self.modelXbrl.qnameConcepts.get(priItemQname)
                        conceptNotAbstract = concept is None or not concept.isAbstract
                        from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
                        value = None
                        objectId = None
                        justify = None
                        fp = FactPrototype(self, cellAspectValues)
                        if conceptNotAbstract:
                            # reduce set of matchable facts to those with pri item qname and have dimension aspects
                            facts = self.modelXbrl.factsByQname[priItemQname] if priItemQname else self.modelXbrl.factsInInstance
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
                                    else:
                                        dimMemQname = None # match facts that report this dimension
                                    facts = facts & self.modelXbrl.factsByDimMemQname(aspect, dimMemQname)
                            for fact in facts:
                                if (all(aspectMatches(rendrCntx, fact, fp, aspect) 
                                        for aspect in matchableAspects) and
                                    all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                        for dim in cellDefaultedDims)):
                                    if yStructuralNode.hasValueExpression(xStructuralNode):
                                        value = yStructuralNode.evalValueExpression(fact, xStructuralNode)
                                    else:
                                        value = fact.effectiveValue
                                    objectId = fact.objectId()
                                    justify = "right" if fact.isNumeric else "left"
                                    break
                        if (conceptNotAbstract and
                            (value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp))):
                            if objectId is None:
                                objectId = "f{0}".format(len(self.factPrototypes))
                                self.factPrototypes.append(fp)  # for property views
                            gridCell(self.gridBody, self.dataFirstCol + i, row, value, justify=justify, 
                                     width=12, # width is in characters, not screen units
                                     objectId=objectId, onClick=self.onClick)
                        else:
                            fp.clear()  # dereference
                            gridSpacer(self.gridBody, self.dataFirstCol + i, row, CENTERCELL)
                        gridSpacer(self.gridBody, self.dataFirstCol + i, row, RIGHTBORDER)
                        gridSpacer(self.gridBody, self.dataFirstCol + i, row, BOTTOMBORDER)
                    row += 1
                if not yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspects, yChildrenFirst)
            return row
    def onClick(self, event):
        objId = event.widget.objectId
        if objId and objId[0] == "f":
            viewableObject = self.factPrototypes[int(objId[1:])]
        else:
            viewableObject = objId
        self.modelXbrl.viewModelObject(viewableObject)
        self.modelXbrl.modelManager.cntlr.currentView = self
            
    def cellEnter(self, *args):
        self.blockSelectEvent = 0
        self.modelXbrl.modelManager.cntlr.currentView = self

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
    
    def saveInstance(self, newFilename=None):
        if (not self.newFactItemOptions.entityIdentScheme or  # not initialized yet
            not self.newFactItemOptions.entityIdentValue or
            not self.newFactItemOptions.startDateDate or not self.newFactItemOptions.endDateDate):
            if not getNewFactItemOptions(self.modelXbrl.modelManager.cntlr, self.newFactItemOptions):
                return # new instance not set
        # newFilename = None # only used when a new instance must be created
        if self.modelXbrl.modelDocument.type != ModelDocument.Type.INSTANCE and newFilename is None:
            newFilename = self.modelXbrl.modelManager.cntlr.fileSave(view=self, fileType="xbrl")
            if not newFilename:
                return  # saving cancelled
        # continue saving in background
        thread = threading.Thread(target=lambda: self.backgroundSaveInstance(newFilename))
        thread.daemon = True
        thread.start()

    def backgroundSaveInstance(self, newFilename=None):
        cntlr = self.modelXbrl.modelManager.cntlr
        if newFilename and self.modelXbrl.modelDocument.type != ModelDocument.Type.INSTANCE:
            self.modelXbrl.modelManager.showStatus(_("creating new instance {0}").format(os.path.basename(newFilename)))
            self.modelXbrl.modelManager.cntlr.waitForUiThreadQueue() # force status update
            self.modelXbrl.createInstance(newFilename) # creates an instance as this modelXbrl's entrypoing
        instance = self.modelXbrl
        cntlr.showStatus(_("Saving {0}").format(instance.modelDocument.basename))
        cntlr.waitForUiThreadQueue() # force status update
        newCntx = ModelXbrl.AUTO_LOCATE_ELEMENT
        newUnit = ModelXbrl.AUTO_LOCATE_ELEMENT
        # check user keyed changes
        for bodyCell in self.gridBody.winfo_children():
            if isinstance(bodyCell, gridCell) and bodyCell.isChanged:
                value = bodyCell.value
                objId = bodyCell.objectId
                if objId:
                    if objId[0] == "f":
                        factPrototypeIndex = int(objId[1:])
                        factPrototype = self.factPrototypes[factPrototypeIndex]
                        concept = factPrototype.concept
                        entityIdentScheme = self.newFactItemOptions.entityIdentScheme
                        entityIdentValue = self.newFactItemOptions.entityIdentValue
                        periodType = factPrototype.concept.periodType
                        periodStart = self.newFactItemOptions.startDateDate if periodType == "duration" else None
                        periodEndInstant = self.newFactItemOptions.endDateDate
                        qnameDims = factPrototype.context.qnameDims
                        prevCntx = instance.matchContext(
                             entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, 
                             qnameDims, [], [])
                        if prevCntx is not None:
                            cntxId = prevCntx.id
                        else: # need new context
                            newCntx = instance.createContext(entityIdentScheme, entityIdentValue, 
                                          periodType, periodStart, periodEndInstant, 
                                          concept.qname, qnameDims, [], [],
                                          afterSibling=newCntx)
                            cntxId = newCntx.id
                            # new context
                        if concept.isNumeric:
                            if concept.isMonetary:
                                unitMeasure = qname(XbrlConst.iso4217, self.newFactItemOptions.monetaryUnit)
                                unitMeasure.prefix = "iso4217"  # want to save with a recommended prefix
                                decimals = self.newFactItemOptions.monetaryDecimals
                            elif concept.isShares:
                                unitMeasure = XbrlConst.qnXbrliShares
                                decimals = self.newFactItemOptions.nonMonetaryDecimals
                            else:
                                unitMeasure = XbrlConst.qnXbrliPure
                                decimals = self.newFactItemOptions.nonMonetaryDecimals
                            prevUnit = instance.matchUnit([unitMeasure],[])
                            if prevUnit is not None:
                                unitId = prevUnit.id
                            else:
                                newUnit = instance.createUnit([unitMeasure],[], afterSibling=newUnit)
                                unitId = newUnit.id
                        attrs = [("contextRef", cntxId)]
                        if concept.isNumeric:
                            attrs.append(("unitRef", unitId))
                            attrs.append(("decimals", decimals))
                            value = Locale.atof(self.modelXbrl.locale, value, str.strip)
                        newFact = instance.createFact(concept.qname, attributes=attrs, text=value)
                        bodyCell.objectId = newFact.objectId()  # switch cell to now use fact ID
                        if self.factPrototypes[factPrototypeIndex] is not None:
                            self.factPrototypes[factPrototypeIndex].clear()
                        self.factPrototypes[factPrototypeIndex] = None #dereference fact prototype
                    else: # instance fact, not prototype
                        fact = self.modelXbrl.modelObject(objId)
                        if fact.concept.isNumeric:
                            value = Locale.atof(self.modelXbrl.locale, value, str.strip)
                        if fact.value != value:
                            if fact.concept.isNumeric and fact.isNil != (not value):
                                fact.isNil = not value
                                if value: # had been nil, now it needs decimals
                                    fact.decimals = (self.newFactItemOptions.monetaryDecimals
                                                     if fact.concept.isMonetary else
                                                     self.newFactItemOptions.nonMonetaryDecimals)
                            fact.text = value
                            XmlValidate.validate(instance, fact)
                    bodyCell.isChanged = False  # clear change flag
        instance.saveInstance(newFilename) # may override prior filename for instance from main menu
        cntlr.showStatus(_("Saved {0}").format(instance.modelDocument.basename), clearAfter=3000)
            