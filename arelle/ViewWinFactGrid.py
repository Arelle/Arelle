'''
See COPYRIGHT.md for copyright information.
'''
import datetime
from tkinter import Menu, constants, BooleanVar
from arelle import ViewWinGrid, ModelObject, XbrlConst
from arelle.UiUtil import (gridBorder, gridSpacer, gridHdr, gridCell, gridCombobox,
                     label, checkbox,
                     TOPBORDER, LEFTBORDER, RIGHTBORDER, BOTTOMBORDER, CENTERCELL)
from collections import defaultdict

def viewFactsGrid(modelXbrl, tabWin, header="Fact Grid", arcrole=XbrlConst.parentChild, linkrole=None, linkqname=None, arcqname=None, lang=None):
    modelXbrl.modelManager.showStatus(_("viewing facts"))
    view = ViewFactsGrid(modelXbrl, tabWin, header, arcrole, linkrole, linkqname, arcqname, lang)
    if view.tableSetup():

        view.ignoreDims = BooleanVar(value=False)
        view.showDimDefaults = BooleanVar(value=False)

        # context menu
        menu = view.contextMenu()
        optionsMenu = Menu(view.viewFrame, tearoff=0)
        view.ignoreDims.trace("w", view.view)
        optionsMenu.add_checkbutton(label=_("Ignore Dimensions"), underline=0, variable=view.ignoreDims, onvalue=True, offvalue=False)
        view.showDimDefaults.trace("w", view.view)
        optionsMenu.add_checkbutton(label=_("Show Dimension Defaults"), underline=0, variable=view.showDimDefaults, onvalue=True, offvalue=False)
        menu.add_cascade(label=_("Options"), menu=optionsMenu, underline=0)
        menu.add_cascade(label=_("Close"), underline=0, command=view.close)
        view.menuAddLangs()
        view.view()
        view.blockSelectEvent = 1
        view.blockViewModelObject = 0
        view.viewFrame.bind("<Enter>", view.cellEnter, '+')
        view.viewFrame.bind("<Leave>", view.cellLeave, '+')

