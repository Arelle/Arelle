'''
Created on Oct 5, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.

'''
import os, threading, time
from tkinter import Menu, BooleanVar, font as tkFont
from arelle import (ViewWinTkTable, ModelDocument, ModelDtsObject, ModelInstanceObject, XbrlConst, 
                    ModelXbrl, XmlValidate, Locale, FunctionXfi,
                    ValidateXbrlDimensions)
from arelle.ModelValue import qname, QName
from arelle.RenderingResolver import resolveAxesStructure, RENDER_UNITS_PER_CHAR
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectModelAspect
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelRenderingObject import (ModelClosedDefinitionNode, ModelEuAxisCoord,
                                         ModelFilterDefinitionNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE)
from arelle.FormulaEvaluator import init as formulaEvaluatorInit, aspectMatches

from arelle.PrototypeInstanceObject import FactPrototype
from arelle.UITkTable import XbrlTable
from arelle.DialogNewFactItem import getNewFactItemOptions
from collections import defaultdict
from _tkinter import TclError

try:
    from tkinter import ttk
    _Combobox = ttk.Combobox
except ImportError:
    from ttk import Combobox
    _Combobox = Combobox

emptyList = []

ENTRY_WIDTH_IN_CHARS = 12 # width of a data column entry cell in characters (nominal)
PADDING = 20 # screen units of padding between entry cells

