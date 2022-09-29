'''
See COPYRIGHT.md for copyright information.
'''
from arelle import XPathContext, XbrlConst, XmlUtil
from arelle.ModelFormulaObject import (aspectModels, aspectStr, Aspect)
from arelle.ModelRenderingObject import (CHILD_ROLLUP_FIRST, CHILD_ROLLUP_LAST,
                                         ModelDefinitionNode, ModelEuAxisCoord,
                                         ModelBreakdown,
                                         ModelClosedDefinitionNode,
                                         ModelRuleDefinitionNode,
                                         ModelFilterDefinitionNode,
                                         ModelDimensionRelationshipDefinitionNode)
from arelle.ModelValue import (QName)


def init(modelXbrl):
    # setup modelXbrl for rendering evaluation

    # dimension defaults required in advance of validation
    from arelle import ValidateXbrlDimensions, ValidateFormula, FormulaEvaluator, ModelDocument
    ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)

    hasXbrlTables = False

    # validate table linkbase dimensions
    for baseSetKey in modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and XbrlConst.isTableRenderingArcrole(arcrole):
            ValidateFormula.checkBaseSet(modelXbrl, arcrole, ELR, modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname))
            if arcrole in (XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD, XbrlConst.tableBreakdown201305, XbrlConst.tableBreakdown201301, XbrlConst.tableAxis2011):
                hasXbrlTables = True

    # provide context for view
    if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE:
        instance = None # use instance of the entry pont
    else: # need dummy instance
        instance = ModelDocument.create(modelXbrl, ModelDocument.Type.INSTANCE,
                                        "dummy.xml",  # fake URI and fake schemaRef
                                        ("http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd",))

    if hasXbrlTables:
        # formula processor is needed for 2011 XBRL tables but not for 2010 Eurofiling tables
        FormulaEvaluator.init()
        modelXbrl.rendrCntx = XPathContext.create(modelXbrl, instance)

        modelXbrl.profileStat(None)

        # setup fresh parameters from formula options
        modelXbrl.parameters = modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces)

        # validate parameters and custom function signatures
        ValidateFormula.validate(modelXbrl, xpathContext=modelXbrl.rendrCntx, parametersOnly=True, statusMsg=_("compiling rendering tables"))

        # deprecated as of 2013-05-17
        # check and extract message expressions into compilable programs
        for msgArcrole in (XbrlConst.tableDefinitionNodeMessage201301, XbrlConst.tableDefinitionNodeSelectionMessage201301,
                           XbrlConst.tableAxisMessage2011, XbrlConst.tableAxisSelectionMessage2011):
            for msgRel in modelXbrl.relationshipSet(msgArcrole).modelRelationships:
                ValidateFormula.checkMessageExpressions(modelXbrl, msgRel.toModelObject)

        # compile and validate tables
        for modelTable in modelXbrl.modelRenderingTables:
            modelTable.fromInstanceQnames = None # required if referred to by variables scope chaining
            modelTable.compile()

            hasNsWithAspectModel = modelTable.namespaceURI in (XbrlConst.euRend, XbrlConst.table2011, XbrlConst.table201301, XbrlConst.table201305)

            # check aspectModel  (attribute removed 2013-06, now always dimensional)
            if modelTable.aspectModel not in ("non-dimensional", "dimensional") and hasNsWithAspectModel:
                modelXbrl.error("xbrlte:unknownAspectModel",
                    _("Table %(xlinkLabel)s, aspect model %(aspectModel)s not recognized"),
                    modelObject=modelTable, xlinkLabel=modelTable.xlinkLabel, aspectModel=modelTable.aspectModel)
            else:
                modelTable.priorAspectAxisDisposition = {}
                # check ordinate aspects against aspectModel
                oppositeAspectModel = ({'dimensional', 'non-dimensional'} - {modelTable.aspectModel}).pop()
                if hasNsWithAspectModel:
                    uncoverableAspects = aspectModels[oppositeAspectModel] - aspectModels[modelTable.aspectModel]
                else:
                    uncoverableAspects = ()
                aspectsCovered = set()
                for tblAxisRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdown, XbrlConst.tableBreakdownMMDD, XbrlConst.tableBreakdown201305, XbrlConst.tableBreakdown201301,XbrlConst.tableAxis2011)).fromModelObject(modelTable):
                    breakdownAspectsCovered = set()
                    hasCoveredAspect = checkBreakdownDefinitionNode(modelXbrl, modelTable, tblAxisRel, tblAxisRel.axisDisposition, uncoverableAspects, breakdownAspectsCovered)
                    ''' removed 2013-10
                    if not hasCoveredAspect:
                        definitionNode = tblAxisRel.toModelObject
                        modelXbrl.error("xbrlte:breakdownDefinesNoAspects",
                            _("Breakdown %(xlinkLabel)s has no participating aspects"),
                            modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel, axis=definitionNode.localName)
                    '''
                    aspectsCovered |= breakdownAspectsCovered
                    checkBreakdownLeafNodeAspects(modelXbrl, modelTable, tblAxisRel, set(), breakdownAspectsCovered)
                if Aspect.CONCEPT not in aspectsCovered and not hasNsWithAspectModel:
                    modelXbrl.error("xbrlte:tableMissingConceptAspect",
                        _("Table %(xlinkLabel)s does not include the concept aspect as one of its participating aspects"),
                        modelObject=modelTable, xlinkLabel=modelTable.xlinkLabel)
                del modelTable.priorAspectAxisDisposition
                # check for table-parameter name clash
                parameterNames = {}
                for tblParamRel in modelXbrl.relationshipSet((XbrlConst.tableParameter, XbrlConst.tableParameterMMDD)).fromModelObject(modelTable):
                    parameterName = tblParamRel.variableQname
                    if parameterName in parameterNames:
                        modelXbrl.error("xbrlte:tableParameterNameClash ",
                            _("Table %(xlinkLabel)s has parameter name clash for variable %(name)s"),
                            modelObject=(modelTable,tblParamRel,parameterNames[parameterName]), xlinkLabel=modelTable.xlinkLabel, name=parameterName)
                    else:
                        parameterNames[parameterName] = tblParamRel

        modelXbrl.profileStat(_("compileTables"))