class ViewFactsGrid(ViewWinGrid.ViewGrid):
    def __init__(self, modelXbrl, tabWin, header, arcrole, linkrole=None, linkqname=None, arcqname=None, lang=None):
        super(ViewFactsGrid, self).__init__(modelXbrl, tabWin, header, True, lang)
        self.arcrole = arcrole
        self.linkrole = linkrole
        self.linkqname = linkqname
        self.arcqname = arcqname

    def tableSetup(self):
        self.blockSelectEvent = 1
        self.blockViewModelObject = 0
        self.tag_has = defaultdict(list) # temporary until Tk 8.6
        # relationship set based on linkrole parameter, to determine applicable linkroles
        relationshipSet = self.modelXbrl.relationshipSet(self.arcrole, self.linkrole, self.linkqname, self.arcqname)
        if not relationshipSet:
            self.modelXbrl.modelManager.addToLog(_("no relationships for {0}").format(self.arcrole))
            return False

        factConcepts = set(fact.concept for fact in self.modelXbrl.factsInInstance).append(fact)

        definedLinkroles = []
        for linkrole in set(rel.linkrole
                            for rel in relationshipSet.modelRelationships
                            if rel.fromModelObject in factConcepts or rel.toModelObject in factConcepts):
            modelRoleTypes = self.modelXbrl.roleTypes.get(linkrole)
            if modelRoleTypes:
                roledefinition = modelRoleTypes[0].definition
                if not roledefinition:
                    roledefinition = linkrole
            else:
                roledefinition = linkrole
            definedLinkroles.append((roledefinition,linkrole))
        definedLinkroles.sort()
        if not definedLinkroles:
            return False
        self.linkrole = definedLinkroles[0][1]
        self.linkroleSetup()
        return True

    def linkroleSetup(self):
        # determine facs in this linkrole
        relationshipSet = self.modelXbrl.relationshipSet(self.arcrole, self.linkrole, self.linkqname, self.arcqname)
        conceptsInLinkrole = set()
        for rel in relationshipSet:
            conceptsInLinkrole.add(rel.fromModelObject)
            conceptsInLinkrole.add(rel.toModelObject)

        # set up facts
        self.conceptFacts = defaultdict(list)
        self.periodContexts = defaultdict(set)
        contextStartDatetimes = {}
        for fact in self.modelXbrl.facts:
            if fact.concept in conceptsInLinkrole:
                self.conceptFacts[fact.qname].append(fact)
                context = fact.context
                if context.isForeverPeriod:
                    contextkey = datetime.datetime(datetime.MINYEAR,1,1)
                else:
                    contextkey = context.endDatetime
                objectId = context.objectId()
                self.periodContexts[contextkey].add(objectId)
                if context.isStartEndPeriod:
                    contextStartDatetimes[objectId] = context.startDatetime

        # sort contexts by period
        self.periodKeys = list(self.periodContexts.keys())
        self.periodKeys.sort()
        # set up treeView widget and tabbed pane
        columnIds = []
        columnIdHeadings = []
        self.contextColId = {}
        self.startdatetimeColId = {}
        self.numCols = 1
        for periodKey in self.periodKeys:
            colId = "#{0}".format(self.numCols)
            columnIds.append(colId)
            columnIdHeadings.append((colId,periodKey))
            for contextId in self.periodContexts[periodKey]:
                self.contextColId[contextId] = colId
                if contextId in contextStartDatetimes:
                    self.startdatetimeColId[contextStartDatetimes[contextId]] = colId
            self.numCols += 1
        self.treeView["columns"] = columnIds
        for colId, colHeading in columnIdHeadings:
            self.treeView.column(colId, width=60, anchor="w")
            if colHeading.year == datetime.MINYEAR:
                date = "forever"
            else:
                date = (colHeading - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            self.treeView.heading(colId, text=date)
        return True

    def view(self):
        # remove old widgets
        self.viewFrame.clearGrid()

        # table name
        self.zAxisRows = 1
        self.dataCols = 0
        self.dataRows = 0
        self.colHdrRows = 0
        self.dataRows = 0
        xFilters = []

        self.analyzeColHdrs(self.parentFacts, 1)
        self.colHdrTopRow = self.zAxisRows + (2 if self.zAxisRows else 1)
        self.dataFirstRow = self.colHdrTopRow + self.colHdrRows
        self.dataFirstCol = 2

        gridHdr(self.gridTblHdr, 0, 0,
                self.tupleFact.concept.label(lang=self.lang),
                anchor="nw",
                #columnspan=(self.dataFirstCol - 1),
                rowspan=(self.dataFirstRow),
                wraplength=200)
        self.zAxis()
        self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1,
                   self.tupleFact.modelTupleFacts, xFilters, True, True, True)
        self.bodyCells(self.dataFirstRow, 0, self.parentFacts, xFilters, True)

        # data cells

        #self.gridView.config(scrollregion=self.gridView.bbox(constants.ALL))

    def analyzeColHdrs(self, tupleFacts, depth):
        for xAxisChildObj in tupleFacts:
            isItem = xAxisChildObj.isItem
            if isItem:
                self.dataCols += 1
            if depth > self.colHdrRows: self.colHdrRows = depth
            self.analyzeColHdrs(xAxisChildObj.modelTupleFacts, depth+1) #recurse

    def zAxis(self, row):
        if row is not None:
            gridBorder(self.gridColHdr, self.dataFirstCol, row, TOPBORDER, columnspan=2)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, LEFTBORDER)
            gridBorder(self.gridColHdr, self.dataFirstCol, row, RIGHTBORDER, columnspan=2)
            gridHdr(self.gridColHdr, self.dataFirstCol, row,
                    "Link role (schedule)",
                    anchor="w", columnspan=2,
                    wraplength=200,
                    objectId="zAxisLabel",
                    onClick=self.onClick)
            self.combobox = gridCombobox(
                         self.gridColHdr, self.dataFirstCol + 2, row,
                         values=[definition for definition,linkrole in self.definedLinkroles],
                         selectindex=self.zFilterIndex,
                         comboboxselected=self.comboBoxSelected)
            gridBorder(self.gridColHdr, self.dataFirstCol + 2, row, RIGHTBORDER)
            row += 1


    def comboBoxSelected(self, *args):
        self.linkrole = self.definedLinkroles[self.combobox.valueIndex][1]
        self.view() # redraw grid


    def xAxis(self, leftCol, topRow, rowBelow, tupleFacts, xFilters, childrenFirst, renderNow, atTop):
        parentRow = rowBelow
        noDescendants = True
        rightCol = leftCol
        widthToSpanParent = 0
        sideBorder = not xFilters
        if atTop and sideBorder and childrenFirst:
            gridBorder(self.gridColHdr, self.dataFirstCol, 1, LEFTBORDER, rowspan=self.dataFirstRow)
        for xAxisChildObj in tupleFacts:
            isItem = xAxisChildObj.isItem
            noDescendants = False
            rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xAxisChildObj.modelTupleFacts, xFilters, # nested items before totals
                                                        childrenFirst, childrenFirst, False)
            if row - 1 < parentRow:
                parentRow = row - 1
            #if not leafNode:
            #    rightCol -= 1
            widthToSpanParent += width
            label = xAxisChildObj.concept.label(lang=self.lang)
            if childrenFirst:
                thisCol = rightCol
                sideBorder = RIGHTBORDER
            else:
                thisCol = leftCol
                sideBorder = LEFTBORDER
            if renderNow:
                columnspan = (rightCol - leftCol + (1 if isItem else 0))
                gridBorder(self.gridColHdr, leftCol, topRow, TOPBORDER, columnspan=columnspan)
                gridBorder(self.gridColHdr, leftCol, topRow,
                           sideBorder, columnspan=columnspan,
                           rowspan=(rowBelow - topRow + 1) )
                gridHdr(self.gridColHdr, leftCol, topRow,
                        label if label else "         ",
                        anchor="center",
                        columnspan=(rightCol - leftCol + (1 if isItem else 0)),
                        rowspan=(row - topRow + 1) if leafNode else 1,
                        wraplength=width,
                        objectId=xAxisChildObj.objectId(),
                        onClick=self.onClick)
                if isItem:
                    gridBorder(self.gridColHdr, thisCol, self.dataFirstRow - 1, BOTTOMBORDER)
                    xFilters.append(xAxisChildObj.concept,
                                     )
            if isItem:
                rightCol += 1
            if renderNow and not childrenFirst:
                self.xAxis(leftCol + (1 if isItem else 0), topRow + 1, rowBelow, xAxisChildObj.modelTupleFacts, xFilters, childrenFirst, True, False) # render on this pass
            leftCol = rightCol
        if atTop and sideBorder and not childrenFirst:
            gridBorder(self.gridColHdr, rightCol - 1, 1, RIGHTBORDER, rowspan=self.dataFirstRow)
        return (rightCol, parentRow, widthToSpanParent, noDescendants)

    def tupleDescendant(self, tupleParent, descendantConcept):
        for tupleChild in tupleParent.modelTupleFacts:
            if tupleChild.concept == descendantConcept:
                return tupleChild
            tupleDescendant = self.tupleDescendant(tupleChild, descendantConcept)
            if tupleDescendant:
                return tupleDescendant
        return None

    def bodyCells(self, row, indent, tupleFacts, xFilters, zFilters):
        for modelTupleFact in tupleFacts:
            if modelTupleFact.concept == self.tupleConcept:
                for i, xColConcept in enumerate(xFilters):
                    fact = self.tupleDescendant(modelTupleFact, xColConcept)
                    if fact:
                        value = fact.effectiveValue
                        objectId = fact.objectId()
                        justify = "right" if fact.isNumeric else "left"
                    else:
                        value = None
                        objectId = None
                    if value is not None:
                        gridCell(self.gridBody, self.dataFirstCol + i, row, value, justify=justify, width=12,
                                 objectId=objectId, onClick=self.onClick)
                    else:
                        gridSpacer(self.gridBody, self.dataFirstCol + i, row, CENTERCELL)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, RIGHTBORDER)
                    gridSpacer(self.gridBody, self.dataFirstCol + i, row, BOTTOMBORDER)
                row += 1
        return row

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
