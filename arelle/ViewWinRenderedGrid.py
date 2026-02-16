'''
See COPYRIGHT.md for copyright information.
'''
import os, threading, time, logging, sys, traceback
from collections import OrderedDict, defaultdict
from tkinter import Menu, BooleanVar, font as tkFont
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectModelAspect
from arelle import (ViewWinTkTable, ModelDtsObject, ModelInstanceObject, XbrlConst,
                    ModelXbrl, Locale, FunctionXfi,
                    ValidateXbrlDimensions, ViewFileRenderedGrid, ViewFileRenderedLayout, ViewFileRenderedStructure)
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelValue import qname, QName
from arelle.rendering.RenderingResolution import RENDER_UNITS_PER_CHAR
from arelle.rendering.RenderingLayout import layoutTable
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelRenderingObject import (StrctMdlBreakdown, DefnMdlDefinitionNode,
                                         DefnMdlClosedDefinitionNode, DefnMdlAspectNode,
                                         OPEN_ASPECT_ENTRY_SURROGATE)
from arelle.formula.FormulaEvaluator import init as formulaEvaluatorInit, aspectMatches

from arelle.PrototypeInstanceObject import FactPrototype
from arelle.UITkTable import XbrlTable
from arelle.DialogNewFactItem import getNewFactItemOptions
from collections import defaultdict
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import eurofilingModelNamespace, eurofilingModelPrefix
from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
from arelle.XmlValidate import UNVALIDATED, validate as xmlValidate

TRACE_TK = False # print trace messages of tk table interface

try:
    from tkinter import ttk
    _Combobox = ttk.Combobox
except ImportError:
    from ttk import Combobox
    _Combobox = Combobox

emptyList = []

ENTRY_WIDTH_IN_CHARS = 12 # width of a data column entry cell in characters (nominal)
ENTRY_WIDTH_SCREEN_UNITS = 100
PADDING = 20 # screen units of padding between entry cells

qnPercentItemType = qname("{http://www.xbrl.org/dtr/type/numeric}num:percentItemType")
qnPureItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:pureItemType")
integerItemTypes = {"integerItemType", "nonPositiveIntegerItemType", "negativeIntegerItemType",
                    "longItemType", "intItemType", "shortItemType", "byteItemType",
                    "nonNegativeIntegerItemType", "unsignedLongItemType", "unsignedIntItemType",
                    "unsignedShortItemType", "unsignedByteItemType", "positiveIntegerItemType"}
TABLE_AXIS_ROLES = (XbrlConst.euTableAxis, XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD)

'''
Returns a tuple with all known table axis roles
'''
def getTableAxisArcroles():
    return TABLE_AXIS_ROLES

