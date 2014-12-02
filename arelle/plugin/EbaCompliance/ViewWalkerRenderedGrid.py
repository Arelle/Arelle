'''
Created on Sep 25, 2014

@author: Gregorio Mongelli (Acsone S. A.)
(c) Copyright 2014 Acsone S. A., All rights reserved.
'''

from arelle.RenderingResolver import resolveAxesStructure
from arelle.ModelFormulaObject import Aspect, aspectModels, aspectModelAspect
from arelle.FormulaEvaluator import aspectMatches
from arelle.ModelInstanceObject import ModelDimensionValue
from arelle.ModelValue import QName
from arelle.ModelXbrl import DEFAULT
from arelle.ModelRenderingObject import (ModelClosedDefinitionNode, ModelEuAxisCoord)
from arelle.PrototypeInstanceObject import FactPrototype

from arelle import XbrlConst
from collections import defaultdict

emptySet = set()
emptyList = []

def viewWalkerRenderedGrid(modelXbrl, factWalkingAction, lang=None, viewTblELR=None, sourceView=None):
    '''
    Constructor
    :type modelXbrl: ModelXbrl
    :type factWalkingAction: FactWalkingAction
    :type lang: str
    '''
    modelXbrl.modelManager.showStatus(_("walking through tables"))
    view = ViewRenderedGrid(modelXbrl, lang, factWalkingAction)
    
    if sourceView is not None:
        viewTblELR = sourceView.tblELR
        view.ignoreDimValidity.set(sourceView.ignoreDimValidity.get())
        view.xAxisChildrenFirst.set(sourceView.xAxisChildrenFirst.get())
        view.yAxisChildrenFirst.set(sourceView.yAxisChildrenFirst.get())
    view.view(viewTblELR)
    modelXbrl.modelManager.showStatus(_("rendering for walk terminated"), clearAfter=5000)
    
