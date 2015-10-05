'''
Created on May 12, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ViewWinGrid, )
from arelle.UiUtil import (gridBorder, gridSpacer, gridHdr, gridCell, 
                     label, 
                     TOPBORDER, LEFTBORDER, RIGHTBORDER, BOTTOMBORDER, CENTERCELL)

def viewTuplesGrid(modelXbrl, tabWin, tupleObjectId, lang=None):
    modelTuple = modelXbrl.modelObject(tupleObjectId)
    if modelTuple is not None:
        modelXbrl.modelManager.showStatus(_("viewing tuples {0}").format(modelTuple.localName))
        parentFacts = modelXbrl.facts
        try: # check if possible to get parent tuple facts
            parentFacts = modelTuple.getparent().modelTupleFacts
        except:
            pass
        view = ViewTuplesGrid(modelXbrl, tabWin, modelTuple, parentFacts, lang)
    
        # context menu
        menu = view.contextMenu()
        menu.add_cascade(label=_("Close"), underline=0, command=view.close)
        view.menuAddLangs()
        view.view()
        view.blockSelectEvent = 1
        view.blockViewModelObject = 0
        view.viewFrame.bind("<Enter>", view.cellEnter, '+')
        view.viewFrame.bind("<Leave>", view.cellLeave, '+')
        return view
    else:
        modelXbrl.modelManager.showStatus(_("viewing tuples requires selecting the tuple to report"), clearAfter=2000)
            
class ViewTuplesGrid(ViewWinGrid.ViewGrid):
    def __init__(self, modelXbrl, tabWin, tupleFact, parentFacts, lang):
        super(ViewTuplesGrid, self).__init__(modelXbrl, tabWin, "Tuples", True, lang)
        self.tupleFact = tupleFact
        self.tupleConcept = tupleFact.concept
        self.parentFacts = parentFacts
        
    def view(self):
        # remove old widgets
        self.viewFrame.clearGrid()

        # table name
        self.zAxisRows = 0
        self.dataCols = 0
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
            if tupleDescendant is not None:
                return tupleDescendant
        return None
                
    def bodyCells(self, row, indent, tupleFacts, xFilters, zFilters):
        for modelTupleFact in tupleFacts:
            if modelTupleFact.concept == self.tupleConcept:
                for i, xColConcept in enumerate(xFilters):
                    fact = self.tupleDescendant(modelTupleFact, xColConcept)
                    if fact is not None:
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
            