def viewRenderedGrid(modelXbrl, tabWin, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing rendering"))
    view = ViewRenderedGrid(modelXbrl, tabWin, lang)
    if not view.table.isInitialized: # unable to load or initialize tktable
        return None

    modelXbrl.modelManager.addToLog(_("Loading experimental table linkbase viewer"))

    view.blockMenuEvents = 1

    menu = view.contextMenu()
    optionsMenu = Menu(view.viewFrame, tearoff=0)
    optionsMenu.add_command(label=_("New fact item options"), underline=0, command=lambda: getNewFactItemOptions(modelXbrl.modelManager.cntlr, view.newFactItemOptions))
    optionsMenu.add_command(label=_("Open breakdown entry rows"), underline=0, command=view.setOpenBreakdownEntryRows)
    view.ignoreDimValidity.trace("w", view.viewReloadDueToMenuAction)
    optionsMenu.add_checkbutton(label=_("Ignore Dimensional Validity"), underline=0, variable=view.ignoreDimValidity, onvalue=True, offvalue=False)
    menu.add_cascade(label=_("Options"), menu=optionsMenu, underline=0)
    view.tablesMenu = Menu(view.viewFrame, tearoff=0)
    menu.add_cascade(label=_("Tables"), menu=view.tablesMenu, underline=0)
    view.tablesMenuLength = 0
    view.menuAddLangs()
    saveMenu = Menu(view.viewFrame, tearoff=0)
    saveMenu.add_command(label=_("HTML table"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(
        view=view, fileType="html", method=ViewFileRenderedGrid.viewRenderedGrid, caption=_("arelle - Save HTML-rendered Table")))
    saveMenu.add_command(label=_("Excel table"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(
        view=view, fileType="xlsx", method=ViewFileRenderedGrid.viewRenderedGrid, caption=_("arelle - Save Excel-rendered Table")))
    saveMenu.add_command(label=_("Layout model"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(
        view=view, fileType="xml", method=ViewFileRenderedLayout.viewRenderedLayout, caption=_("arelle - Save Table Layout Model")))
    saveMenu.add_command(label=_("Structural model"), underline=0, command=lambda: view.modelXbrl.modelManager.cntlr.fileSave(
        view=view, fileType="json", method=ViewFileRenderedStructure.viewRenderedStructuralModel, caption=_("arelle - Save Table Structural Model")))
    saveMenu.add_command(label=_("XBRL instance"), underline=0, command=view.saveInstance)
    menu.add_cascade(label=_("Save"), menu=saveMenu, underline=0)
    view.view()
    view.blockSelectEvent = 1
    view.blockViewModelObject = 0
    view.viewFrame.bind("<Enter>", view.cellEnter, '+')
    view.viewFrame.bind("<Leave>", view.cellLeave, '+')
    view.viewFrame.bind("<FocusOut>", view.onQuitView, '+')
    view.viewFrame.bind("<1>", view.onClick, '+') # does not currently work (since tktable changes)
    view.viewFrame.bind("<Configure>", view.onConfigure, '+') # frame resized, redo column header wrap length ratios
    view.blockMenuEvents = 0
    if "saveTableStructuralModel" in modelXbrl.modelManager.formulaOptions.parameterValues:
        ViewFileRenderedStructure.viewRenderedStructuralModel(modelXbrl,
              modelXbrl.modelManager.formulaOptions.parameterValues["saveTableStructuralModel"][1],
              lang=lang, sourceView=view)
    if "saveTableLayoutModel" in modelXbrl.modelManager.formulaOptions.parameterValues:
        ViewFileRenderedLayout.viewRenderedLayout(modelXbrl,
              modelXbrl.modelManager.formulaOptions.parameterValues["saveTableLayoutModel"][1],
              lang=lang, sourceView=view)
    if "saveHtmlTable" in modelXbrl.modelManager.formulaOptions.parameterValues:
        ViewFileRenderedGrid.viewRenderedGrid(modelXbrl,
              modelXbrl.modelManager.formulaOptions.parameterValues["saveHtmlTable"][1],
              lang=lang, sourceView=view)
    if "saveTable" in modelXbrl.modelManager.formulaOptions.parameterValues:
        ViewFileRenderedGrid.viewRenderedGrid(modelXbrl,
              modelXbrl.modelManager.formulaOptions.parameterValues["saveTable"][1],
              lang=lang, sourceView=view)
    return view

class ViewRenderedGrid(ViewWinTkTable.ViewTkTable):
    def __init__(self, modelXbrl, tabWin, lang):
        super(ViewRenderedGrid, self).__init__(modelXbrl, tabWin, _("Table"),
                                               False, lang, self.onQuitView)
        self.newFactItemOptions = ModelInstanceObject.NewFactItemOptions(xbrlInstance=modelXbrl)
        self.factPrototypes = []
        self.aspectEntryObjectIdsNode = {}
        self.aspectEntryObjectIdsCell = {}
        self.factPrototypeAspectEntryObjectIds = defaultdict(set)
        self.zHdrElts = None
        # context menu Boolean vars
        self.options = self.modelXbrl.modelManager.cntlr.config.setdefault("viewRenderedGridOptions", {})
        self.openBreakdownLines = self.options.setdefault("openBreakdownLines", 5) # ensure there is a default entry
        self.ignoreDimValidity = BooleanVar(value=self.options.setdefault("ignoreDimValidity",True))
        formulaEvaluatorInit() # one-time module initialization
        self.conceptMessageIssued = False
        self.tblMenuEntries = {}

    def close(self):
        super(ViewRenderedGrid, self).close()
        if self.modelXbrl:
            for fp in self.factPrototypes:
                fp.clear()
            self.factPrototypes = None
            self.aspectEntryObjectIdsNode.clear()
            self.aspectEntryObjectIdsCell.clear()
            self.rendrCntx = None # remove the reference but do not manipulate since it may still be in use and shared

    def loadTablesMenu(self):
        if not self.tblMenuEntries:
            self.tablesToELR = {}
            for lytMdlTableSet in self.lytMdlTblMdl.lytMdlTableSets:
                # table name
                modelRoleTypes = self.modelXbrl.roleTypes.get(lytMdlTableSet.srcLinkrole)
                if modelRoleTypes is not None and len(modelRoleTypes) > 0:
                    # roledefinition = modelRoleTypes[0].definition
                    roledefinition = self.modelXbrl.roleTypeDefinition(lytMdlTableSet.srcLinkrole, self.lang) # Definition in selected language
                    if roledefinition is None or roledefinition == "":
                        roledefinition = os.path.basename(lytMdlTableSet.srcLinkrole)
                    # add table to menu if there's any entry
                    self.tblMenuEntries[roledefinition] = lytMdlTableSet.srcLinkrole
                    # find table group object corresponding to this table for EBA filings from the root table object
                    for tableAxisArcrole in getTableAxisArcroles():
                        tblAxisRelSet = self.modelXbrl.relationshipSet(tableAxisArcrole, lytMdlTableSet.srcLinkrole)
                        if tblAxisRelSet and len(tblAxisRelSet.modelRelationships) > 0:
                            for table in tblAxisRelSet.rootConcepts:
                                # find a table group object corresponding to this table (ugly hack?)
                                for tableGroupConcept in self.modelXbrl.nameConcepts.get( table.id.replace("_tQ_", "_tgQ_"), () ):
                                    self.tablesToELR[tableGroupConcept.objectId()] = lytMdlTableSet.srcLinkrole
        self.tablesMenu.delete(0, self.tablesMenuLength)
        self.tablesMenuLength = 0
        self.tblELR = None
        for tblMenuEntry in sorted(self.tblMenuEntries.items()):
            tbl,elr = tblMenuEntry
            self.tablesMenu.add_command(label=tbl, command=lambda e=elr: self.view(viewTblELR=e)) # use this to activate profiling from menu selection:  , profile=True))
            self.tablesMenuLength += 1
            if self.tblELR is None:
                self.tblELR = elr # start viewing first ELR

    def viewReloadDueToMenuAction(self, *args):
        if not self.blockMenuEvents:
            # update config (config saved when exiting)
            self.options["ignoreDimValidity"] = self.ignoreDimValidity.get()
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
        startedAt = time.time()
        self.blockMenuEvents += 1
        if newInstance is not None:
            self.modelXbrl = newInstance # a save operation has created a new instance to use subsequently
            clearZchoices = False
        if viewTblELR:  # specific table selection
            self.tblELR = viewTblELR
            clearZchoices = True
        else:   # first or subsequenct reloading (language, dimensions, other change)
            clearZchoices = self.zHdrElts is None

        # remove old widgets
        self.viewFrame.clearGrid()

        layoutTable(self)

        lytMdlTblMdl = self.lytMdlTblMdl
        if len(lytMdlTblMdl.lytMdlTableSets) == 0 or len(lytMdlTblMdl.lytMdlTableSets[0].lytMdlTables) == 0:
            if TRACE_TK: print("no table to display")
            self.blockMenuEvents -= 1
            return # no table to display

        if clearZchoices: # also need first time initialization
            self.loadTablesMenu()  # load menus (and initialize if first time
            self.zHdrElts = None
        # identify tableSet in tableSets
        viewTblELR = viewTblELR or self.tblELR
        for lytMdlTableSet in self.lytMdlTblMdl.lytMdlTableSets:
            if lytMdlTableSet.srcLinkrole == viewTblELR:
                break
        self.lytMdlTable = lytMdlTableSet.lytMdlTables[0] # only one table in table set?
        self.zConstraints = set()
        self.xConstraints = defaultdict(set) # index by xColNum
        self.yConstraints = defaultdict(set) # index by yRowNum
        if self.zHdrElts is None:
            # each Z is a separate table in the outer table
            lytMdlZHdrs = self.lytMdlTable.lytMdlAxisHeaders("z")
            if lytMdlZHdrs is not None:
                lytMdlZHdrGroups = lytMdlZHdrs.lytMdlGroups
                numZtbls = self.lytMdlTable.numBodyCells("z") or 1 # must have at least 1 z entry
                self.zHdrElts = [OrderedDict() for i in range(numZtbls)]
                self.zAspectChoices = OrderedDict()
                for lytMdlZGrp in lytMdlZHdrGroups:
                    for lytMdlZHdr in lytMdlZGrp.lytMdlHeaders:
                        zRow = 0
                        if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlZHdr.lytMdlCells):
                            continue # skip header with only open aspect entry surrogate
                        for iz, lytMdlZCell in enumerate(lytMdlZHdr.lytMdlCells):
                            zConstraint = tuple(c.aspect for c in lytMdlZCell.lytMdlConstraints)
                            for iSpan in range(lytMdlZCell.span):
                                if not lytMdlZCell.rollup:
                                    zAspLbl = ", ".join(lbl[0] for lbl in lytMdlZCell.labels)
                                    self.zHdrElts[zRow][zConstraint] = zAspLbl
                                    if zConstraint not in self.zAspectChoices:
                                        self.zAspectChoices[zConstraint] = defaultdict(set)
                                    self.zAspectChoices[zConstraint][zAspLbl].add(zRow)
                                zRow += 1
                            self.zConstraints.update(lytMdlZCell.lytMdlConstraints)
            else:
                self.zHdrElts = [[]]
                numZtbls = 1
            self.zTbl = 0
            # get number of y header columns
            self.numZHdrs = self.numYHdrCols = self.numXHdrRows = 0
            self.dataRows = self.dataRows = 0
            lytMdlZHdrs = self.lytMdlTable.lytMdlAxisHeaders("z")
            if lytMdlZHdrs is not None:
                '''
                for lytMdlZGrp in lytMdlZHdrs.lytMdlGroups:
                    for lytMdlZHdr in lytMdlZGrp.lytMdlHeaders:
                        dataRow = 0
                        for lytMdlZCell in lytMdlZHdr.lytMdlCells:
                            dataRow += 1
                        if dataRow > self.numZHdrs:
                            self.numZHdrs = dataRow
                '''
                dataRow = len(lytMdlZHdrs.lytMdlGroups)
                if dataRow > self.numZHdrs:
                    self.numZHdrs = dataRow
            for lytMdlYGrp in getattr(self.lytMdlTable.lytMdlAxisHeaders("y"), "lytMdlGroups", []):
                for lytMdlYHdr in lytMdlYGrp.lytMdlHeaders:
                    self.numYHdrCols +=  lytMdlYHdr.maxNumLabels
                    dataRow = 0
                    if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlYHdr.lytMdlCells):
                        continue # skip header with only open aspect entry surrogate
                    for lytMdlYCell in lytMdlYHdr.lytMdlCells:
                        dataRow += lytMdlYCell.span
                    if dataRow > self.dataRows:
                        self.dataRows = dataRow
            for lytMdlXGrp in getattr(self.lytMdlTable.lytMdlAxisHeaders("x"), "lytMdlGroups", []):
                for lytMdlXHdr in lytMdlXGrp.lytMdlHeaders:
                    self.numXHdrRows += lytMdlXHdr.maxNumLabels
                    dataCol = 0
                    if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlXHdr.lytMdlCells):
                        continue # skip header with only open aspect entry surrogate
                    for lytMdlCell in lytMdlXHdr.lytMdlCells:
                        if lytMdlCell.isOpenAspectEntrySurrogate:
                            continue # strip all open aspect entry surrogates from layout model file
                        dataCol += lytMdlCell.span
                    if dataCol > self.dataRows:
                        self.dataRows = dataCol
        self.dataFirstRow = self.numZHdrs + self.numXHdrRows
        if TRACE_TK: print(f"resizeTable rows {self.dataFirstRow+self.dataRows} cols {self.numYHdrCols+self.dataRows} titleRows {self.dataFirstRow} titleColumns {self.numYHdrCols})")
        self.table.resizeTable(self.dataFirstRow+self.dataRows, self.numYHdrCols+self.dataRows, titleRows=self.dataFirstRow, titleColumns=self.numYHdrCols)

        try:
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
            if TRACE_TK: print(f"tbl hdr x {0} y {0} cols {self.numYHdrCols-1} rows {self.dataFirstRow - 1} value {lytMdlTableSet.label}")
            self.table.initHeaderCellValue(lytMdlTableSet.label,
                                           0, 0, self.numYHdrCols-1, self.dataFirstRow - 1,
                                           XbrlTable.TG_TOP_LEFT_JUSTIFIED)
            self.zAxis(clearZchoices, self.numXHdrRows)
            self.xAxis(self.numYHdrCols, self.colHdrTopRow)
            self.yAxis(0, self.dataFirstRow)
            for fp in self.factPrototypes: # dereference prior facts
                if fp is not None:
                    fp.clear()
            self.factPrototypes = []

            startedAt2 = time.time()
            if self.bodyCells(self.numYHdrCols, self.dataFirstRow):
                # has body cells
                #print("bodyCells {:.2f}secs ".format(time.time() - startedAt2) + self.roledefinition)
                self.table.clearModificationStatus()
                self.table.disableUnusedCells()
                self.table.resizeTableCells()

            # data cells
            #print("body cells done")
        except Exception as err:
            self.modelXbrl.error(f"exception: {type(err).__name__}",
                "Table Linkbase GUI rendering exception: %(error)s at %(traceback)s",
                modelXbrl=self.modelXbrl, error=err,
                traceback=traceback.format_exc())

        self.modelXbrl.profileStat("viewTable_" + os.path.basename(viewTblELR), time.time() - startedAt)
        self.blockMenuEvents -= 1

    def zAxis(self, clearZchoices, colSpan):
        if not self.zHdrElts or not self.zHdrElts[0]:
            return
        # create combo box cells for multiple choice elements
        for iZ, (aspect, aspectChoices) in enumerate(self.zAspectChoices.items()):
            values = [a for a in aspectChoices.keys() if a and a != OPEN_ASPECT_ENTRY_SURROGATE]
            if TRACE_TK: print(f"zAxis comboBox x {self.dataFirstCol} y {iZ} values {values} value {self.zHdrElts[self.zTbl][aspect]} colspan {colSpan}")
            if values:
                combobox = self.table.initHeaderCombobox(self.dataFirstCol,
                                                         iZ,
                                                         values=values,
                                                         value=self.zHdrElts[self.zTbl][aspect],
                                                         colspan=colSpan,
                                                         #selectindex=self.zBreakdownLeafNbr[breakdownRow],
                                                         comboboxselected=self.onZComboBoxSelected)
                combobox.zAspect = aspect

    def onZComboBoxSelected(self, event):
        combobox = event.widget
        comboAspect = combobox.zAspect
        comboVal = combobox.get()
        zTblsForAspect = self.zAspectChoices[combobox.zAspect][comboVal]
        # find zRow for the selected aspects
        for asp, aspVal in self.zHdrElts[self.zTbl].items():
            if asp != comboAspect:
                zTblsForAspect &= self.zAspectChoices[asp][aspVal]
        if len(zTblsForAspect) > 0:
            self.zTbl = next(iter(zTblsForAspect)) # get first of set
            self.view() # redraw grid

    def xAxis(self, leftCol, topRow):
        lytMdlXHdrs = self.lytMdlTable.lytMdlAxisHeaders("x")
        if lytMdlXHdrs is None:
            return
        firstColHdr = True
        yValue = topRow
        for lytMdlGrp in lytMdlXHdrs.lytMdlGroups:
            for iHdr, lytMdlHdr in enumerate(lytMdlGrp.lytMdlHeaders):
                if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlHdr.lytMdlCells):
                    continue # skip header with only open aspect entry surrogate
                for iLabel in range(lytMdlHdr.maxNumLabels):
                    xValue = leftCol
                    for lytMdlCell in lytMdlHdr.lytMdlCells:
                        if lytMdlCell.isOpenAspectEntrySurrogate:
                            continue # strip all open aspect entry surrogates from layout model file
                        if TRACE_TK: print(f"xAxis hdr x {xValue} y {yValue} cols {lytMdlCell.span} rows {1} isRollUpParent {lytMdlCell.rollup} value \"{lytMdlCell.labelXmlText(iLabel,'')}\"")
                        self.table.initHeaderCellValue(lytMdlCell.labelXmlText(iLabel,""),
                                                       xValue, yValue,
                                                       lytMdlCell.span - 1,
                                                       0, # rowspan - 1,
                                                       XbrlTable.TG_CENTERED,
                                                       #objectId=xStrctNode.objectId(),
                                                       hasTopBorder=not lytMdlCell.rollup,
                                                       hasBottomBorder = (
                                                           iHdr >= len(lytMdlGrp.lytMdlHeaders) - 1 or
                                                           not any(nxtHdrCell.rollup
                                                                   for nxtHdrCell in lytMdlGrp.lytMdlHeaders[iHdr+1].lytMdlCells))
                                                       )
                        self.xConstraints[xValue].update(lytMdlCell.lytMdlConstraints)
                        xValue += lytMdlCell.span or 1
                    yValue += 1

    def yAxis(self, leftCol, row):
        lytMdlYHdrs = self.lytMdlTable.lytMdlAxisHeaders("y")
        if lytMdlYHdrs is None:
            return
        xValue = leftCol
        for lytMdlGrp in lytMdlYHdrs.lytMdlGroups:
            for iHdr, lytMdlHdr in enumerate(lytMdlGrp.lytMdlHeaders):
                yRow = 0
                if all(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlHdr.lytMdlCells):
                    continue # skip header with only open aspect entry surrogate
                for lytMdlCell in lytMdlHdr.lytMdlCells:
                    if lytMdlCell.isOpenAspectEntrySurrogate:
                        continue # strip all open aspect entry surrogates from layout model file
                    for iLabel in range(lytMdlHdr.maxNumLabels):
                        if TRACE_TK: print(f"yAxis hdr x {xValue + iLabel} y {row + yRow} cols {1} rows {lytMdlCell.span} rollup {lytMdlCell.rollup} value \"{lytMdlCell.labelXmlText(iLabel,'')}\"")
                        self.table.initHeaderCellValue(lytMdlCell.labelXmlText(iLabel,""),
                                                       xValue + iLabel, row + yRow,
                                                       0, #columnspan + nestedColumnspan - 1,
                                                       lytMdlCell.span - 1, #nestedRowspan - 1,
                                                       XbrlTable.TG_LEFT_JUSTIFIED,
                                                       #objectId=yStrctNode.objectId(),
                                                       hasLeftBorder = not lytMdlCell.rollup,
                                                       hasRightBorder = (
                                                           iHdr >= len(lytMdlGrp.lytMdlHeaders) - 1 or
                                                           not any(nxtHdrCell.rollup
                                                                   for nxtHdrCell in lytMdlGrp.lytMdlHeaders[iHdr+1].lytMdlCells))
                                                       #width=3 if lytMdlCell.rollup else None
                                                       )
                        self.yConstraints[row + yRow].update(lytMdlCell.lytMdlConstraints)
                    yRow += lytMdlCell.span
                xValue += lytMdlHdr.maxNumLabels

    def getbackgroundColor(self, factPrototype):
        bgColor = XbrlTable.TG_BG_DEFAULT # default monetary
        concept = factPrototype.concept
        if concept == None:
            return bgColor
        isNumeric = concept.isNumeric
        # isMonetary = concept.isMonetary
        isInteger = concept.baseXbrliType in integerItemTypes
        isPercent = concept.typeQname in (qnPercentItemType, qnPureItemType)
        isString = concept.baseXbrliType in ("stringItemType", "normalizedStringItemType")
        isDate = concept.baseXbrliType in ("dateTimeItemType", "dateItemType")
        if isNumeric:
            if concept.isShares or isInteger:
                bgColor = XbrlTable.TG_BG_ORANGE
            elif isPercent:
                bgColor = XbrlTable.TG_BG_YELLOW
            # else assume isMonetary
        elif isDate:
            bgColor = XbrlTable.TG_BG_GREEN
        elif isString:
            bgColor = XbrlTable.TG_BG_VIOLET
        return bgColor;

    def bodyCells(self, leftCol, topRow):
        if not self.lytMdlTable.lytMdlBodyChildren:
            return False # no body cells
        lytMdlZBodyCell = self.lytMdlTable.lytMdlBodyChildren[0] # examples only show one z cell despite number of tables
        if self.zTbl >= len(lytMdlZBodyCell.lytMdlBodyChildren):
            return False # no body cells for selected z table
        lytMdlYBodyCell = lytMdlZBodyCell.lytMdlBodyChildren[self.zTbl]
        yRowNum = topRow
        for lytMdlXBodyCell in lytMdlYBodyCell.lytMdlBodyChildren:
            if not any(lytMdlCell.isOpenAspectEntrySurrogate for lytMdlCell in lytMdlXBodyCell.lytMdlBodyChildren):
                for iBodyCell, lytMdlCell in enumerate(lytMdlXBodyCell.lytMdlBodyChildren):
                    xColNum = leftCol + iBodyCell
                    if lytMdlCell.isOpenAspectEntrySurrogate:
                        continue
                    justify = "left"
                    f = None # should be a fact prototype for cell with no bound facts and not blocked
                    for f, v, justify in lytMdlCell.facts:
                        break;
                    #colElt = etree.SubElement(rowElt, "{http://www.w3.org/1999/xhtml}td",
                    #                          attrib={"class":"cell",
                    #                                  "style":f"text-align:{justify};width:8em;"}
                    #                 ).text = "\n".join(v for f, v, justify in lytMdlCell.facts)
                    if f is not None:
                        fp = f
                        value = v
                        objectId = f.objectId()
                    else:
                        cellAspectValues = dict((c.aspect, c.value)
                                                for aC in (self.zConstraints, self.xConstraints[xColNum], self.yConstraints[yRowNum])
                                                for c in aC)
                        fp = FactPrototype(self, cellAspectValues)
                        value = None
                        objectId = "f{0}".format(len(self.factPrototypes))
                        self.factPrototypes.append(fp)  # for property views
                        for aspect, aspectValue in cellAspectValues.items():
                            if isinstance(aspectValue, str) and aspectValue.startswith(OPEN_ASPECT_ENTRY_SURROGATE):
                                self.factPrototypeAspectEntryObjectIds[objectId].add(aspectValue)
                    if fp is not None and fp.concept is not None and not fp.concept.isAbstract:
                        modelConcept = fp.concept
                        if (justify is None) and modelConcept is not None:
                            justify = XbrlTable.TG_RIGHT_JUSTIFIED if modelConcept.isNumeric else XbrlTable.TG_LEFT_JUSTIFIED
                        if modelConcept is not None and modelConcept.isEnumeration:
                            myValidationObject = ValidateXbrl(self.modelXbrl)
                            myValidationObject.modelXbrl = self.modelXbrl
                            enumerationSet = ValidateXbrlDimensions.usableEnumerationMembers(myValidationObject, modelConcept)
                            enumerationDict = dict()
                            for enumerationItem in enumerationSet:
                                # we need to specify the concept linkrole to sort out between possibly many different labels
                                enumerationDict[enumerationItem.label(linkrole=modelConcept.enumLinkrole)] = enumerationItem.qname
                            enumerationValues = sorted(list(enumerationDict.keys()))
                            enumerationQNameStrings = [""]+list(str(enumerationDict[enumerationItem]) for enumerationItem in enumerationValues)
                            enumerationValues = [""]+enumerationValues
                            try:
                                selectedIdx = enumerationQNameStrings.index(value)
                                effectiveValue = enumerationValues[selectedIdx]
                            except ValueError:
                                effectiveValue = enumerationValues[0]
                                selectedIdx = 0
                            if TRACE_TK: print(f"body comboBox enums x {xColNum} y {yRowNum} values {enumerationValues} value {effectiveValue}")
                            self.table.initCellCombobox(effectiveValue,
                                                        enumerationValues,
                                                        xColNum,
                                                        yRowNum,
                                                        objectId=objectId,
                                                        selectindex=selectedIdx,
                                                        codes=enumerationDict)
                        elif modelConcept is not None and modelConcept.type is not None and modelConcept.type.qname == XbrlConst.qnXbrliQNameItemType:
                            if eurofilingModelPrefix in modelConcept.nsmap and modelConcept.nsmap.get(eurofilingModelPrefix) == eurofilingModelNamespace:
                                hierarchy = modelConcept.get("{" + eurofilingModelNamespace + "}" + "hierarchy", None)
                                domainQNameAsString = modelConcept.get("{" + eurofilingModelNamespace + "}" + "domain", None)
                                if hierarchy is not None and domainQNameAsString is not None:
                                    newAspectValues = [""]
                                    newAspectQNames = dict()
                                    newAspectQNames[""] = None
                                    domPrefix, _, domLocalName = domainQNameAsString.strip().rpartition(":")
                                    domNamespace = modelConcept.nsmap.get(domPrefix)
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
                                self.table.initCellValue(value,
                                                         xColNum,
                                                         yRowNum,
                                                         justification=justify,
                                                         objectId=objectId,
                                                         backgroundColourTag=self.getbackgroundColor(fp))
                            else:
                                qNameValues = newAspectValues
                                try:
                                    selectedIdx = qNameValues.index(value)
                                    effectiveValue = value
                                except ValueError:
                                    effectiveValue = qNameValues[0]
                                    selectedIdx = 0
                                if TRACE_TK: print(f"body comboBox qnames x {xColNum} y {yRowNum} values {qNameValues} value {effectiveValue}")
                                self.table.initCellCombobox(effectiveValue,
                                                            qNameValues,
                                                            xColNum,
                                                            yRowNum,
                                                            objectId=objectId,
                                                            selectindex=selectedIdx,
                                                            codes=newAspectQNames)
                        elif modelConcept is not None and modelConcept.type is not None and modelConcept.type.qname == XbrlConst.qnXbrliBooleanItemType:
                            booleanValues = ["",
                                             XbrlConst.booleanValueTrue,
                                             XbrlConst.booleanValueFalse]
                            try:
                                selectedIdx = booleanValues.index(value)
                                effectiveValue = value
                            except ValueError:
                                effectiveValue = booleanValues[0]
                                selectedIdx = 0
                            if TRACE_TK: print(f"body comboBox bools x {xColNum} y {yRowNum} values {booleanValues} value {effectiveValue}")
                            self.table.initCellCombobox(effectiveValue,
                                                        booleanValues,
                                                        xColNum,
                                                        yRowNum,
                                                        objectId=objectId,
                                                        selectindex=selectedIdx)
                        else:
                            if TRACE_TK: print(f"body cell x {xColNum} y {yRowNum} value {value}")
                            self.table.initCellValue(value,
                                                     xColNum,
                                                     yRowNum,
                                                     justification=justify,
                                                     objectId=objectId,
                                                     backgroundColourTag=self.getbackgroundColor(fp))
                yRowNum += 1
        return True # has body cells

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
        # triggered on grid frame enter (not cell enter)
        self.blockSelectEvent = 0
        self.modelXbrl.modelManager.cntlr.currentView = self

    def cellLeave(self, *args):
        # triggered on grid frame leave (not cell leave)
        self.blockSelectEvent = 1

    # this method is not currently used
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
                elif isinstance(modelObject, ModelDtsObject.ModelRoleType):
                    objectId = self.modelXbrl.roleTypeDefinition(modelObject.roleURI, self.lang)
                else:
                    objectId = modelObject.objectId()
                if objectId in self.tablesToELR:
                    self.view(viewTblELR=self.tablesToELR[objectId])
                    try:
                        self.modelXbrl.modelManager.cntlr.currentView = self.modelXbrl.guiViews.tableView
                        # force focus (synch) on the corresponding "Table" tab (useful in case of several instances)
                        self.modelXbrl.guiViews.tableView.tabWin.select(str(self.modelXbrl.guiViews.tableView.viewFrame))
                    except:
                        pass
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
                self.setHeightAndWidth()
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
        # this method is passed as callback when creating the view
        # (to ScrolledTkTableFrame and then to XbrlTable that will monitor cell operations)
        self.updateInstanceFromFactPrototypes()
        self.updateProperties()

    def hasChangesToSave(self):
        return len(self.table.modifiedCells)

    def updateProperties(self):
        if self.modelXbrl is not None:
            modelXbrl =  self.modelXbrl
            # make sure we handle an instance
            if modelXbrl.modelDocument.type == ModelDocumentType.INSTANCE:
                tbl = self.table
                # get coordinates of last currently operated cell
                coordinates = tbl.getCurrentCellCoordinates()
                if coordinates is not None:
                    # get object identifier from its coordinates in the current table
                    objId = tbl.getObjectId(coordinates)
                    if objId is not None and len(objId) > 0:
                        if objId and objId[0] == "f":
                            # fact prototype
                            viewableObject = self.factPrototypes[int(objId[1:])]
                        elif objId[0] != "a":
                            # instance fact
                            viewableObject = self.modelXbrl.modelObject(objId)
                        else:
                            return
                        modelXbrl.viewModelObject(viewableObject)


    def updateInstanceFromFactPrototypes(self):
        # Only update the model if it already exists
        if self.modelXbrl is not None \
           and self.modelXbrl.modelDocument.type == ModelDocumentType.INSTANCE:
            instance = self.modelXbrl
            cntlr =  instance.modelManager.cntlr
            newCntx = ModelXbrl.AUTO_LOCATE_ELEMENT
            newUnit = ModelXbrl.AUTO_LOCATE_ELEMENT
            tbl = self.table
            # check user keyed changes to aspects
            aspectEntryChanges = {}  # index = widget ID,  value = widget contents
            aspectEntryChangeIds = aspectEntryChanges.keys()
            for modifiedCell in tbl.getCoordinatesOfModifiedCells():
                objId = tbl.getObjectId(modifiedCell)
                if objId is not None and len(objId)>0:
                    if tbl.isHeaderCell(modifiedCell):
                        if objId[0] == OPEN_ASPECT_ENTRY_SURROGATE:
                            aspectEntryChanges[objId] = tbl.getTableValue(modifiedCell)
                    else:
                        # check user keyed changes to facts
                        cellIndex = str(modifiedCell)
                        comboboxCells = tbl.window_names(cellIndex)
                        if comboboxCells is not None and len(comboboxCells)>0:
                            comboName = tbl.window_cget(cellIndex, '-window')
                            combobox = cntlr.parent.nametowidget(comboName)
                        else:
                            combobox = None
                        if isinstance(combobox, _Combobox):
                            codeDict = combobox.codes
                            if len(codeDict)>0: # the drop-down list shows labels, we want to have the actual values
                                bodyCellValue = tbl.getTableValue(modifiedCell)
                                value = codeDict.get(bodyCellValue, None)
                                if value is None:
                                    value = bodyCellValue # this must be a qname!
                            else:
                                value = tbl.getTableValue(modifiedCell)
                        else:
                            value = tbl.getTableValue(modifiedCell)
                        objId = tbl.getObjectId(modifiedCell)
                        if objId is not None and len(objId)>0:
                            if objId[0] == "f":
                                factPrototypeIndex = int(objId[1:])
                                factPrototype = self.factPrototypes[factPrototypeIndex]
                                concept = factPrototype.concept
                                if concept is None:
                                    if not self.conceptMessageIssued:
                                        # This should be removed once cells have been disabled until every needed selection is done
                                        self.conceptMessageIssued = True
                                        self.modelXbrl.modelManager.cntlr.showMessage(_("Please make sure every Z axis selection is done"))
                                    return
                                else:
                                    self.conceptMessageIssued = False
                                entityIdentScheme = self.newFactItemOptions.entityIdentScheme
                                entityIdentValue = self.newFactItemOptions.entityIdentValue
                                periodType = concept.periodType
                                periodStart = self.newFactItemOptions.startDateDate if periodType == "duration" else None
                                periodEndInstant = self.newFactItemOptions.endDateDate
                                qnameDims = factPrototype.context.qnameDims
                                newAspectValues = self.newFactOpenAspects(objId)
                                if newAspectValues is None:
                                    self.modelXbrl.modelManager.showStatus(_("Some open values are missing in an axis, the save is incomplete"), 5000)
                                    continue
                                qnameDims.update(newAspectValues)
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
                                    cntxId = newCntx.id # need new context
                                # new context
                                if concept.isNumeric:
                                    if concept.isMonetary:
                                        unitMeasure = qname(XbrlConst.iso4217, self.newFactItemOptions.monetaryUnit)
                                        unitMeasure.prefix = "iso4217" # want to save with a recommended prefix
                                        decimals = self.newFactItemOptions.monetaryDecimals
                                    elif concept.isShares:
                                        unitMeasure = XbrlConst.qnXbrliShares
                                        decimals = self.newFactItemOptions.nonMonetaryDecimals
                                    else:
                                        unitMeasure = XbrlConst.qnXbrliPure
                                        decimals = self.newFactItemOptions.nonMonetaryDecimals
                                    prevUnit = instance.matchUnit([unitMeasure], [])
                                    if prevUnit is not None:
                                        unitId = prevUnit.id
                                    else:
                                        newUnit = instance.createUnit([unitMeasure], [], afterSibling=newUnit)
                                        unitId = newUnit.id
                                attrs = [("contextRef", cntxId)]
                                if concept.isNumeric:
                                    attrs.append(("unitRef", unitId))
                                    attrs.append(("decimals", decimals))
                                    value = Locale.atof(self.modelXbrl.locale, value, str.strip)
                                newFact = instance.createFact(concept.qname, attributes=attrs, text=value)
                                tbl.setObjectId(modifiedCell,
                                                newFact.objectId()) # switch cell to now use fact ID
                                if self.factPrototypes[factPrototypeIndex] is not None:
                                    self.factPrototypes[factPrototypeIndex].clear()
                                self.factPrototypes[factPrototypeIndex] = None #dereference fact prototype
                            elif objId[0] != "a": # instance fact, not prototype
                                fact = self.modelXbrl.modelObject(objId)
                                if isinstance(fact, ModelInstanceObject.ModelFact):
                                    if fact.concept.isNumeric:
                                        value = Locale.atof(self.modelXbrl.locale, value, str.strip)
                                        if fact.concept.isMonetary:
                                            unitMeasure = qname(XbrlConst.iso4217, self.newFactItemOptions.monetaryUnit)
                                            unitMeasure.prefix = "iso4217" # want to save with a recommended prefix
                                            decimals = self.newFactItemOptions.monetaryDecimals
                                        elif fact.concept.isShares:
                                            unitMeasure = XbrlConst.qnXbrliShares
                                            decimals = self.newFactItemOptions.nonMonetaryDecimals
                                        else:
                                            unitMeasure = XbrlConst.qnXbrliPure
                                            decimals = self.newFactItemOptions.nonMonetaryDecimals
                                    if fact.value != str(value):
                                        if fact.isNil != (not value):
                                            fact.isNil = not value
                                            if fact.isNil:
                                                pass
                                                #TODO: clear out nil facts
                                        if fact.concept.isNumeric and (not fact.isNil): # if nil, there is no need to update these values
                                            fact.decimals = decimals
                                            prevUnit = instance.matchUnit([unitMeasure], [])
                                            if prevUnit is not None:
                                                unitId = prevUnit.id
                                            else:
                                                newUnit = instance.createUnit([unitMeasure], [], afterSibling=newUnit)
                                                unitId = newUnit.id
                                            fact.unitID = unitId
                                        fact.text = str(value)
                                        instance.setIsModified()
                                        fact.xValid = UNVALIDATED
                                        xmlValidate(instance, fact)
            tbl.clearModificationStatus()

    def saveInstance(self, newFilename=None, onSaved=None):
        if (not self.newFactItemOptions.entityIdentScheme or  # not initialized yet
            not self.newFactItemOptions.entityIdentValue or
            not self.newFactItemOptions.startDateDate or not self.newFactItemOptions.endDateDate):
            if not getNewFactItemOptions(self.modelXbrl.modelManager.cntlr, self.newFactItemOptions):
                return # new instance not set
        # newFilename = None # only used when a new instance must be created

        self.updateInstanceFromFactPrototypes()
        if self.modelXbrl.modelDocument.type != ModelDocumentType.INSTANCE and newFilename is None:
            newFilename = self.modelXbrl.modelManager.cntlr.fileSave(view=self, fileType="xbrl")
            if not newFilename:
                return  # saving cancelled
        # continue saving in background
        thread = threading.Thread(target=lambda: self.backgroundSaveInstance(newFilename, onSaved))
        thread.daemon = True
        thread.start()


    def backgroundSaveInstance(self, newFilename=None, onSaved=None):
        cntlr = self.modelXbrl.modelManager.cntlr
        if newFilename and self.modelXbrl.modelDocument.type != ModelDocumentType.INSTANCE:
            self.modelXbrl.modelManager.showStatus(_("creating new instance {0}").format(os.path.basename(newFilename)))
            self.modelXbrl.modelManager.cntlr.waitForUiThreadQueue() # force status update
            self.modelXbrl.createInstance(newFilename) # creates an instance as this modelXbrl's entrypoint
        instance = self.modelXbrl
        cntlr.showStatus(_("Saving {0}").format(instance.modelDocument.basename))
        cntlr.waitForUiThreadQueue() # force status update

        self.updateInstanceFromFactPrototypes()
        instance.saveInstance(overrideFilepath=newFilename) # may override prior filename for instance from main menu
        cntlr.addToLog(_("{0} saved").format(newFilename if newFilename is not None else instance.modelDocument.filepath))
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
            # is aspect in a childStrctNode?
            if value is not None and OPEN_ASPECT_ENTRY_SURROGATE in aspectObjId and len(value)==0:
                return None # some values are missing!
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
        while (n.strctMdlParentNode is not None):
            depth += 1
            root = n = n.strctMdlParentNode

        headers = set()
        headerValues = {}
        def getHeaders(n, d):
            for childStrctNode in n.strctMdlChildNodes:
                if d == depth:
                    h = childStrctNode.header(lang=self.lang,
                                                   returnGenLabel=False,
                                                   returnMsgFormatString=False)
                    if not childStrctNode.isEntryPrototype() and h:
                        headerValues[h] = childStrctNode.aspectValue(aspect)
                        headers.add(h)
                else:
                    getHeaders(childStrctNode, d+1)
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
            dimFilterRels = structuralNodeWithFilter.defnMdlNode.filterRelationships
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
                                if memberModel.axis and memberModel.linkrole and memberModel.arcrole:
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