class ViewRenderedGrid:
    def __init__(self, modelXbrl, lang, factWalkingAction):
        '''
        Constructor
        :type modelXbrl: ModelXbrl
        :type lang: str
        :type factWalkingAction: FactWalkingAction
        '''
        # find table model namespace based on table namespace
        self.tableModelNamespace = XbrlConst.tableModel
        for xsdNs in modelXbrl.namespaceDocs.keys():
            if xsdNs in (XbrlConst.tableMMDD, XbrlConst.table, XbrlConst.table201305, XbrlConst.table201301, XbrlConst.table2011):
                self.tableModelNamespace = xsdNs + "/model"
                break
        class nonTkBooleanVar():
            def __init__(self, value=True):
                self.value = value
            def set(self, value):
                self.value = value
            def get(self):
                return self.value
        # context menu boolean vars (non-tkinter boolean
        self.modelXbrl = modelXbrl
        self.lang = lang
        self.ignoreDimValidity = nonTkBooleanVar(value=True)
        self.xAxisChildrenFirst = nonTkBooleanVar(value=True)
        self.yAxisChildrenFirst = nonTkBooleanVar(value=False)
        self.factWalkingAction = factWalkingAction 

    def tableModelQName(self, localName):
        return '{' + self.tableModelNamespace + '}' + localName

    def view(self, viewTblELR=None):
        if viewTblELR is not None:
            tblELRs = (viewTblELR,)
        else:
            tblELRs = self.modelXbrl.relationshipSet("Table-rendering").linkRoleUris
        for tblELR in tblELRs:
            self.zOrdinateChoices = {}
            
                
            for discriminator in range(1, 65535):  # @UnusedVariable
                # each table z production
                tblAxisRelSet, xTopStructuralNode, yTopStructuralNode, zTopStructuralNode = resolveAxesStructure(self, tblELR)  # @UnusedVariable
                self.hasTableFilters = bool(self.modelTable.filterRelationships)
                
                self.zStrNodesWithChoices = []
                if tblAxisRelSet:
                    zAspectStructuralNodes = defaultdict(set)
                    self.zAxis(1, zTopStructuralNode, zAspectStructuralNodes, False)
                    xStructuralNodes = []
                    self.xAxis(self.dataFirstCol, self.colHdrTopRow, self.colHdrTopRow + self.colHdrRows - 1, 
                               xTopStructuralNode, xStructuralNodes, self.xAxisChildrenFirst.get(), True, True)
                    self.bodyCells(self.dataFirstRow, yTopStructuralNode, xStructuralNodes, zAspectStructuralNodes, self.yAxisChildrenFirst.get(), tblELR)
                # find next choice structural node
                moreDiscriminators = False
                for zStrNodeWithChoices in self.zStrNodesWithChoices:
                    currentIndex = zStrNodeWithChoices.choiceNodeIndex + 1
                    if currentIndex < len(zStrNodeWithChoices.choiceStructuralNodes):
                        zStrNodeWithChoices.choiceNodeIndex = currentIndex
                        self.zOrdinateChoices[zStrNodeWithChoices.definitionNode] = currentIndex
                        moreDiscriminators = True
                        break
                    else:
                        zStrNodeWithChoices.choiceNodeIndex = 0
                        self.zOrdinateChoices[zStrNodeWithChoices.definitionNode] = 0
                        # continue incrementing next outermore z choices index
                if not moreDiscriminators:
                    break
        self.factWalkingAction.afterAllFactsEvent()

            
    def zAxis(self, row, zStructuralNode, zAspectStructuralNodes, discriminatorsTable):
        if zStructuralNode is not None:
            label = zStructuralNode.header(lang=self.lang)
            choiceLabel = None
            effectiveStructuralNode = zStructuralNode
            if zStructuralNode.choiceStructuralNodes: # same as combo box selection in GUI mode
                if not discriminatorsTable:
                    self.zStrNodesWithChoices.insert(0, zStructuralNode) # iteration from last is first
                try:
                    effectiveStructuralNode = zStructuralNode.choiceStructuralNodes[zStructuralNode.choiceNodeIndex]
                    choiceLabel = effectiveStructuralNode.header(lang=self.lang)
                    if not label and choiceLabel:
                        label = choiceLabel # no header for choice
                        choiceLabel = None
                except KeyError:
                    pass

            for aspect in aspectModels[self.aspectModel]:
                if effectiveStructuralNode.hasAspect(aspect, inherit=True): #implies inheriting from other z axes
                    if aspect == Aspect.DIMENSIONS:
                        for dim in (effectiveStructuralNode.aspectValue(Aspect.DIMENSIONS, inherit=True) or emptyList):
                            zAspectStructuralNodes[dim].add(effectiveStructuralNode)
                    else:
                        zAspectStructuralNodes[aspect].add(effectiveStructuralNode)
            for zStructuralNode in zStructuralNode.childStructuralNodes:
                self.zAxis(row + 1, zStructuralNode, zAspectStructuralNodes, discriminatorsTable)

    def xAxis(self, leftCol, topRow, rowBelow, xParentStructuralNode, xStructuralNodes, childrenFirst, renderNow, atTop):
        if xParentStructuralNode is not None:
            parentRow = rowBelow
            noDescendants = True
            rightCol = leftCol
            widthToSpanParent = 0
            for xStructuralNode in xParentStructuralNode.childStructuralNodes:
                noDescendants = False
                rightCol, row, width, leafNode = self.xAxis(leftCol, topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, # nested items before totals
                                                            childrenFirst, childrenFirst, False)
                if row - 1 < parentRow:
                    parentRow = row - 1
                #if not leafNode: 
                #    rightCol -= 1
                nonAbstract = not xStructuralNode.isAbstract
                if nonAbstract:
                    width += 100 # width for this label
                widthToSpanParent += width
                if renderNow and nonAbstract:
                    xStructuralNodes.append(xStructuralNode)
                if nonAbstract:
                    rightCol += 1
                if renderNow and not childrenFirst:
                    self.xAxis(leftCol + (1 if nonAbstract else 0), topRow + 1, rowBelow, xStructuralNode, xStructuralNodes, childrenFirst, True, False) # render on this pass
                leftCol = rightCol
            return (rightCol, parentRow, widthToSpanParent, noDescendants)

    def bodyCells(self, row, yParentStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst, tblELR):
        if yParentStructuralNode is not None:
            dimDefaults = self.modelXbrl.qnameDimensionDefaults
            for yStructuralNode in yParentStructuralNode.childStructuralNodes:
                if yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst, tblELR)
                if not (yStructuralNode.isAbstract or 
                        (yStructuralNode.childStructuralNodes and
                         not isinstance(yStructuralNode.definitionNode, (ModelClosedDefinitionNode, ModelEuAxisCoord)))) and yStructuralNode.isLabeled:
                    yAspectStructuralNodes = defaultdict(set)
                    for aspect in aspectModels[self.aspectModel]:
                        if yStructuralNode.hasAspect(aspect):
                            if aspect == Aspect.DIMENSIONS:
                                for dim in (yStructuralNode.aspectValue(Aspect.DIMENSIONS) or emptyList):
                                    yAspectStructuralNodes[dim].add(yStructuralNode)
                            else:
                                yAspectStructuralNodes[aspect].add(yStructuralNode)
                    yTagSelectors = yStructuralNode.tagSelectors
                    # data for columns of rows
                    for _, xStructuralNode in enumerate(xStructuralNodes):
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
                        for aspect in _DICT_SET(xAspectStructuralNodes.keys()) | _DICT_SET(yAspectStructuralNodes.keys()) | _DICT_SET(zAspectStructuralNodes.keys()):  # @UndefinedVariable
                            aspectValue = xStructuralNode.inheritedAspectValue(yStructuralNode,
                                               self, aspect, cellTagSelectors, 
                                               xAspectStructuralNodes, yAspectStructuralNodes, zAspectStructuralNodes)
                            # value is None for a dimension whose value is to be not reported in this slice
                            if (isinstance(aspect, _INT) or  # not a dimension @UndefinedVariable
                                dimDefaults.get(aspect) != aspectValue or # explicit dim defaulted will equal the value
                                aspectValue is not None): # typed dim absent will be none
                                cellAspectValues[aspect] = aspectValue
                            matchableAspects.add(aspectModelAspect.get(aspect,aspect)) #filterable aspect from rule aspect
                        cellDefaultedDims = _DICT_SET(dimDefaults) - _DICT_SET(cellAspectValues.keys())  # @UndefinedVariable
                        priItemQname = cellAspectValues.get(Aspect.CONCEPT)
                            
                        concept = self.modelXbrl.qnameConcepts.get(priItemQname)
                        conceptNotAbstract = concept is None or not concept.isAbstract
                        fact = None
                        value = None
                        fp = FactPrototype(self, cellAspectValues)
                        if conceptNotAbstract:
                            # reduce set of matchable facts to those with pri item qname and have dimension aspects
                            facts = self.modelXbrl.factsByQname(priItemQname, set()) if priItemQname else self.modelXbrl.factsInInstance
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
                                        dimMemQname = DEFAULT
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
                                    self.factWalkingAction.onFactEvent(fact, value, tblELR)
                                    break

                        fp.clear()  # dereference
                    row += 1
                if not yChildrenFirst:
                    row = self.bodyCells(row, yStructuralNode, xStructuralNodes, zAspectStructuralNodes, yChildrenFirst, tblELR)
        return row
            