def checkBreakdownDefinitionNode(modelXbrl, modelTable, tblAxisRel, tblAxisDisposition, uncoverableAspects, aspectsCovered):
    definitionNode = tblAxisRel.toModelObject
    hasCoveredAspect = False
    if isinstance(definitionNode, (ModelDefinitionNode, ModelEuAxisCoord)):
        for aspect in definitionNode.aspectsCovered():
            aspectsCovered.add(aspect)
            if (aspect in uncoverableAspects or
                (isinstance(aspect, QName) and modelTable.aspectModel == 'non-dimensional')):
                modelXbrl.error("xbrlte:axisAspectModelMismatch",
                    _("%(definitionNode)s %(xlinkLabel)s, aspect model %(aspectModel)s, aspect %(aspect)s not allowed"),
                    modelObject=modelTable, definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel, aspectModel=modelTable.aspectModel,
                    aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect])
            hasCoveredAspect = True
            if aspect in modelTable.priorAspectAxisDisposition:
                otherAxisDisposition, otherDefinitionNode = modelTable.priorAspectAxisDisposition[aspect]
                if tblAxisDisposition != otherAxisDisposition and aspect != Aspect.DIMENSIONS:
                    modelXbrl.error("xbrlte:aspectClashBetweenBreakdowns",
                        _("%(definitionNode)s %(xlinkLabel)s, aspect %(aspect)s defined on axes of disposition %(axisDisposition)s and %(axisDisposition2)s"),
                        modelObject=(modelTable, definitionNode, otherDefinitionNode), definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel,
                        axisDisposition=tblAxisDisposition, axisDisposition2=otherAxisDisposition,
                        aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect])
            else:
                modelTable.priorAspectAxisDisposition[aspect] = (tblAxisDisposition, definitionNode)
        ruleSetChildren = XmlUtil.children(definitionNode, definitionNode.namespaceURI, "ruleSet")
        if definitionNode.isMerged:
            if ruleSetChildren:
                modelXbrl.error("xbrlte:mergedRuleNodeWithTaggedRuleSet",
                    _("Merged %(definitionNode)s %(xlinkLabel)s has tagged rule set(s)"),
                    modelObject=[modelTable, definitionNode] + ruleSetChildren,
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
            labelRels = modelXbrl.relationshipSet(XbrlConst.elementLabel).fromModelObject(definitionNode)
            if labelRels:
                modelXbrl.error("xbrlte:invalidUseOfLabel",
                    _("Merged %(definitionNode)s %(xlinkLabel)s has label(s)"),
                    modelObject=[modelTable, definitionNode] + [r.toModelObject for r in labelRels],
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
            if not definitionNode.isAbstract:
                modelXbrl.error("xbrlte:nonAbstractMergedRuleNode",
                    _("Merged %(definitionNode)s %(xlinkLabel)s is not abstract"),
                    modelObject=(modelTable, definitionNode), definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel)
    if isinstance(definitionNode, ModelRuleDefinitionNode):
        tagConstraintSets = {}
        otherConstraintSet = None
        # must look at xml constructs for duplicates
        for ruleSet in XmlUtil.children(definitionNode, definitionNode.namespaceURI, "ruleSet"):
            tag = ruleSet.tagName
            if tag is not None: # named constraint sets only
                for aspect in ruleSet.aspectsCovered():
                    if aspect != Aspect.DIMENSIONS:
                        modelTable.aspectsInTaggedConstraintSets.add(aspect)
            if tag in tagConstraintSets:
                modelXbrl.error("xbrlte:duplicateTag",
                    _("%(definitionNode)s %(xlinkLabel)s duplicate rule set tags %(tag)s"),
                    modelObject=(modelTable, definitionNode, tagConstraintSets[tag], ruleSet),
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel, tag=tag)
            else:
                tagConstraintSets[tag] = ruleSet
        for tag, constraintSet in definitionNode.constraintSets.items():
            if otherConstraintSet is None:
                otherConstraintSet = constraintSet
            elif otherConstraintSet.aspectsCovered() != constraintSet.aspectsCovered():
                modelXbrl.error("xbrlte:constraintSetAspectMismatch",
                    _("%(definitionNode)s %(xlinkLabel)s constraint set mismatches between %(tag1)s and %(tag2)s in constraints %(aspects)s"),
                    modelObject=(modelTable, definitionNode, otherConstraintSet, constraintSet),
                    definitionNode=definitionNode.localName, xlinkLabel=definitionNode.xlinkLabel,
                    tag1=getattr(otherConstraintSet,"tagName","(no tag)"), tag2=getattr(constraintSet, "tagName", "(no tag)"),
                    aspects=", ".join(aspectStr(aspect)
                                      for aspect in otherConstraintSet.aspectsCovered() ^ constraintSet.aspectsCovered()
                                      if aspect != Aspect.DIMENSIONS))
    if isinstance(definitionNode, ModelDimensionRelationshipDefinitionNode):
        hasCoveredAspect = True
        if modelTable.aspectModel == 'non-dimensional':
            modelXbrl.error("xbrlte:axisAspectModelMismatch",
                _("DimensionRelationship axis %(xlinkLabel)s can't be used in non-dimensional aspect model"),
                modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel)
    definitionNodeHasChild = False
    for axisSubtreeRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableBreakdownTree201305, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD, XbrlConst.tableDefinitionNodeSubtree201305, XbrlConst.tableDefinitionNodeSubtree201301, XbrlConst.tableAxisSubtree2011)).fromModelObject(definitionNode):
        if checkBreakdownDefinitionNode(modelXbrl, modelTable, axisSubtreeRel, tblAxisDisposition, uncoverableAspects, aspectsCovered):
            hasCoveredAspect = True # something below was covering
        definitionNodeHasChild = True
    if isinstance(definitionNode, ModelFilterDefinitionNode):
        for aspect in definitionNode.aspectsCovered():
            if isinstance(aspect, QName): # dimension aspect
                concept = modelXbrl.qnameConcepts.get(aspect)
                if concept is None or not concept.isDimensionItem:
                    modelXbrl.error("xbrlte:invalidDimensionQNameOnAspectNode",
                        _("Aspect node %(xlinkLabel)s dimensional aspect %(dimension)s is not a dimension"),
                        modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel, dimension=aspect)

    if not definitionNodeHasChild:
        if (definitionNode.namespaceURI in ("http://www.eurofiling.info/2010/rendering", "http://xbrl.org/2011/table")
            and not hasCoveredAspect):
            modelXbrl.error("xbrlte:aspectValueNotDefinedByOrdinate",
                _("%(definitionNode)s %(xlinkLabel)s does not define an aspect"),
                modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName)
        if (isinstance(definitionNode, ModelClosedDefinitionNode) and
            definitionNode.isAbstract):
            modelXbrl.error("xbrlte:abstractRuleNodeNoChildren",
                _("Abstract %(definitionNode)s %(xlinkLabel)s has no children"),
                modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName)
    return hasCoveredAspect