def viewRenderedGrid(modelXbrl, tabWin, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, tabWin, lang)
        
    view.blockMenuEvents = 1

    menu = view.contextMenu()
    optionsMenu = Menu(view.viewFrame, tearoff=0)
    optionsMenu.add_command(label=_("New fact item options"), underline=0, command=lambda: getNewFactItemOptions(modelXbrl.modelManager.cntlr, view.newFactItemOptions))
    optionsMenu.add_command(label=_("Open breakdown entry rows"), underline=0, command=view.setOpenBreakdownEntryRows)
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
    saveMenu.add_command(label=_("Layout model"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(view=view, fileType="xml"))
    saveMenu.add_command(label=_("XBRL instance"), underline=0, command=view.saveInstance)
    menu.add_cascade(label=_("Save"), menu=saveMenu, underline=0)
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.viewFrame.bind("<Enter>", view.cellEnter, '+')
    view.viewFrame.bind("<Leave>", view.cellLeave, '+')
    view.viewFrame.bind("<FocusOut>", view.onQuitView, '+')
    view.viewFrame.bind("<1>", view.onClick, '+')
    view.viewFrame.bind("<Configure>", view.onConfigure, '+') # frame resized, redo column header wrap length ratios
    view.blockMenuEvents = 0
            
class ViewRenderedGrid(ViewWinTkTable.ViewTkTable):
    def __init__(self, modelXbrl, tabWin, lang):
        super(ViewRenderedGrid, self).__init__(modelXbrl, tabWin, _("Table"),
                                               False, lang)
        self.newFactItemOptions = ModelInstanceObject.NewFactItemOptions(xbrlInstance=modelXbrl)
        self.factPrototypes = []
        self.aspectEntryObjectIdsNode = {}
        self.aspectEntryObjectIdsCell = {}
        self.factPrototypeAspectEntryObjectIds = defaultdict(set)
        self.zOrdinateChoices = None
        # context menu Boolean vars
        self.options = self.modelXbrl.modelManager.cntlr.config.setdefault("viewRenderedGridOptions", {})
        self.openBreakdownLines = self.options.setdefault("openBreakdownLines", 5) # ensure there is a default entry
        self.ignoreDimValidity = BooleanVar(value=self.options.setdefault("ignoreDimValidity",True))
        self.xAxisChildrenFirst = BooleanVar(value=self.options.setdefault("xAxisChildrenFirst",True))
        self.yAxisChildrenFirst = BooleanVar(value=self.options.setdefault("yAxisChildrenFirst",False))
        formulaEvaluatorInit() # one-time module initialization
            
    def close(self):
        super(ViewRenderedGrid, self).close()
        if self.modelXbrl:
            for fp in self.factPrototypes:
                fp.clear()
            self.factPrototypes = None
            self.aspectEntryObjectIdsNode.clear()
            self.aspectEntryObjectIdsCell.clear()
        
    def loadTablesMenu(self):
        tblMenuEntries = {}             
        tblRelSet = self.modelXbrl.relationshipSet("Table-rendering")
        self.tablesToELR = {}
        for tblLinkroleUri in tblRelSet.linkRoleUris:
            for tableAxisArcrole in (XbrlConst.euTableAxis, XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD, XbrlConst.tableBreakdown201305, XbrlConst.tableBreakdown201301, XbrlConst.tableAxis2011):
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
                            self.tablesToELR[table.objectId()] = tblLinkroleUri
                            break
        self.tablesMenu.delete(0, self.tablesMenuLength)
        self.tablesMenuLength = 0
        self.tblELR = None
        for tblMenuEntry in sorted(tblMenuEntries.items()):
            tbl,elr = tblMenuEntry
            self.tablesMenu.add_command(label=tbl, command=lambda e=elr: self.view(viewTblELR=e)) # use this to activate profiling from menu selection:  , profile=True))
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
            
    def setOpenBreakdownEntryRows(self, *args):
        import tkinter.simpledialog
        newValue = tkinter.simpledialog.askinteger(_("arelle - Open breakdown entry rows setting"),
                _("The number of extra entry rows for open breakdowns is: {0} \n\n"
                  "(When a row header includes an open breakdown, such as \nfor typed dimension(s), this number of extra entry rows \nare provided below the table.)"
                  ).format(self.options["openBreakdownLines"]),
                parent=self.tabWin)
        if newValue is not None:
            self.options["openBreakdownLines"] = self.openBreakdownLines = newValue
            self.viewReloadDueToMenuAction()
        
    def view(self, viewTblELR=None, newInstance=None, profile=False):
        '''
        if profile: # for debugging only, to use, uncomment in loadTablesMenu
            import cProfile, pstats, sys
            statsFile = "/Users/hermf/temp/profileRendering.bin"
            cProfile.runctx("self.view(viewTblELR=viewTblELR)", globals(), locals(), statsFile)
            priorStdOut = sys.stdout
            sys.stdout = open("/Users/hermf/temp/profileRendering.txt", "w")
            statObj = pstats.Stats(statsFile)
            statObj.strip_dirs()
            statObj.sort_stats("time")
            statObj.print_stats()
            statObj.print_callees()
            statObj.print_callers()
            sys.stdout.flush()
            sys.stdout.close()
            del statObj
            sys.stdout = priorStdOut
            os.remove(statsFile)
            return
        '''
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
        self.table.resizeTable(self.dataFirstRow+self.dataRows-1, self.dataFirstCol+self.dataCols-1, titleRows=self.dataFirstRow-1, titleColumns=self.dataFirstCol-1)
        self.hasTableFilters = bool(self.modelTable.filterRelationships)
        
        if tblAxisRelSet:
            # review row header wrap widths and limit to 2/3 of the frame width (all are screen units)
            fontWidth = tkFont.Font(font='TkTextFont').configure()['size']
            fontWidth = fontWidth * 3 // 2
            dataColsAllowanceWidth = (fontWidth * ENTRY_WIDTH_IN_CHARS + PADDING) * self.dataCols + PADDING
            frameWidth = self.viewFrame.winfo_width()
            if dataColsAllowanceWidth + self.rowHdrWrapLength > frameWidth:
                if dataColsAllowanceWidth > frameWidth / 2:
                    rowHdrAllowanceWidth = frameWidth / 2
                else:
                    rowHdrAllowanceWidth = frameWidth - dataColsAllowanceWidth
                if self.rowHdrWrapLength > rowHdrAllowanceWidth:
                    widthRatio = rowHdrAllowanceWidth / self.rowHdrWrapLength
                    self.rowHdrWrapLength = rowHdrAllowanceWidth
                    fixedWidth = sum(w for w in self.rowHdrColWidth if w <= RENDER_UNITS_PER_CHAR)
                    adjustableWidth = sum(w for w in self.rowHdrColWidth if w > RENDER_UNITS_PER_CHAR)
                    if adjustableWidth> 0:
                        widthRatio = (rowHdrAllowanceWidth - fixedWidth) / adjustableWidth
                        for i in range(len(self.rowHdrColWidth)):
                            w = self.rowHdrColWidth[i]
                            if w > RENDER_UNITS_PER_CHAR:
                                self.rowHdrColWidth[i] = int(w * widthRatio)
            self.aspectEntryObjectIdsNode.clear()
            self.aspectEntryObjectIdsCell.clear()
            self.factPrototypeAspectEntryObjectIds.clear()
            self.table.initHeaderCellValue((self.modelTable.genLabel(lang=self.lang, strip=True) or  # use table label, if any 
                                            self.roledefinition),
                                           0, 0, (self.dataFirstCol - 2),
                                           (self.dataFirstRow - 2),
                                           XbrlTable.TG_TOP_LEFT_JUSTIFIED)
            self.table.initHeaderBorder(0, 0,
                                        hasLeftBorder=True,
                                        hasTopBorder=True,
                                        hasRightBorder=False,
                                        hasBottomBorder=False)
            self.zAspectStructuralNodes = defaultdict(set)
            self.zAxis(1, zTopStructuralNode, clearZchoices)
            xStructuralNodes = []
            colsFoundPlus1, _, _, _ = self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                                                 xTopStructuralNode, xStructuralNodes, self.xAxisChildrenFirst.get(), True, True)
            _, rowsFoundPlus1 = self.yAxis(1, self.dataFirstRow,
                                           yTopStructuralNode, self.yAxisChildrenFirst.get(), True, True)
            self.table.resizeTable(rowsFoundPlus1-1,
                                   colsFoundPlus1-1,
                                   clearData=False)
            for fp in self.factPrototypes: # dereference prior facts
                if fp is not None:
                    fp.clear()
            self.factPrototypes = []
            self.bodyCells(self.dataFirstRow, yTopStructuralNode, xStructuralNodes, self.zAspectStructuralNodes, self.yAxisChildrenFirst.get())
            self.table.clearModificationStatus()
                
            # data cells
            #print("body cells done")
                
        self.modelXbrl.profileStat("viewTable_" + os.path.basename(viewTblELR), time.time() - startedAt)

        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))
        self.blockMenuEvents -= 1

            
    def zAxis(self, row, zStructuralNode, clearZchoices):
        if zStructuralNode is not None:
            label = zStructuralNode.header(lang=self.lang)
            xValue = self.dataFirstCol-1
            yValue = row-1
            self.table.initHeaderCellValue(label,
                                           xValue, yValue,
                                           1, 0,
                                           XbrlTable.TG_LEFT_JUSTIFIED,
                                           objectId=zStructuralNode.objectId())
            self.table.initHeaderBorder(xValue, yValue,
                                        hasLeftBorder=True,
                                        hasTopBorder=True,
                                        hasRightBorder=False)
    
            if zStructuralNode.choiceStructuralNodes is not None: # combo box
                valueHeaders = [''.ljust(zChoiceStructuralNode.indent * 4) + # indent if nested choices 
                                (zChoiceStructuralNode.header(lang=self.lang) or '')
                                for zChoiceStructuralNode in zStructuralNode.choiceStructuralNodes]
                zAxisIsOpenExplicitDimension = False
                zAxisTypedDimension = None
                i = zStructuralNode.choiceNodeIndex # for aspect entry, use header selected
                comboBoxValue = None if i >= 0 else zStructuralNode.aspects.get('aspectValueLabel')
                chosenStructuralNode = zStructuralNode.choiceStructuralNodes[i]    
                aspect = None
                for aspect in chosenStructuralNode.aspectsCovered():
                    if aspect != Aspect.DIMENSIONS:
                        break
                # for open filter nodes of explicit dimension allow selection of all values
                zAxisAspectEntryMode = False
                if isinstance(chosenStructuralNode.definitionNode, ModelFilterDefinitionNode):
                    if isinstance(aspect, QName):
                        dimConcept = self.modelXbrl.qnameConcepts[aspect]
                        if dimConcept.isExplicitDimension:
                            if len(valueHeaders) != 1 or valueHeaders[0]: # not just a blank initial entry
                                valueHeaders.append("(all members)")
                            else:
                                valueHeaders.extend(
                                   self.explicitDimensionFilterMembers(zStructuralNode, chosenStructuralNode))
                                zAxisAspectEntryMode = True
                            zAxisIsOpenExplicitDimension = True
                        elif dimConcept.isTypedDimension:
                            if (zStructuralNode.choiceStructuralNodes[0].contextItemBinding is None and
                                not valueHeaders[0]): # remove filterNode from the list
                                ''' this isn't reliable
                                if i > 0:
                                    del zStructuralNode.choiceStructuralNodes[0]
                                    del valueHeaders[0]
                                    zStructuralNode.choiceNodeIndex = i = i-1
                                '''
                                if i >= 0:
                                    chosenStructuralNode = zStructuralNode.choiceStructuralNodes[i]
                                else:
                                    chosenStructuralNode = zStructuralNode # use aspects of structural node (for entered typed value)
                            if not comboBoxValue and not valueHeaders:
                                comboBoxValue = "--please select--"
                                i = -1
                            valueHeaders.append("(enter typed member)")
                            zAxisTypedDimension = dimConcept
                combobox = self.table.initHeaderCombobox(self.dataFirstCol + 1,
                                                         row-1,
                                                         colspan=1,
                                                         values=valueHeaders,
                                                         value=comboBoxValue,
                                                         selectindex=zStructuralNode.choiceNodeIndex if i >= 0 else None,
                                                         comboboxselected=self.onZComboBoxSelected)
                combobox.zStructuralNode = zStructuralNode
                combobox.zAxisIsOpenExplicitDimension = zAxisIsOpenExplicitDimension
                combobox.zAxisTypedDimension = zAxisTypedDimension
                combobox.zAxisAspectEntryMode = zAxisAspectEntryMode
                combobox.zAxisAspect = aspect
                combobox.zChoiceOrdIndex = row - 1
                combobox.objectId = zStructuralNode.objectId()
                self.table.initHeaderBorder(self.dataFirstCol + 2, row-1,
                                            hasRightBorder=True)
                # add aspect for chosen node
                self.setZStructuralNodeAspects(chosenStructuralNode)
            else:
                #process aspect on this node before child nodes in case it is overridden
                self.setZStructuralNodeAspects(zStructuralNode)
            # nested nodes override parent nodes
            for zStructuralNode in zStructuralNode.childStructuralNodes:
                self.zAxis(row + 1, zStructuralNode, clearZchoices)
                    
    def setZStructuralNodeAspects(self, zStructuralNode, add=True):
        for aspect in aspectModels[self.aspectModel]:
            if (aspect in zStructuralNode.aspects or # might be added as custom-entered value (typed dim)
                zStructuralNode.hasAspect(aspect, inherit=True)): #implies inheriting from other z axes
                if aspect == Aspect.DIMENSIONS:
                    for dim in (zStructuralNode.aspectValue(Aspect.DIMENSIONS, inherit=True) or emptyList):
                        if add:
                            self.zAspectStructuralNodes[dim].add(zStructuralNode)
                        else:
                            self.zAspectStructuralNodes[dim].discard(zStructuralNode)
                else:
                    if add:
                        self.zAspectStructuralNodes[aspect].add(zStructuralNode)
                    else:
                        self.zAspectStructuralNodes[aspect].discard(zStructuralNode)
            
    def onZComboBoxSelected(self, event):
        if self.hasChangesToSave():
            import tkinter.messagebox
            reply = tkinter.messagebox.askyesnocancel(
                        _("arelle - Unsaved Changes"),
                        _("Save unsaved changes before Z-axis change? \n(No will discard changes.)"), 
                        parent=self.tabWin)
            if reply is None:
                return # cancel
            if reply:  # yes
                self.saveInstance(onSaved=lambda: self.onZComboBoxSelected(event))
                return # called again after saving on ui foreground thread
        combobox = event.widget
        structuralNode = combobox.zStructuralNode
        if combobox.zAxisAspectEntryMode:
            aspectValue = structuralNode.aspectEntryHeaderValues.get(combobox.get())
            if aspectValue is not None:
                self.zOrdinateChoices[combobox.zStructuralNode.definitionNode] = \
                    structuralNode.aspects = {combobox.zAxisAspect: aspectValue, 'aspectValueLabel': combobox.get()}
                self.view() # redraw grid
        elif combobox.zAxisIsOpenExplicitDimension and combobox.get() == "(all members)":
            # reload combo box
            self.comboboxLoadExplicitDimension(combobox, 
                                               structuralNode, # owner of combobox
                                               structuralNode.choiceStructuralNodes[structuralNode.choiceNodeIndex]) # aspect filter node
            structuralNode.choiceNodeIndex = -1 # use entry aspect value
            combobox.zAxisAspectEntryMode = True
        elif combobox.zAxisTypedDimension is not None and combobox.get() == "(enter typed member)":
            # ask typed member entry
            import tkinter.simpledialog
            result = tkinter.simpledialog.askstring(_("Enter new typed dimension value"), 
                                                    combobox.zAxisTypedDimension.label(), 
                                                    parent=self.tabWin)
            if result:
                structuralNode.choiceNodeIndex = -1 # use entry aspect value
                aspectValue = FunctionXfi.create_element(self.rendrCntx, 
                                                         None, 
                                                         (combobox.zAxisTypedDimension.typedDomainElement.qname, (), result))
                self.zOrdinateChoices[combobox.zStructuralNode.definitionNode] = \
                    structuralNode.aspects = {combobox.zAxisAspect: aspectValue, 
                                              Aspect.DIMENSIONS: {combobox.zAxisTypedDimension.qname},
                                              'aspectValueLabel': result}
                if not hasattr(structuralNode, "aspectEntryHeaderValues"): structuralNode.aspectEntryHeaderValues = {}
                structuralNode.aspectEntryHeaderValues[result] = aspectValue
                valueHeaders = list(combobox["values"])
                if result not in valueHeaders: valueHeaders.insert(0, result)
                combobox["values"] = valueHeaders
                combobox.zAxisAspectEntryMode = True
                self.view() # redraw grid
        else:
            # remove prior combo choice aspect
            self.setZStructuralNodeAspects(structuralNode.choiceStructuralNodes[structuralNode.choiceNodeIndex], add=False)
            i = combobox.valueIndex
            self.zOrdinateChoices[combobox.zStructuralNode.definitionNode] =  structuralNode.choiceNodeIndex = i
            # set current combo choice aspect
            self.setZStructuralNodeAspects(structuralNode.choiceStructuralNodes[i])
            self.view() # redraw grid
            
    def xAxis(self, leftCol, topRow, rowBelow, xParentStructuralNode, xStructuralNodes, childrenFirst, renderNow, atTop):
        if xParentStructuralNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            widthToSpanParent = 0
            sideBorder = not xStructuralNodes
            if atTop and sideBorder and childrenFirst:
                self.table.initHeaderBorder(self.dataFirstCol-1, 0,
                                            cellsToTheRight=0,
                                            cellsBelow=self.dataFirstRow-1,
                                            hasLeftBorder=True)
            for xStructuralNode in xParentStructuralNode.childStructuralNodes:
                if not xStructuralNode.isRollUp:
                    noDescendants = False
                    rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, # nested items before totals
                                                                childrenFirst, childrenFirst, False)
                    if row - 1 < parentRow:
                        parentRow = row - 1
                    #if not leafNode: 
                    #    rightCol -= 1
                    isLabeled = xStructuralNode.isLabeled
                    nonAbstract = not xStructuralNode.isAbstract and isLabeled
                    if nonAbstract and isLabeled:
                        width += 100 # width for this label, in screen units
                    widthToSpanParent += width
                    hasLeftBorder = False;
                    hasRightBorder = False;
                    if childrenFirst:
                        thisCol = rightCol
                        hasRightBorder = True
                    else:
                        thisCol = leftCol
                        hasLeftBorder = True
                    if renderNow and isLabeled:
                        columnspan = (rightCol - leftCol + (1 if nonAbstract else 0))
                        label = xStructuralNode.header(lang=self.lang,
                                                       returnGenLabel=isinstance(xStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))
                        xValue = leftCol-1
                        yValue = topRow-1
                        self.table.initHeaderCellValue(label if label
                                                       else "         ",
                                                       xValue, yValue,
                                                       columnspan-1,
                                                       ((row - topRow + 1) if leafNode else 1)-1,
                                                       XbrlTable.TG_CENTERED,
                                                       objectId=xStructuralNode.objectId())
                        # Initially the rowspan was (rowBelow - topRow + 1)
                        self.table.initHeaderBorder(xValue, yValue,
                                                    cellsBelow=(rowBelow - topRow),
                                                    hasLeftBorder=hasLeftBorder,
                                                    hasTopBorder=True,
                                                    hasRightBorder=hasRightBorder)
                        if nonAbstract:
                            xValue = thisCol - 1
                            for i, role in enumerate(self.colHdrNonStdRoles):
                                j = (self.dataFirstRow
                                     - len(self.colHdrNonStdRoles) + i)-1
                                self.table.initHeaderCellValue(xStructuralNode.header(role=role, lang=self.lang),
                                                         xValue,
                                                         j,
                                                         0,
                                                         0,
                                                         XbrlTable.TG_CENTERED,
                                                         objectId=xStructuralNode.objectId())
                                self.table.initHeaderBorder(xValue, j,
                                                            hasLeftBorder=hasLeftBorder,
                                                            hasTopBorder=True,
                                                            hasRightBorder=hasRightBorder)
                            self.table.initHeaderBorder(xValue,
                                                        self.dataFirstRow - 2,
                                                        hasBottomBorder=True)
                            xStructuralNodes.append(xStructuralNode)
                    if nonAbstract:
                        rightCol += 1
                    if renderNow and not childrenFirst:
                        self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, childrenFirst, True, False) # render on this pass
                    leftCol = rightCol
            if atTop and sideBorder and not childrenFirst:
                # Initially, rowspan=self.dataFirstRow
                self.table.initHeaderBorder(rightCol - 2, 0,
                                            cellsToTheRight=0,
                                            cellsBelow=self.dataFirstRow-1,
                                            hasRightBorder=True)
            return (rightCol, parentRow, widthToSpanParent, noDescendants)
            
    def yAxis(self, leftCol, row, yParentStructuralNode, childrenFirst, renderNow, atLeft):
        if yParentStructuralNode is not None:
            nestedBottomRow = row
            if atLeft:
                # initially rowspan was self.dataRows
                self.table.initHeaderBorder(self.rowHdrCols + len(self.rowHdrNonStdRoles)-1,
                                            self.dataFirstRow-1,
                                            cellsToTheRight=0,
                                            cellsBelow=self.dataRows-1,
                                            hasRightBorder=True)
                # initially colspan was (self.rowHdrCols + len(self.rowHdrNonStdRoles))
                self.table.initHeaderBorder(0,
                                            self.dataFirstRow + self.dataRows - 2,
                                            cellsToTheRight=(self.rowHdrCols + len(self.rowHdrNonStdRoles))-1,
                                            cellsBelow=0,
                                            hasBottomBorder=True)
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                if not yStructuralNode.isRollUp:
                    isAbstract = (yStructuralNode.isAbstract or 
                                  (yStructuralNode.childStructuralNodes and
                                   not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord))))
                    isNonAbstract = not isAbstract
                    isLabeled = yStructuralNode.isLabeled
                    nestRow, nextRow = self.yAxis(leftCol + isLabeled, row, yStructuralNode,  # nested items before totals
                                            childrenFirst, childrenFirst, False)
                    
                    topRow = row
                    if childrenFirst and isNonAbstract:
                        row = nextRow
                    if renderNow and isLabeled:
                        columnspan = self.rowHdrCols - leftCol + 1 if isNonAbstract or nextRow == row else 1
                        self.table.initHeaderBorder(leftCol-1, topRow-1,
                                                    cellsToTheRight=(0 if childrenFirst and nextRow > row else columnspan-1),
                                                    cellsBelow=(nestRow - topRow),
                                                    hasLeftBorder=True,
                                                    hasTopBorder=True)
                        if childrenFirst and row > topRow:
                            self.table.initHeaderBorder(leftCol, row-1,
                                                        cellsToTheRight=(self.rowHdrCols - leftCol)-1,
                                                        cellsBelow=0,
                                                        hasTopBorder=True)
                        depth = yStructuralNode.depth
                        wraplength = (self.rowHdrColWidth[depth] if isAbstract else
                                      self.rowHdrWrapLength - sum(self.rowHdrColWidth[0:depth]))
                        if wraplength < 0:
                            wraplength = self.rowHdrColWidth[depth]
                        label = yStructuralNode.header(lang=self.lang,
                                                       returnGenLabel=isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)),
                                                       recurseParent=not isinstance(yStructuralNode.definitionNode, ModelFilterDefinitionNode))
                        if label != OPEN_ASPECT_ENTRY_SURROGATE:
                            # TODO: check if the following parameters have to
                            # be used:
                            # - wraplength=wraplength
                            # - minwidth=(RENDER_UNITS_PER_CHAR if isNonAbstract and nextRow > topRow else None)
                            xValue = leftCol-1
                            yValue = row-1
                            self.table.initHeaderCellValue(label if label is not None else "         ",
                                                           xValue, yValue,
                                                           columnspan-1,
                                                           (nestRow - row if isAbstract else 1)-1,
                                                           (XbrlTable.TG_LEFT_JUSTIFIED
                                                            if isNonAbstract or nestRow == row
                                                            else XbrlTable.TG_CENTERED),
                                                           objectId=yStructuralNode.objectId())
                            self.table.initHeaderBorder(xValue, yValue,
                                                        hasLeftBorder=True,
                                                        hasTopBorder=True,
                                                        hasRightBorder=True,
                                                        hasBottomBorder=True)
                        else:
                            self.aspectEntryObjectIdsNode[yStructuralNode.aspectEntryObjectId] = yStructuralNode
                            # TODO: is the following still needed?
                            # width=int(max(wraplength/RENDER_UNITS_PER_CHAR, 5))
                            self.aspectEntryObjectIdsCell[yStructuralNode.aspectEntryObjectId] = self.table.initHeaderCombobox(leftCol-1,
                                                                                                                               row-1,
                                                                                                                               values=self.aspectEntryValues(yStructuralNode),
                                                                                                                               objectId=yStructuralNode.aspectEntryObjectId,
                                                                                                                               comboboxselected=self.onAspectComboboxSelection)
                        if isNonAbstract:
                            for i, role in enumerate(self.rowHdrNonStdRoles):
                                isCode = "code" in role
                                docCol = self.dataFirstCol - len(self.rowHdrNonStdRoles) + i-1
                                yValue = row-1
                                # TODO: wraplength=40 if isCode else ENTRY_WIDTH_SCREEN_UNITS
                                self.table.initHeaderCellValue(yStructuralNode.header(role=role, lang=self.lang),
                                                               docCol, yValue,
                                                               0, 0,
                                                               XbrlTable.TG_CENTERED if isCode else XbrlTable.TG_RIGHT_JUSTIFIED,
                                                               objectId=yStructuralNode.objectId())
                                self.table.initHeaderBorder(docCol, yValue,
                                                            hasLeftBorder=True,
                                                            hasTopBorder=True)                    if isNonAbstract:
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
                        dummy, row = self.yAxis(leftCol + isLabeled, row, yStructuralNode, childrenFirst, renderNow, False) # render on this pass
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
                    # TODO: check if border must be set (LEFTBORDER)
                    self.table.initHeaderBorder(self.dataFirstCol - 2,
                                                row-2,
                                                hasLeftBorder=True)
    
                    # data for columns of row
                    #print ("row " + str(row) + "yNode " + yStructuralNode.definitionNode.objectId() )
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
                        for aspect in _DICT_SET(xAspectStructuralNodes.keys()) | _DICT_SET(yAspectStructuralNodes.keys()) | _DICT_SET(zAspectStructuralNodes.keys()):
                            aspectValue = xStructuralNode.inheritedAspectValue(yStructuralNode,
                                               self, aspect, cellTagSelectors, 
                                               xAspectStructuralNodes, yAspectStructuralNodes, zAspectStructuralNodes)
                            # value is None for a dimension whose value is to be not reported in this slice
                            if (isinstance(aspect, _INT) or  # not a dimension
                                dimDefaults.get(aspect) != aspectValue or # explicit dim defaulted will equal the value
                                aspectValue is not None): # typed dim absent will be none
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
                                        dimMemQname = ModelXbrl.DEFAULT
                                    else:
                                        dimMemQname = None # match facts that report this dimension
                                    facts = facts & self.modelXbrl.factsByDimMemQname(aspect, dimMemQname)
                            for fact in facts:
                                if (all(aspectMatches(self.rendrCntx, fact, fp, aspect) 
                                        for aspect in matchableAspects) and
                                    all(fact.context.dimMemberQname(dim,includeDefaults=True) in (dimDefaults[dim], None)
                                        for dim in cellDefaultedDims)):
                                    if yStructuralNode.hasValueExpression(xStructuralNode):
                                        value = yStructuralNode.evalValueExpression(fact, xStructuralNode)
                                    else:
                                        value = fact.effectiveValue
                                    objectId = fact.objectId()
                                    justify = XbrlTable.TG_RIGHT_JUSTIFIED if fact.isNumeric else XbrlTable.TG_LEFT_JUSTIFIED
                                    break
                        if (conceptNotAbstract and
                            (value is not None or ignoreDimValidity or isFactDimensionallyValid(self, fp) or
                             isEntryPrototype)):
                            if objectId is None:
                                objectId = "f{0}".format(len(self.factPrototypes))
                                self.factPrototypes.append(fp)  # for property views
                                for aspect, aspectValue in cellAspectValues.items():
                                    if isinstance(aspectValue, str) and aspectValue.startswith(OPEN_ASPECT_ENTRY_SURROGATE):
                                        self.factPrototypeAspectEntryObjectIds[objectId].add(aspectValue) 
                            modelConcept = fp.concept
                            if (justify is None) and modelConcept is not None:
                                justify = XbrlTable.TG_RIGHT_JUSTIFIED if modelConcept.isNumeric else XbrlTable.TG_LEFT_JUSTIFIED
                            if modelConcept is not None and modelConcept.isEnumeration:
                                myValidationObject = ValidateXbrl(self.modelXbrl)
                                enumerationSet = ValidateXbrlDimensions.usableEnumerationMembers(myValidationObject, modelConcept)
                                enumerationDict = dict()
                                for enumerationItem in enumerationSet:
                                    enumerationDict[enumerationItem.label()] = enumerationItem.qname
                                enumerationValues = sorted(list(enumerationDict.keys()))
                                enumerationQNameStrings = [""]+list(str(enumerationDict[enumerationItem]) for enumerationItem in enumerationValues)
                                enumerationValues = [""]+enumerationValues
                                try:
                                    selectedIdx = enumerationQNameStrings.index(value)
                                    effectiveValue = enumerationValues[selectedIdx]
                                except ValueError:
                                    effectiveValue = enumerationValues[0]
                                    selectedIdx = 0
                                # TODO: check if this is still used:
                                # width=ENTRY_WIDTH_IN_CHARS,
                                self.table.initCellCombobox(effectiveValue,
                                                            enumerationValues,
                                                            self.dataFirstCol + i-1,
                                                            row-1,
                                                            objectId=objectId,
                                                            selectindex=selectedIdx,
                                                            codes=enumerationDict)
                            elif modelConcept is not None and modelConcept.type.qname == XbrlConst.qnXbrliQNameItemType:
                                if eurofilingModelPrefix in concept.nsmap and concept.nsmap.get(eurofilingModelPrefix) == eurofilingModelNamespace:
                                    hierarchy = concept.get("{" + eurofilingModelNamespace + "}" + "hierarchy", None)
                                    domainQNameAsString = concept.get("{" + eurofilingModelNamespace + "}" + "domain", None)
                                    if hierarchy is not None and domainQNameAsString is not None:
                                        newAspectValues = [""]
                                        newAspectQNames = dict()
                                        newAspectQNames[""] = None
                                        domPrefix, _, domLocalName = domainQNameAsString.strip().rpartition(":")
                                        domNamespace = concept.nsmap.get(domPrefix)
                                        relationships = concept_relationships(self.rendrCntx, 
                                             None, 
                                             (QName(domPrefix, domNamespace, domLocalName),
                                              hierarchy, # linkrole,
                                              "XBRL-dimensions",
                                              'descendant'),
                                             False) # return flat list
                                        for rel in relationships:
                                            if (rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember)
                                                and rel.isUsable):
                                                header = rel.toModelObject.label(lang=self.lang)
                                                newAspectValues.append(header)
                                                currentQName = rel.toModelObject.qname
                                                if str(currentQName) == value:
                                                    value = header
                                                newAspectQNames[header] = currentQName
                                    else:
                                        newAspectValues = None
                                else:
                                    newAspectValues = None
                                if newAspectValues is None:
                                    # TODO: check if the following parameter
                                    # is needed:
                                    # width=ENTRY_WIDTH_IN_CHARS
                                    self.table.initCellValue(value,
                                                             self.dataFirstCol + i-1,
                                                             row-1,
                                                             justification=justify,
                                                             objectId=objectId)
                                else:
                                    qNameValues = newAspectValues
                                    try:
                                        selectedIdx = qNameValues.index(value)
                                        effectiveValue = value
                                    except ValueError:
                                        effectiveValue = qNameValues[0]
                                        selectedIdx = 0
                                    # TODO: check if the following parameter
                                    # is needed:
                                    # width=ENTRY_WIDTH_IN_CHARS,
                                    self.table.initCellCombobox(effectiveValue,
                                                                qNameValues,
                                                                self.dataFirstCol + i-1,
                                                                row-1,
                                                                objectId=objectId,
                                                                selectindex=selectedIdx,
                                                                codes=newAspectQNames)
                            elif modelConcept is not None and modelConcept.type.qname == XbrlConst.qnXbrliBooleanItemType:
                                booleanValues = ["",
                                                 XbrlConst.booleanValueTrue,
                                                 XbrlConst.booleanValueFalse]
                                try:
                                    selectedIdx = booleanValues.index(value)
                                    effectiveValue = value
                                except ValueError:
                                    effectiveValue = booleanValues[0]
                                    selectedIdx = 0
                                # TODO: check if the following parameter
                                # is needed:
                                # width=ENTRY_WIDTH_IN_CHARS,
                                self.table.initCellCombobox(effectiveValue,
                                                            booleanValues,
                                                            self.dataFirstCol + i-1,
                                                            row-1,
                                                            objectId=objectId,
                                                            selectindex=selectedIdx)
                            else:
                                # TODO: check if the following parameter
                                # is needed:
                                # width=ENTRY_WIDTH_IN_CHARS
                                self.table.initCellValue(value,
                                                         self.dataFirstCol + i-1,
                                                         row-1,
                                                         justification=justify,
                                                         objectId=objectId)
                        else:
                            fp.clear()  # dereference
                            self.table.initReadonlyCell(self.dataFirstCol + i-1,
                                                        row-1)
                        # TODO: check if there is a need for borders:
                        # RIGHTBORDER, BOTTOMBORDER
                        #self.table.initHeaderBorder(self.dataFirstCol + i-1,
                        #                            row-1,
                        #                            hasRightBorder=True,
                        #                            hasBottomBorder=True)
                    row += 1
                if not yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst)
            return row
        
    def onClick(self, event):
        try:
            objId = event.widget.objectId
            if objId and objId[0] == "f":
                viewableObject = self.factPrototypes[int(objId[1:])]
            else:
                viewableObject = objId
            self.modelXbrl.viewModelObject(viewableObject)
        except AttributeError: # not clickable
            pass
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
            try:
                if isinstance(modelObject, ModelDtsObject.ModelRelationship):
                    objectId = modelObject.toModelObject.objectId()
                else:
                    objectId = modelObject.objectId()
                if objectId in self.tablesToELR:
                    self.view(viewTblELR=self.tablesToELR[objectId])
            except (KeyError, AttributeError):
                    pass
            self.blockViewModelObject -= 1
            
    def onConfigure(self, event, *args):
        if not self.blockMenuEvents:
            lastFrameWidth = getattr(self, "lastFrameWidth", 0)
            lastFrameHeight = getattr(self, "lastFrameHeight", 0)
            frameWidth = self.tabWin.winfo_width()
            frameHeight = self.tabWin.winfo_height()
            if lastFrameWidth != frameWidth or lastFrameHeight != frameHeight:
                self.updateInstanceFromFactPrototypes()
                self.lastFrameWidth = frameWidth
                self.lastFrameHeight = frameHeight
                self.table.config(maxheight=frameHeight-self.viewFrame.horizontalScrollbarHeight,
                                  maxwidth=frameWidth-self.viewFrame.verticalScrollbarWidth)
                if lastFrameWidth:
                    # frame resized, recompute row header column widths and lay out table columns
                    """
                    def sleepAndReload():
                        time.sleep(.75)
                        self.viewReloadDueToMenuAction()
                    self.modelXbrl.modelManager.cntlr.uiThreadQueue.put((sleepAndReload, []))
                    """
                    #self.modelXbrl.modelManager.cntlr.uiThreadQueue.put((self.viewReloadDueToMenuAction, []))
                    def deferredReload():
                        self.deferredReloadCount -= 1  # only do reload after all queued reload timers expire
                        if self.deferredReloadCount <= 0:
                            self.viewReloadDueToMenuAction()
                    self.deferredReloadCount = getattr(self, "deferredReloadCount", 0) + 1
                    self.viewFrame.after(1500, deferredReload)
                            
    def onQuitView(self, event, *args):
        self.updateInstanceFromFactPrototypes()
            
    def hasChangesToSave(self):
        return len(self.table.modifiedCells)
    
    def updateInstanceFromFactPrototypes(self):
        # Only update the model if it already exists
        if self.modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE:
            instance = self.modelXbrl
            cntlr =  instance.modelManager.cntlr
            newCntx = ModelXbrl.AUTO_LOCATE_ELEMENT
            newUnit = ModelXbrl.AUTO_LOCATE_ELEMENT
            tbl = self.table
            # check user keyed changes to aspects
            aspectEntryChanges = {}  # index = widget ID,  value = widget contents
            aspectEntryChangeIds = _DICT_SET(aspectEntryChanges.keys())
            for modifiedCell in tbl.getCoordinatesOfModifiedCells():
                objId = tbl.getObjectId(modifiedCell)
                if objId is not None and len(objId)>0:
                    if tbl.isHeaderCell(modifiedCell):
                        if objId[0] == OPEN_ASPECT_ENTRY_SURROGATE:
                            bodyCell.isChanged = False  # clear change flag
                            aspectEntryChanges[objId] = bodyCell.value
            aspectEntryChangeIds = _DICT_SET(aspectEntryChanges.keys())
            # check user keyed changes to facts
            for bodyCell in self.gridBody.winfo_children():
                if isinstance(bodyCell, gridCell) and bodyCell.isChanged:
                    value = bodyCell.value
                    objId = bodyCell.objectId
                    if objId:
                        if (objId[0] == "f" and 
                            (bodyCell.isChanged or # change in fact value widget or any open aspect widget
                             self.factPrototypeAspectEntryObjectIds[objId] & aspectEntryChangeIds)):
                            factPrototypeIndex = int(objId[1:])
                            factPrototype = self.factPrototypes[factPrototypeIndex]
                            concept = factPrototype.concept
                            entityIdentScheme = self.newFactItemOptions.entityIdentScheme
                            entityIdentValue = self.newFactItemOptions.entityIdentValue
                            periodType = factPrototype.concept.periodType
                            periodStart = self.newFactItemOptions.startDateDate if periodType == "duration" else None
                            periodEndInstant = self.newFactItemOptions.endDateDate
                            qnameDims = factPrototype.context.qnameDims
                            qnameDims.update(self.newFactOpenAspects(objId))
                            # open aspects widgets
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
                            bodyCell.isChanged = False  # clear change flag
                        elif objId[0] != "a": # instance fact, not prototype
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
                                instance.setIsModified()
                                XmlValidate.validate(instance, fact)
                            bodyCell.isChanged = False  # clear change flag
                        
    def saveInstance(self, newFilename=None, onSaved=None):
        if (not self.newFactItemOptions.entityIdentScheme or  # not initialized yet
            not self.newFactItemOptions.entityIdentValue or
            not self.newFactItemOptions.startDateDate or not self.newFactItemOptions.endDateDate):
            if not getNewFactItemOptions(self.modelXbrl.modelManager.cntlr, self.newFactItemOptions):
                return # new instance not set
        # newFilename = None # only used when a new instance must be created
        
        self.updateInstanceFromFactPrototypes()
        if self.modelXbrl.modelDocument.type != ModelDocument.Type.INSTANCE and newFilename is None:
            newFilename = self.modelXbrl.modelManager.cntlr.fileSave(view=self, fileType="xbrl")
            if not newFilename:
                return  # saving cancelled
        # continue saving in background
        thread = threading.Thread(target=lambda: self.backgroundSaveInstance(newFilename, onSaved))
        thread.daemon = True
        thread.start()
        
    def backgroundSaveInstance(self, newFilename=None, onSaved=None):
        cntlr = self.modelXbrl.modelManager.cntlr
        if newFilename and self.modelXbrl.modelDocument.type != ModelDocument.Type.INSTANCE:
            self.modelXbrl.modelManager.showStatus(_("creating new instance {0}").format(os.path.basename(newFilename)))
            self.modelXbrl.modelManager.cntlr.waitForUiThreadQueue() # force status update
            self.modelXbrl.createInstance(newFilename) # creates an instance as this modelXbrl's entrypoint
        instance = self.modelXbrl
        cntlr.showStatus(_("Saving {0}").format(instance.modelDocument.basename))
        cntlr.waitForUiThreadQueue() # force status update

        self.updateInstanceFromFactPrototypes()
        instance.saveInstance(newFilename) # may override prior filename for instance from main menu
        cntlr.showStatus(_("Saved {0}").format(instance.modelDocument.basename), clearAfter=3000)
        if onSaved is not None:
            self.modelXbrl.modelManager.cntlr.uiThreadQueue.put((onSaved, []))

    def newFactOpenAspects(self, factObjectId):
        aspectValues = {}
        for aspectObjId in self.factPrototypeAspectEntryObjectIds[factObjectId]:
            structuralNode = self.aspectEntryObjectIdsNode[aspectObjId]
            for aspect in structuralNode.aspectsCovered():
                if aspect != Aspect.DIMENSIONS:
                    break
            gridCellItem = self.aspectEntryObjectIdsCell[aspectObjId]
            value = gridCellItem.get()
            # is aspect in a childStructuralNode? 
            if value:
                aspectValue = structuralNode.aspectEntryHeaderValues.get(value)
                if aspectValue is None: # try converting value
                    if isinstance(aspect, QName): # dimension
                        dimConcept = self.modelXbrl.qnameConcepts[aspect]
                        if dimConcept.isExplicitDimension:
                            # value must be qname
                            aspectValue = None # need to find member for the description
                        else:
                            typedDimElement = dimConcept.typedDomainElement
                            aspectValue = FunctionXfi.create_element(
                                  self.rendrCntx, None, (typedDimElement.qname, (), value))
                if aspectValue is not None:
                    aspectValues[aspect] = aspectValue
        return aspectValues
    
    def aspectEntryValues(self, structuralNode):
        for aspect in structuralNode.aspectsCovered():
            if aspect != Aspect.DIMENSIONS:
                break
        # if findHeader is None, return all header values in a list
        # otherwise return aspect value matching header if any
        depth = 0
        n = structuralNode
        while (n.parentStructuralNode is not None):
            depth += 1
            root = n = n.parentStructuralNode
            
        headers = set()
        headerValues = {}
        def getHeaders(n, d):
            for childStructuralNode in n.childStructuralNodes:
                if d == depth:
                    h = childStructuralNode.header(lang=self.lang, 
                                                   returnGenLabel=False, 
                                                   returnMsgFormatString=False)
                    if not childStructuralNode.isEntryPrototype() and h:
                        headerValues[h] = childStructuralNode.aspectValue(aspect)
                        headers.add(h)
                else:
                    getHeaders(childStructuralNode, d+1)
        getHeaders(root, 1)
            
        structuralNode.aspectEntryHeaderValues = headerValues       
        # is this an explicit dimension, if so add "(all members)" option at end
        headersList = sorted(headers)
        if isinstance(aspect, QName): # dimension
            dimConcept = self.modelXbrl.qnameConcepts[aspect]
            if dimConcept.isExplicitDimension:
                if headersList: # has entries, add all-memembers at end
                    headersList.append("(all members)")
                else:  # empty list, just add all members anyway
                    return self.explicitDimensionFilterMembers(structuralNode, structuralNode)
        return headersList

    def onAspectComboboxSelection(self, event):
        gridCombobox = event.widget
        if gridCombobox.get() == "(all members)":
            structuralNode = self.aspectEntryObjectIdsNode[gridCombobox.objectId]
            self.comboboxLoadExplicitDimension(gridCombobox, structuralNode, structuralNode)
            
    def comboboxLoadExplicitDimension(self, gridCombobox, structuralNode, structuralNodeWithFilter):
        gridCombobox["values"] = self.explicitDimensionFilterMembers(structuralNode, structuralNodeWithFilter)
            
    def explicitDimensionFilterMembers(self, structuralNode, structuralNodeWithFilter):
        for aspect in structuralNodeWithFilter.aspectsCovered():
            if isinstance(aspect, QName): # dimension
                break
        valueHeaders = set()
        if structuralNode is not None:
            headerValues = {}
            # check for dimension filter(s)
            dimFilterRels = structuralNodeWithFilter.definitionNode.filterRelationships
            if dimFilterRels:
                for rel in dimFilterRels:
                    dimFilter = rel.toModelObject
                    if dimFilter is not None:
                        for memberModel in dimFilter.memberProgs:
                                memQname = memberModel.qname
                                memConcept = self.modelXbrl.qnameConcepts.get(memQname)
                                if memConcept is not None and (not memberModel.axis or memberModel.axis.endswith('-self')):
                                    header = memConcept.label(lang=self.lang)
                                    valueHeaders.add(header)
                                    if rel.isUsable:
                                        headerValues[header] = memQname
                                    else:
                                        headerValues[header] = memConcept
                                elif memberModel.axis and memberModel.linkrole and memberModel.arcrole:
                                    # merge of pull request 42 acsone:TABLE_Z_AXIS_DESCENDANT_OR_SELF
                                    if memberModel.axis.endswith('-or-self'):
                                        searchAxis = memberModel.axis[:len(memberModel.axis)-len('-or-self')]
                                    else:
                                        searchAxis = memberModel.axis
                                    relationships = concept_relationships(self.rendrCntx, 
                                                         None, 
                                                         (memQname,
                                                          memberModel.linkrole,
                                                          memberModel.arcrole,
                                                          searchAxis),
                                                         False) # return flat list
                                    for rel in relationships:
                                        if rel.isUsable:
                                            header = rel.toModelObject.label(lang=self.lang)
                                            valueHeaders.add(header)
                                            headerValues[header] = rel.toModelObject.qname
            if not valueHeaders:
                relationships = concept_relationships(self.rendrCntx, 
                                     None, 
                                     (aspect,
                                      "XBRL-all-linkroles", # linkrole,
                                      "XBRL-dimensions",
                                      'descendant'),
                                     False) # return flat list
                for rel in relationships:
                    if (rel.arcrole in (XbrlConst.dimensionDomain, XbrlConst.domainMember)
                        and rel.isUsable):
                        header = rel.toModelObject.label(lang=self.lang)
                        valueHeaders.add(header)
                        headerValues[header] = rel.toModelObject.qname
            structuralNode.aspectEntryHeaderValues = headerValues
        return sorted(valueHeaders)
                
# import after other modules resolved to prevent circular references
from arelle.FunctionXfi import concept_relationships