def checkBreakdownLeafNodeAspects(modelXbrl, modelTable, tblAxisRel, parentAspectsCovered, breakdownAspects):
    definitionNode = tblAxisRel.toModelObject
    aspectsCovered = parentAspectsCovered.copy()
    if isinstance(definitionNode, (ModelDefinitionNode, ModelEuAxisCoord)):
        for aspect in definitionNode.aspectsCovered():
            aspectsCovered.add(aspect)
        definitionNodeHasChild = False
        for axisSubtreeRel in modelXbrl.relationshipSet((XbrlConst.tableBreakdownTree, XbrlConst.tableBreakdownTreeMMDD, XbrlConst.tableBreakdownTree201305, XbrlConst.tableDefinitionNodeSubtree, XbrlConst.tableDefinitionNodeSubtreeMMDD, XbrlConst.tableDefinitionNodeSubtree201305, XbrlConst.tableDefinitionNodeSubtree201301, XbrlConst.tableAxisSubtree2011)).fromModelObject(definitionNode):
            checkBreakdownLeafNodeAspects(modelXbrl, modelTable, axisSubtreeRel, aspectsCovered, breakdownAspects)
            definitionNodeHasChild = True

        if not definitionNode.isAbstract and not isinstance(definitionNode, ModelBreakdown): # this is a leaf node
            missingAspects = set(aspect
                                 for aspect in breakdownAspects
                                 if aspect not in aspectsCovered and
                                    aspect != Aspect.DIMENSIONS and not isinstance(aspect,QName))
            if (missingAspects):
                modelXbrl.error("xbrlte:missingAspectValue",
                    _("%(definitionNode)s %(xlinkLabel)s does not define an aspect for %(aspect)s"),
                    modelObject=(modelTable,definitionNode), xlinkLabel=definitionNode.xlinkLabel, definitionNode=definitionNode.localName,
                    aspect=', '.join(aspectStr(aspect) for aspect in missingAspects))
