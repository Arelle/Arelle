'''
See COPYRIGHT.md for copyright information.
'''
import xml.dom, datetime
import regex as re
from arelle import XbrlConst, XbrlUtil, XmlUtil
from arelle.formula import XPathContext
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.ModelValue import qname, QName, dateTime, DATE, DATETIME, DATEUNION, DateTime, dateUnionEqual, anyURI
from arelle.FunctionUtil import anytypeArg, stringArg, numericArg, qnameArg, nodeArg, atomicArg
from arelle.ModelXbrl import ModelXbrl
from arelle.ModelDtsObject import anonymousTypeSuffix, ModelConcept
from arelle.ModelInstanceObject import ModelDimensionValue, ModelFact, ModelInlineFact
from arelle.ModelFormulaObject import ModelFormulaResource
from arelle.PythonUtil import flattenSequence
from arelle.formula.XPathParser import OperationDef
from arelle.XmlValidateConst import UNKNOWN, VALID, VALID_NO_CONTENT
from arelle.XmlValidate import validate as xmlValidate, NCNamePattern
from arelle.ValidateXbrlCalcs import inferredDecimals, inferredPrecision
from arelle.ValidateXbrlDimensions import priItemElrHcRels
from arelle.Locale import format_picture
from lxml import etree
from math import isnan, isinf

class xfiFunctionNotAvailable(Exception):
    def __init__(self):
        self.args =  (_("xfi function not available"),)
    def __repr__(self):
        return self.args[0]

def call(
        xc: XPathContext.XPathContext,
        p: OperationDef,
        localname: str,
        args: XPathContext.ResultStack,
) -> XPathContext.RecursiveContextItem:
    try:
        if localname not in xfiFunctions: raise xfiFunctionNotAvailable
        return xfiFunctions[localname](xc, p, args)
    except xfiFunctionNotAvailable:
        raise XPathContext.FunctionNotAvailable("xfi:{0}".format(localname))

def instance(xc, p, args, i=0):
    if i >= len(args):  # missing argument means to use the standard input instance
        return xc.modelXbrl
    if len(args[i]) != 1: # a sequence of instances isn't acceptable to these classes of functions
        raise XPathContext.FunctionArgType(i+1,"xbrl:xbrl")
    xbrliXbrl = anytypeArg(xc, args, i, "xbrli:xbrl")
    if isinstance(xbrliXbrl, ModelObject) and xbrliXbrl.elementQname == XbrlConst.qnXbrliXbrl:
        return xbrliXbrl.modelXbrl
    elif isinstance(xbrliXbrl, ModelXbrl):
        return xbrliXbrl
    raise XPathContext.FunctionArgType(i,"xbrl:xbrl")

def item(xc, args, i=0):
    if len(args[i]) != 1: raise XPathContext.FunctionArgType(i+1,"xbrl:item")
    modelItem = xc.modelItem(args[i][0])
    if modelItem is not None:
        return modelItem
    raise XPathContext.FunctionArgType(i,"xbrl:item")

def xbrlTuple(xc, args, i=0):
    # can't name this just tuple because then it hides tuple() constructor of Python
    if len(args[i]) != 1: raise XPathContext.FunctionArgType(i+1,"xbrl:tuple")
    modelTuple = args[i][0]
    if isinstance(modelTuple, (ModelFact, ModelInlineFact)) and modelTuple.isTuple:
        return modelTuple
    raise XPathContext.FunctionArgType(i,"xbrl:tuple")

def item_context(xc, args, i=0):
    return item(xc, args, i).context

def item_context_element(xc, args, name):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        return XmlUtil.descendant(context, XbrlConst.xbrli, name)
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def context(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return item_context(xc, args)

def unit(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:item")
    modelItem = xc.modelItem(args[0][0])
    if modelItem is not None:
        modelConcept = modelItem.concept
        if modelConcept.isNumeric and not modelConcept.isFraction:
            return modelItem.unit
        return []
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def unit_numerator(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:unit")
    unit = args[0][0]
    if isinstance(unit,ModelObject) and \
       unit.localName == "unit" and unit.namespaceURI == XbrlConst.xbrli:
        measuresParent = XmlUtil.descendant(unit, XbrlConst.xbrli, "unitNumerator")
        if measuresParent is None: measuresParent = unit
        return XmlUtil.descendants(measuresParent, XbrlConst.xbrli, "measure")
    raise XPathContext.FunctionArgType(1,"xbrl:unit")

def unit_denominator(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:unit")
    unit = args[0][0]
    if isinstance(unit,ModelObject) and \
       unit.localName == "unit" and unit.namespaceURI == XbrlConst.xbrli:
        measuresParent = XmlUtil.descendant(unit, XbrlConst.xbrli, "unitDenominator")
        if measuresParent is None: return []
        return XmlUtil.descendants(measuresParent, XbrlConst.xbrli, "measure")
    raise XPathContext.FunctionArgType(1,"xbrl:unit")

def measure_name(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:measure")
    unit = args[0][0]
    if isinstance(unit,ModelObject) and \
       unit.localName == "measure" and unit.namespaceURI == XbrlConst.xbrli:
        return qname(unit, XmlUtil.text(unit))
    raise XPathContext.FunctionArgType(1,"xbrl:unit")

def period(xc, p, args):
    return item_context_element(xc, args, "period")

def context_period(xc, p, args):
    return parent_child(args, "context", "period")

def parent_child(args, parentName, childName, findDescendant=False):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:" + parentName)
    parent = args[0][0]
    if isinstance(parent,ModelObject) and \
       parent.localName == parentName and parent.namespaceURI == XbrlConst.xbrli:
        if childName.startswith('@'):
            return parent.get(childName[1:])
        elif childName == 'text()':
            return XmlUtil.textNotStripped(parent)
        elif childName == 'strip-text()':
            return XmlUtil.text(parent)
        elif findDescendant:
            return XmlUtil.descendant(parent, XbrlConst.xbrli, childName)
        else:
            return XmlUtil.child(parent, XbrlConst.xbrli, childName)
    raise XPathContext.FunctionArgType(1,"xbrl:" + parentName)

def is_start_end_period(xc, p, args):
    return is_period_type(args, "startDate")

def is_forever_period(xc, p, args):
    return is_period_type(args, "forever")

def is_duration_period(xc, p, args):
    return is_period_type(args, ("forever","startDate") )

def is_instant_period(xc, p, args):
    return is_period_type(args, "instant")

def is_period_type(args, periodElement):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:period")
    period = args[0][0]
    if isinstance(period,ModelObject) and \
       period.localName == "period" and period.namespaceURI == XbrlConst.xbrli:
        return XmlUtil.hasChild(period, XbrlConst.xbrli, periodElement)
    raise XPathContext.FunctionArgType(1,"xbrl:period")

def period_start(xc, p, args):
    return period_datetime(p, args, ("startDate","instant"))

def period_end(xc, p, args):
    return period_datetime(p, args, ("endDate","instant"))

def period_instant(xc, p, args):
    return period_datetime(p, args, "instant")

def period_datetime(p, args, periodElement):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:period")
    period = args[0][0]
    if (isinstance(period,ModelObject) == 1 and
        period.localName == "period" and period.namespaceURI == XbrlConst.xbrli):
        child = XmlUtil.child(period, XbrlConst.xbrli, periodElement)
        if child is not None:
            addOneDay = child.localName != "startDate"
            return dateTime( child, addOneDay=addOneDay, type=DATETIME)
        elif periodElement == "instant":
            raise XPathContext.XPathException(p, 'xfie:PeriodIsNotInstant', _('Period is not instant'))
        else:
            raise XPathContext.XPathException(p, 'xfie:PeriodIsForever', _('Period is forever'))
    raise XPathContext.FunctionArgType(1,"xbrl:period")

def entity(xc, p, args):
    return item_context_element(xc, args, "entity")

def context_entity(xc, p, args):
    return parent_child(args, "context", "entity")

def identifier(xc, p, args):
    return item_context_element(xc, args, "identifier")

def context_identifier(xc, p, args):
    return parent_child(args, "context", "identifier", True)

def entity_identifier(xc, p, args):
    return parent_child(args, "entity", "identifier")

def identifier_value(xc, p, args):
    return parent_child(args, "identifier", "strip-text()")

def identifier_scheme(xc, p, args):
    scheme = parent_child(args, "identifier", "@scheme")
    if scheme is None:
        return None
    return anyURI(scheme)

def fact_identifier_value(xc, p, args):
    return XmlUtil.text(item_context_element(xc, args, "identifier")).strip()

def fact_identifier_scheme(xc, p, args):
    scheme = item_context_element(xc, args, "identifier").get("scheme")
    if scheme is None:
        return None
    return anyURI(scheme)

def segment(xc, p, args):
    seg = item_context_element(xc, args, "segment")
    if seg is None:
        return () # no segment
    return seg

def entity_segment(xc, p, args):
    seg = parent_child(args, "entity", "segment")
    if seg is None:
        return () # no segment
    return seg

def context_segment(xc, p, args):
    seg = parent_child(args, "context", "segment", True)
    if seg is None:
        return () # no segment
    return seg

def scenario(xc, p, args):
    scen = item_context_element(xc, args, "scenario")
    if scen is None:
        return () # no segment
    return scen

def context_scenario(xc, p, args):
    scen = parent_child(args, "context", "scenario")
    if scen is None:
        return () # no segment
    return scen

def precision(xc, p, args):
    return infer_precision_decimals(xc, p, args, "precision")

def decimals(xc, p, args):
    return infer_precision_decimals(xc, p, args, "decimals")

def infer_precision_decimals(xc, p, args, attrName):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    if len(args[0]) != 1: raise XPathContext.FunctionArgType(1,"xbrl:item",args[0])
    modelItem = xc.modelItem(args[0][0])
    if modelItem is None:
        raise XPathContext.FunctionArgType(1,"xbrl:item")
    modelConcept = modelItem.concept
    if modelConcept.isFraction:
        return 'INF'
    if modelConcept.isNumeric:
        p = inferredPrecision(modelItem) if attrName == "precision" else inferredDecimals(modelItem)
        if isinf(p):
            return 'INF'
        if isnan(p):
            raise XPathContext.XPathException(p, 'xfie:ItemIsNotNumeric', _('Argument 1 {0} is not inferrable.').format(attrName))
        return p
    raise XPathContext.XPathException(p, 'xfie:ItemIsNotNumeric', _('Argument 1 is not reported with {0}.').format(attrName))

def numeric(xc, p, args):
    return conceptProperty(xc, p, args, "numeric")

def non_numeric(xc, p, args):
    return conceptProperty(xc, p, args, "non-numeric")

def fraction(xc, p, args):
    return conceptProperty(xc, p, args, "fraction")

def conceptProperty(xc, p, args, property):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    qn = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    if qn:
        modelConcept = xc.modelXbrl.qnameConcepts.get(qn)
        if modelConcept is not None:
            if property == "numeric": return modelConcept.isNumeric or modelConcept.isFraction
            if property == "non-numeric": return modelConcept.isItem and not (modelConcept.isNumeric or modelConcept.isFraction)
            if property == "fraction": return modelConcept.isFraction
    return False

def checkXffFunctionUse(xc, p, functionName):
    # check function use after checking argument types
    if xc.progHeader is not None and xc.progHeader.element is not None:
        try:
            modelResourceElt = xc.progHeader.element._modelResourceElt
        except AttributeError:
            modelResourceElt = xc.progHeader.element
            while (modelResourceElt is not None and not isinstance(modelResourceElt, ModelFormulaResource)):
                modelResourceElt = modelResourceElt.getparent()
            xc.progHeader.element._modelResourceElt = modelResourceElt

        if (modelResourceElt is None or
            modelResourceElt.localName not in ("formula", "consistencyAssertion", "valueAssertion", "precondition", "message")):
            raise XPathContext.XPathException(p, 'xffe:invalidFunctionUse', _('Function xff:uncovered-aspect cannot be used on an XPath expression associated with a {0}').format(xc.progHeader.element.localName))

    if xc.variableSet is not None and xc.variableSet.implicitFiltering  == "false":
        raise XPathContext.XPathException(p, 'xffe:invalidFunctionUse', _('Function xff:uncovered-aspect cannot be used with implicitFiltering=false'))

def uncovered_aspect(xc, p, args):
    from arelle.ModelFormulaObject import aspectFromToken, Aspect
    from arelle.formula.FormulaEvaluator import uncoveredAspectValue
    if len(args) not in (1,2): raise XPathContext.FunctionNumArgs()
    aspect = aspectFromToken.get(stringArg(xc, args, 0, "xs:token").strip())
    if aspect == Aspect.DIMENSIONS:
        qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)

    checkXffFunctionUse(xc, p, "uncovered-aspect")

    if aspect == Aspect.DIMENSIONS:
        if qn:
            modelConcept = xc.modelXbrl.qnameConcepts.get(qn)
            if modelConcept is not None and modelConcept.isDimensionItem:
                aspect = qn
            else:
                return ()   # not a dimension
            dimValue = uncoveredAspectValue(xc, aspect)
            if isinstance(dimValue, ModelDimensionValue):
                if dimValue.isExplicit:
                    return dimValue.memberQname
                elif dimValue.isTyped:
                    return dimValue     # return the typedMember element, not its contents
            elif isinstance(dimValue, QName): # qname for explicit or node for typed
                return dimValue
            return ()
    aspectValue = uncoveredAspectValue(xc, aspect)
    if aspectValue is None:
        return ()
    return aspectValue

def has_fallback_value(xc, p, args):
    from arelle.formula.FormulaEvaluator import variableBindingIsFallback
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    variableQname = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)

    checkXffFunctionUse(xc, p, "has-fallback-value")

    return variableBindingIsFallback(xc, variableQname)

def uncovered_non_dimensional_aspects(xc, p, args):
    return uncovered_aspects(xc, p, args, dimensionAspects=False)

def uncovered_dimensional_aspects(xc, p, args):
    return uncovered_aspects(xc, p, args, dimensionAspects=True)

def uncovered_aspects(xc, p, args, dimensionAspects=False):
    from arelle.ModelFormulaObject import aspectToToken, Aspect
    from arelle.formula.FormulaEvaluator import uncoveredVariableSetAspects
    if len(args) != 0: raise XPathContext.FunctionNumArgs()

    # check function use after checking argument types
    if xc.progHeader is not None and xc.progHeader.element is not None:
        if xc.progHeader.element.localName not in ("formula", "consistencyAssertion", "valueAssertion", "message"):
            raise XPathContext.XPathException(p, 'xffe:invalidFunctionUse', _('Function xff:uncovered-aspect cannot be used on an XPath expression associated with a {0}').format(xc.progHeader.element.localName))
        if xc.variableSet is not None and xc.variableSet.implicitFiltering  == "false":
            raise XPathContext.XPathException(p, 'xffe:invalidFunctionUse', _('Function xff:uncovered-aspect cannot be used with implicitFiltering=false'))

    uncoveredAspects = uncoveredVariableSetAspects(xc)
    return [(a if dimensionAspects else aspectToToken.get(a))
            for a in uncoveredAspects if a != Aspect.DIMENSIONS and isinstance(a,QName) == dimensionAspects ]

def nodesEqual(xc, args, test, mustBeItems=False, nonItemErrCode=None):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    seq1 = flattenSequence(args[0])
    seq2 = flattenSequence(args[1])
    for i, node1 in enumerate(seq1):
        try:
            node2 = seq2[i]
            if not isinstance(node1, (ModelObject,ModelAttribute)):
                raise XPathContext.FunctionArgType(1,"node()*")
            if not isinstance(node2, (ModelObject,ModelAttribute)):
                raise XPathContext.FunctionArgType(2,"node()*")
            if mustBeItems:
                if not isinstance(node1, (ModelFact, ModelInlineFact)) or not node1.isItem:
                    raise XPathContext.FunctionArgType(1,"xbrl:item*", errCode=nonItemErrCode)
                if not isinstance(node2, (ModelFact, ModelInlineFact)) or not node2.isItem:
                    raise XPathContext.FunctionArgType(2,"xbrl:item*", errCode=nonItemErrCode)
            if not test(node1, node2):
                return False
        except IndexError:
            return False
    return True

def setsEqual(xc, args, test, mustBeItems=False):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    seq1 = flattenSequence(args[0])
    seq2 = flattenSequence(args[1])
    for node1 in seq1:
        if not isinstance(node1, ModelObject):
            raise XPathContext.FunctionArgType(1,"node()*")
        if mustBeItems and (not isinstance(node1, (ModelFact, ModelInlineFact)) or not node1.isItem):
            raise XPathContext.FunctionArgType(1,"xbrl:item*", errCode="xfie:NodeIsNotXbrlItem")
    for node2 in seq2:
        if not isinstance(node2, ModelObject):
            raise XPathContext.FunctionArgType(2,"node()*")
        if mustBeItems and (not isinstance(node2, (ModelFact, ModelInlineFact)) or not node2.isItem):
            raise XPathContext.FunctionArgType(2,"xbrl:item*", errCode="xfie:NodeIsNotXbrlItem")
    if len(set(seq1)) != len(set(seq2)): # sequences can have nondistinct duplicates, just same set lengths needed
        return False
    for node1 in seq1:
        if not any(test(node1, node2) for node2 in seq2):
            return False
    return True

def identical_nodes(xc, p, args):
    return nodesEqual(xc, args, identical_nodes_test)

def identical_nodes_test(node1, node2):
    return node1 == node2

def s_equal(xc, p, args):
    return nodesEqual(xc, args, s_equal_test)

def s_equal_test(node1, node2):
    if (isinstance(node1, (ModelFact, ModelInlineFact)) and node1.isItem and
        isinstance(node2, (ModelFact, ModelInlineFact)) and node2.isItem):
        return (c_equal_test(node1, node2) and u_equal_test(node1, node2) and
                XbrlUtil.xEqual(node1, node2) and
                # must be validated (by xEqual) before precision tests to assure xAttributes is set
                node1.xAttributes.get("precision") == node2.xAttributes.get("precision") and
                node1.xAttributes.get("decimals") == node2.xAttributes.get("decimals"))
    elif isinstance(node1, ModelObject):
        if isinstance(node2, ModelObject):
            return XbrlUtil.sEqual(node1.modelXbrl, node1, node2, excludeIDs=XbrlUtil.TOP_IDs_EXCLUDED, dts2=node2.modelXbrl)
        else:
            return False
    elif isinstance(node1, ModelAttribute):
        if isinstance(node2, ModelAttribute):
            return node1.text == node2.text
    return False

def u_equal(xc, p, args):
    return nodesEqual(xc, args, u_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def u_equal_test(modelItem1, modelItem2):
    modelUnit1 = modelItem1.unit
    modelUnit2 = modelItem2.unit
    if modelUnit1 is None:
        return modelUnit2 is None
    else:
        return modelUnit1.isEqualTo(modelUnit2)

def v_equal(xc, p, args):
    return nodesEqual(xc, args, v_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def v_equal_test(modelItem1, modelItem2):
    return modelItem1.isVEqualTo(modelItem2)

def c_equal(xc, p, args):
    return nodesEqual(xc, args, c_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def c_equal_test(modelItem1, modelItem2):
    modelCntx1 = modelItem1.context
    modelCntx2 = modelItem2.context
    if modelCntx1 is None:
        return modelCntx2 is None
    else:
        return modelCntx1.isEqualTo(modelCntx2,dimensionalAspectModel=False)

def identical_node_set(xc, p, args):
    return setsEqual(xc, args, identical_nodes_test)

def s_equal_set(xc, p, args):
    return setsEqual(xc, args, s_equal_test)

def v_equal_set(xc, p, args):
    return setsEqual(xc, args, v_equal_test, mustBeItems=True)

def c_equal_set(xc, p, args):
    return setsEqual(xc, args, c_equal_test, mustBeItems=True)

def u_equal_set(xc, p, args):
    return setsEqual(xc, args, u_equal_test, mustBeItems=True)

def x_equal(xc, p, args):
    return nodesEqual(xc, args, x_equal_test)

def x_equal_test(node1, node2):
    if isinstance(node1, ModelObject):
        if isinstance(node2, ModelObject):
            return XbrlUtil.xEqual(node1, node2)
        else:
            return False
    elif isinstance(node1, ModelAttribute):
        if isinstance(node2, ModelAttribute):
            return node1.sValue == node2.sValue
    return False


def duplicate_item(xc, p, args):
    node1 = item(xc, args, 0)
    node2 = item(xc, args, 1)
    if node1.isItem and node2.isItem:
        return node1.isDuplicateOf(node2)
    return False

def duplicate_tuple(xc, p, args):
    node1 = xbrlTuple(xc, args, 0)
    node2 = xbrlTuple(xc, args, 1)
    return duplicate_tuple_test(node1, node2)

def duplicate_tuple_test(node1, node2, topLevel=True):
    if node1.isTuple and node2.isTuple:
        return node1.isDuplicateOf(node2)
    return False

def p_equal(xc, p, args):
    return nodesEqual(xc, args, p_equal_test)

def p_equal_test(node1, node2):
    if not isinstance(node1, (ModelFact, ModelInlineFact)) or not (node1.isItem or node1.isTuple):
        raise XPathContext.FunctionArgType(1,"xbrli:item or xbrli:tuple", errCode="xfie:ElementIsNotXbrlConcept")
    if not isinstance(node2, (ModelFact, ModelInlineFact)) or not (node1.isItem or node1.isTuple):
        raise XPathContext.FunctionArgType(2,"xbrli:item or xbrli:tuple", errCode="xfie:ElementIsNotXbrlConcept")
    return node1.parentElement == node2.parentElement

def cu_equal(xc, p, args):
    return nodesEqual(xc, args, cu_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def cu_equal_test(modelItem1, modelItem2):
    return c_equal_test(modelItem1, modelItem2) and u_equal_test(modelItem1, modelItem2)

def pc_equal(xc, p, args):
    return nodesEqual(xc, args, pc_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def pc_equal_test(modelItem1, modelItem2):
    return p_equal_test(modelItem1, modelItem2) and c_equal_test(modelItem1, modelItem2)

def pcu_equal(xc, p, args):
    return nodesEqual(xc, args, pcu_equal_test, mustBeItems=True, nonItemErrCode="xfie:NodeIsNotXbrlItem")

def pcu_equal_test(modelItem1, modelItem2):
    return p_equal_test(modelItem1, modelItem2) and c_equal_test(modelItem1, modelItem2) and u_equal_test(modelItem1, modelItem2)

def start_equal(xc, p, args):
    return date_equal_test(xc, p, args, False)

def end_equal(xc, p, args):
    return date_equal_test(xc, p, args, True)

def taxonomy_refs(xc, p, args):
    return [ref.referringModelObject.xAttributes.get("{http://www.w3.org/1999/xlink}href").xValue # need typed value
            for ref in sorted(xc.modelXbrl.modelDocument.referencesDocument.values(),
                              key=lambda r:r.referringModelObject.objectIndex)
            if ref.referringModelObject.localName == "schemaRef"]

def date_equal_test(xc, p, args, instantEndDate):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    date1 = atomicArg(xc, p, args, 0, "xbrldi:dateUnion", missingArgFallback=(), emptyFallback=None)
    if not isinstance(date1, (DateTime,datetime.date)):
        raise XPathContext.FunctionArgType(1,"xbrldi:dateUnion")
    date2 = atomicArg(xc, p, args, 1, "xbrldi:dateUnion", missingArgFallback=(), emptyFallback=None)
    if not isinstance(date1, (DateTime,datetime.date)):
        raise XPathContext.FunctionArgType(2,"xbrldi:dateUnion")
    return dateUnionEqual(date1, date2, instantEndDate)

def nodes_correspond(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    node1 = nodeArg(xc, args, 0, "node()?", missingArgFallback=(), emptyFallback=())
    node2 = nodeArg(xc, args, 1, "node()?", missingArgFallback=(), emptyFallback=())
    if node1 == ():
        if node2 == (): return True
        return False
    if node2 == (): return False
    return XbrlUtil.nodesCorrespond(xc.modelXbrl, node1, node2, xc.modelXbrl)

def facts_in_instance(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args)
    return inst.factsInInstance

def items_in_instance(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args)
    return [f for f in inst.factsInInstance if f.isItem]

def tuples_in_instance(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args)
    return [f for f in inst.factsInInstance if f.isTuple]

def items_in_tuple(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    parentTuple = xbrlTuple(xc, args, 0)
    return [f for f in parentTuple.modelTupleFacts if f.isItem]

def tuples_in_tuple(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    parentTuple = xbrlTuple(xc, args, 0)
    return [f for f in parentTuple.modelTupleFacts if f.isTuple]

def non_nil_facts_in_instance(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args)
    return [f for f in inst.factsInInstance if (f.isItem or f.isTuple) and not f.isNil]

def concept(xc, p, args):
    qnConcept = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    srcConcept = xc.modelXbrl.qnameConcepts.get(qnConcept)
    if srcConcept is None or not (srcConcept.isItem or srcConcept.isTuple) or srcConcept.qname is None or srcConcept.qname.namespaceURI == XbrlConst.xbrli:
        raise XPathContext.XPathException(p, 'xfie:invalidConceptQName', _('Argument 1 {0} is not a concept in the DTS.').format(qnConcept))
    return srcConcept

def concept_balance(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    balance = concept(xc,p,args).get("{http://www.xbrl.org/2003/instance}balance")
    if balance is None:
        balance = ""
    return balance

def concept_period_type(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return concept(xc,p,args).get("{http://www.xbrl.org/2003/instance}periodType")

def concept_custom_attribute(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    qnAttr = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    if qnAttr is None: raise XPathContext.FunctionArgType(2,"xs:QName")
    element = concept(xc,p,args)
    return element_attribute(element, qnAttr)

def concept_data_type(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    typeQname = concept(xc,p,args).typeQname
    if typeQname is None or typeQname.localName.endswith(anonymousTypeSuffix):
        return ()
    return typeQname

def concept_data_type_derived_from(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    qnType = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    if qnType is None: raise XPathContext.FunctionArgType(2,"xs:QName")
    return concept(xc,p,args).instanceOfType(qnType)

def concept_substitutions(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    return concept(xc,p,args).substitutionGroupQnames

def concepts_from_local_name(xc, p, args):
    if not 1 <= len(args) <= 2: raise XPathContext.FunctionNumArgs()
    localName = stringArg(xc, args, 0, "xs:string")
    if len(args) == 2:
        nsPattern = re.compile(stringArg(xc, args, 1, "xs:string"))
        return [c.qname for c in xc.modelXbrl.nameConcepts.get(localName,())
                if (c.isItem or c.isTuple) and bool(nsPattern.search(c.qname.namespaceURI))]
    else:
        return [c.qname for c in xc.modelXbrl.nameConcepts.get(localName,())
                if c.isItem or c.isTuple]

def concepts_from_local_name_pattern(xc, p, args):
    if not 1 <= len(args) <= 2: raise XPathContext.FunctionNumArgs()
    localNamePattern = re.compile(stringArg(xc, args, 0, "xs:string"))
    if len(args) == 2:
        nsPattern = re.compile(stringArg(xc, args, 1, "xs:string"))
        return [c.qname for c in xc.modelXbrl.qnameConcepts.values()
                if (c.isItem or c.isTuple) and bool(localNamePattern.search(c.name)) and bool(nsPattern.search(c.qname.namespaceURI))]
    else:
        return [c.qname for c in xc.modelXbrl.qnameConcepts.values()
                if (c.isItem or c.isTuple) and bool(localNamePattern.search(c.name))]

def filter_member_network_selection(xc, p, args):
    if len(args) != 5: raise XPathContext.FunctionNumArgs()
    qnDim = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    qnMem = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    linkroleURI = stringArg(xc, args, 2, "xs:string")
    arcroleURI = stringArg(xc, args, 3, "xs:string")
    axis = stringArg(xc, args, 4, "xs:string")
    if not axis in ('descendant-or-self', 'child-or-self', 'descendant', 'child'):
        return ()
    dimConcept = xc.modelXbrl.qnameConcepts.get(qnDim)
    if dimConcept is None or not dimConcept.isDimensionItem:
        raise XPathContext.XPathException(p, 'xfie:invalidDimensionQName', _('Argument 1 {0} is not a dimension concept QName.').format(qnDim))
    memConcept = xc.modelXbrl.qnameConcepts.get(qnMem)
    if memConcept is None or not memConcept.isDomainMember:
        # removed error 2011-03-10: raise XPathContext.XPathException(p, 'xfie:unrecognisedExplicitDimensionValueQName', _('Argument 1 {0} is not a member concept QName.').format(qnMem))
        return ()
    relationshipSet = xc.modelXbrl.relationshipSet(arcroleURI, linkroleURI)
    if relationshipSet is not None:
        members = set()
        ''' removed 2011-03-10:
        linkQnames = set()
        arcQnames = set()
        '''
        if axis.endswith("-or-self"):
            members.add(qnMem)
        fromRels = relationshipSet.fromModelObject(memConcept)
        if fromRels is not None:
            filter_member_network_members(relationshipSet, fromRels, axis.startswith("descendant"), members=members)
            ''' removed 2011-03-10:
            if len(linkQnames) > 1 or len(arcQnames) > 1:
                raise XPathContext.XPathException(p, 'xfie:ambiguousFilterMemberNetwork',
                          _('Network of linkrole {0} and arcrole {1} dimension {2} from {3} is ambiguous because of multiple link elements, {4}, or arc elements {5}').format(
                            linkroleURI, arcroleURI, qnDim, qnMem, linkQnames, arcQnames))
            '''
            return members
        # no fromRels, must be a toRel or else the qname is not in the member network
        if relationshipSet.toModelObject(memConcept):
            return members  # valid situation, the member exists as a leaf node
    # removed error 2011-03-10: raise XPathContext.XPathException(p, 'xfie:unrecognisedExplicitDimensionValueQName', _('Argument 1 {0} member is not in the network.').format(qnMem))
    return ()

def filter_member_network_members(relationshipSet, fromRels, recurse, members=None, relationships=None, linkQnames=None, arcQnames=None):
    if members is None:
        members = set()
    for modelRel in fromRels:
        toConcept = modelRel.toModelObject
        toConceptQname = toConcept.qname
        if linkQnames is not None:
            linkQnames.add(modelRel.linkQname)
        if arcQnames is not None:
            arcQnames.add(modelRel.qname)
        if toConceptQname not in members:
            members.add(toConceptQname)
            if relationships is not None:
                relationships.add(modelRel)
            if recurse:
                filter_member_network_members(relationshipSet, relationshipSet.fromModelObject(toConcept), recurse, members, relationships, linkQnames, arcQnames)

def filter_member_DRS_selection(xc, p, args):
    if len(args) != 5: raise XPathContext.FunctionNumArgs()
    qnDim = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    qnPriItem = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    qnMem = qnameArg(xc, p, args, 2, 'QName', emptyFallback=None)
    linkroleURI = stringArg(xc, args, 3, "xs:string")
    if not linkroleURI:  # '' or ()
        linkroleURI = None  # select all ELRs
    axis = stringArg(xc, args, 4, "xs:string")
    if not axis in ('DRS-descendant', 'DRS-child'):
        return ()
    memSelectionQnames = set()
    dimConcept = xc.modelXbrl.qnameConcepts.get(qnDim)
    if dimConcept is None or dimConcept.qname is None or dimConcept.qname.namespaceURI == XbrlConst.xbrli:
        raise XPathContext.XPathException(p, 'xfie:invalidDimensionQName', _('Argument 1 {0} is not in the DTS.').format(qnDim))
    elif not dimConcept.isDimensionItem:
        raise XPathContext.XPathException(p, 'xfie:invalidDimensionQName', _('Argument 1 {0} is not a dimension.').format(qnDim))
    priItemConcept = xc.modelXbrl.qnameConcepts.get(qnPriItem)
    if priItemConcept is None  or priItemConcept.qname is None  or priItemConcept.qname.namespaceURI == XbrlConst.xbrli:
        raise XPathContext.XPathException(p, 'xfie:invalidPrimaryItemConceptQName', _('Argument 2 {0} is not in the DTS.').format(qnPriItem))
    elif not priItemConcept.isPrimaryItem:
        raise XPathContext.XPathException(p, 'xfie:invalidPrimaryItemConceptQName', _('Argument 2 {0} is not a primary item.').format(qnPriItem))
    memConcept = xc.modelXbrl.qnameConcepts.get(qnMem)
    if memConcept is None or not memConcept.isDomainMember or not dimConcept.isDimensionItem:
        # not an error, just don't find anything
        return ()
    for hcELR, hcRels in priItemElrHcRels(xc, priItemConcept, linkroleURI).items():
        if not linkroleURI or linkroleURI == hcELR:
            for hasHcRel in hcRels:
                hcConcept = hasHcRel.toModelObject
                if hasHcRel.arcrole == XbrlConst.all:
                    dimELR = (hasHcRel.targetRole or hcELR)
                    for hcDimRel in xc.modelXbrl.relationshipSet(XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
                        if dimConcept == hcDimRel.toModelObject:
                            filter_member_DRS_members(xc,
                                                      xc.modelXbrl.relationshipSet(XbrlConst.dimensionDomain,
                                                                                   (hcDimRel.targetRole or dimELR))
                                                      .fromModelObject(dimConcept),
                                                      axis,
                                                      memConcept,
                                                      False,
                                                      set(),
                                                      memSelectionQnames)
    return memSelectionQnames

def filter_member_DRS_members(xc, fromRels, axis, memConcept, inSelection, visited, memSelectionQnames):
    for rel in fromRels:
        toConcept = rel.toModelObject
        toConceptQname = toConcept.qname
        nestedSelection = inSelection
        if rel.fromModelObject == memConcept or inSelection:  # from is the asked-for parent
            memSelectionQnames.add(toConceptQname) # to is a child or descendant
            nestedSelection = True
        if toConceptQname not in visited and (not nestedSelection or axis == "DRS-descendant"):
            visited.add(toConcept)
            filter_member_DRS_members(xc,
                                      xc.modelXbrl.relationshipSet(XbrlConst.domainMember,
                                                                   (rel.targetRole or rel.linkrole))
                                      .fromModelObject(toConcept),
                                      axis,
                                      memConcept,
                                      nestedSelection,
                                      visited,
                                      memSelectionQnames)
            visited.discard(toConcept)

def dimension_default(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    qnDim = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    dimConcept = xc.modelXbrl.qnameConcepts.get(qnDim)
    if dimConcept is None or dimConcept.qname is None or dimConcept.qname.namespaceURI == XbrlConst.xbrli:
        raise XPathContext.XPathException(p, 'xfie:invalidDimensionQName', _('Argument 1 {0} is not in the DTS.').format(qnDim))
    elif not dimConcept.isDimensionItem:
        raise XPathContext.XPathException(p, 'xfie:invalidDimensionQName', _('Argument 1 {0} is not a dimension.').format(qnDim))
    for dimDefRel in xc.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).fromModelObject(dimConcept):
        dimConcept = dimDefRel.toModelObject
        if dimConcept is not None and dimConcept.isDomainMember:
            return [dimConcept.qname]
    return []

def fact_segment_remainder(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        return context.segNonDimValues
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_scenario_remainder(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        return context.scenNonDimValues
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_dim_value(xc, p, args, dimType):
    context = item_context(xc, args)
    qnDim = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    dimConcept = xc.modelXbrl.qnameConcepts.get(qnDim)
    if dimConcept is None or not dimConcept.isDimensionItem:
        raise XPathContext.XPathException(p,
                                          'xfie:invalid{0}DimensionQName'.format(dimType),
                                          _('Argument 1 {0} is not a dimension concept QName.').format(qnDim))
    if context is not None:
        return context.dimValue(qnDim)
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_has_explicit_dimension(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    dimValue = fact_dim_value(xc, p, args, "Explicit")
    return dimValue is not None and (isinstance(dimValue,QName) or
                                     dimValue.isExplicit)

def fact_has_typed_dimension(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    dimValue = fact_dim_value(xc, p, args, "Typed")
    return dimValue is not None and not isinstance(dimValue,QName) and dimValue.isTyped

def fact_explicit_dimension_value_value(xc, p, args):
    context = item_context(xc, args)
    if context is not None:
        qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=())
        if qn == (): raise XPathContext.FunctionArgType(2,"xbrl:QName")
        dimConcept = xc.modelXbrl.qnameConcepts.get(qn) # check qname is explicit dimension
        if dimConcept is None or not dimConcept.isExplicitDimension:
            raise XPathContext.XPathException(p, 'xfie:invalidExplicitDimensionQName', _('dimension does not specify an explicit dimension'))
        dimValue = context.dimValue(qn)
        if isinstance(dimValue, ModelDimensionValue) and dimValue.isExplicit:
            return dimValue.memberQname # known to be valid given instance is valid
        elif isinstance(dimValue, QName): #default, check if this is valid
            ''' removed 2011-03-01 FWG clarification that default always applies
            #note that there's no way to check one dimension without full set of others for validity
            modelItem = xc.modelItem(args[0][0])
            itemConcept = modelItem.concept
            from arelle.ValidateXbrlDimensions import checkPriItemDimValueValidity
            memConcept = xc.modelXbrl.qnameConcepts.get(dimValue)
            # remove check for pri item validity per FWG meeting notes 2011-01-13
            if itemConcept: # and checkPriItemDimValueValidity(xc, itemConcept, dimConcept, memConcept):
                return dimValue
            '''
            return dimValue
        return () # not an applicable primary item for default dimension
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_has_explicit_dimension_value(xc, p, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    return qnameArg(xc, p, args, 2, 'QName', emptyFallback=()) == fact_explicit_dimension_value_value(xc, p, args)

def fact_explicit_dimension_value(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    return fact_explicit_dimension_value_value(xc, p, args)

def fact_typed_dimension_value(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=())
        if qn == (): raise XPathContext.FunctionArgType(2,"xbrl:QName")
        modelConcept = xc.modelXbrl.qnameConcepts.get(qn) # check qname is explicit dimension
        if modelConcept is None or not modelConcept.isTypedDimension:
            raise XPathContext.XPathException(p, 'xfie:invalidTypedDimensionQName', _('dimension does not specify a typed dimension'))
        result = context.dimValue(qn)
        return result if result is not None else ()
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_typed_dimension_simple_value(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        qn = qnameArg(xc, p, args, 1, 'QName', emptyFallback=())
        if qn == (): raise XPathContext.FunctionArgType(2,"xbrl:QName")
        modelConcept = xc.modelXbrl.qnameConcepts.get(qn) # check qname is explicit dimension
        if modelConcept is None or not modelConcept.isTypedDimension:
            raise XPathContext.XPathException(p, 'xfie:invalidTypedDimensionQName', _('dimension does not specify a typed dimension'))
        result = context.dimValue(qn)
        if result is None:
            return ()
        typedMember = result.typedMember
        if typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "false") in ("true","1"):
            return ()
        if typedMember.xValid == VALID_NO_CONTENT:
            for _child in typedMember.iterchildren(): # has children
                raise XPathContext.XPathException(p, 'xqt-err:FOTY0012', _('dimension domain element is not atomizable'))
            return () # no error if no children
        return typedMember.xValue
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def fact_explicit_dimensions(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        return set(qn for qn, dim in context.qnameDims.items() if dim.isExplicit) | xc.modelXbrl.qnameDimensionDefaults.keys()
    return set()

def fact_typed_dimensions(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    context = item_context(xc, args)
    if context is not None:
        return set(qn for qn, dim in context.qnameDims.items() if dim.isTyped)
    return set()

def fact_dimension_s_equal2(xc, p, args):
    if len(args) != 3: raise XPathContext.FunctionNumArgs()
    context1 = item_context(xc, args, i=0)
    context2 = item_context(xc, args, i=1)
    if context1 is not None:
        if context2 is not None:
            qn = qnameArg(xc, p, args, 2, 'QName', emptyFallback=())
            if qn == (): raise XPathContext.FunctionArgType(3,"xbrl:QName")
            modelConcept = xc.modelXbrl.qnameConcepts.get(qn) # check qname is explicit dimension
            if modelConcept is None or not modelConcept.isDimensionItem:
                # raise XPathContext.XPathException(p, 'xfie:invalidTypedDimensionQName', _('dimension does not specify a typed dimension'))
                return False
            dimValue1 = context1.dimValue(qn)
            dimValue2 = context2.dimValue(qn)
            if dimValue1 is not None and isinstance(dimValue1,ModelDimensionValue):
                return dimValue1.isEqualTo(dimValue2, equalMode=XbrlUtil.S_EQUAL2)
            elif dimValue2 is not None and isinstance(dimValue2,ModelDimensionValue):
                return dimValue2.isEqualTo(dimValue1, equalMode=XbrlUtil.S_EQUAL2)
            return dimValue1 == dimValue2
        raise XPathContext.FunctionArgType(2,"xbrl:item")
    raise XPathContext.FunctionArgType(1,"xbrl:item")

def linkbase_link_roles(xc, p, args):
    if len(args) > 2: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 1)
    arcroleURI = stringArg(xc, args, 0, "xs:string")
    relationshipSet = inst.relationshipSet(arcroleURI)
    if relationshipSet:
        return [anyURI(linkrole) for linkrole in relationshipSet.linkRoleUris]
    return ()

def navigate_relationships(xc, p, args):
    raise xfiFunctionNotAvailable()

def concept_label(xc, p, args):
    if not 4 <= len(args) <= 5: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 4)
    qnSource = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    srcConcept = inst.qnameConcepts.get(qnSource)
    if srcConcept is None:
        return ""
    linkroleURI = stringArg(xc, args, 1, "xs:string", emptyFallback='')
    if not linkroleURI: linkroleURI = XbrlConst.defaultLinkRole
    labelroleURI = stringArg(xc, args, 2, "xs:string", emptyFallback='')
    if not labelroleURI: labelroleURI = XbrlConst.standardLabel
    lang = stringArg(xc, args, 3, "xs:string", emptyFallback='')
    relationshipSet = inst.relationshipSet(XbrlConst.conceptLabel,linkroleURI)
    if relationshipSet is not None:
        label = relationshipSet.label(srcConcept, labelroleURI, lang)
        if label is not None: return label
    return ""


def arcrole_definition(xc, p, args):
    if len(args) > 2: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 1)
    arcroleURI = stringArg(xc, args, 0, "xs:string", emptyFallback='')
    modelArcroleTypes = inst.arcroleTypes.get(arcroleURI)
    if modelArcroleTypes is not None and len(modelArcroleTypes) > 0:
        arcroledefinition = modelArcroleTypes[0].definition
        if arcroledefinition is not None: return arcroledefinition
    return ()

def role_definition(xc, p, args):
    if len(args) > 2: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 1)
    roleURI = stringArg(xc, args, 0, "xs:string", emptyFallback='')
    modelRoleTypes = inst.roleTypes.get(roleURI)
    if modelRoleTypes is not None and len(modelRoleTypes) > 0:
        roledefinition = modelRoleTypes[0].definition
        if roledefinition is not None: return roledefinition
    return ()

def fact_footnotes(xc, p, args):
    if len(args) > 6: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 5)
    itemObj = item(xc, args)
    linkroleURI = stringArg(xc, args, 1, "xs:string", emptyFallback='')
    if not linkroleURI: linkroleURI = XbrlConst.defaultLinkRole
    arcroleURI = stringArg(xc, args, 2, "xs:string", emptyFallback='')
    if not arcroleURI: arcroleURI = XbrlConst.factFootnote
    footnoteroleURI = stringArg(xc, args, 3, "xs:string", emptyFallback='')
    if not footnoteroleURI: footnoteroleURI = XbrlConst.footnote
    lang = stringArg(xc, args, 4, "xs:string", emptyFallback='')
    relationshipSet = inst.relationshipSet(arcroleURI,linkroleURI)
    if relationshipSet: # must return empty sequence, not None if no footnotes match filters
        return relationshipSet.label(itemObj, footnoteroleURI, lang, returnMultiple=True) or ()
    return ()

def concept_relationships(xc, p, args, nestResults=False):
    lenArgs = len(args)
    if not 4 <= lenArgs <= 8: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 7)
    qnSource = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    linkroleURI = stringArg(xc, args, 1, "xs:string")
    if not linkroleURI:
        linkroleURI = XbrlConst.defaultLinkRole
    elif linkroleURI == "XBRL-all-linkroles":
        linkroleURI = None
    arcroleURI = stringArg(xc, args, 2, "xs:string")
    axis = stringArg(xc, args, 3, "xs:string")
    if not axis in ('descendant', 'child', 'ancestor', 'parent', 'sibling', 'sibling-or-self'):
        raise XPathContext.FunctionArgType(3, "'descendant', 'child', 'ancestor', 'parent', 'sibling' or 'sibling-or-self'",
                                           errCode="xfie:InvalidConceptRelationParameters")
    if qnSource != XbrlConst.qnXfiRoot:
        srcConcept = inst.qnameConcepts.get(qnSource)
        if srcConcept is None:
            return ()
    if lenArgs > 4:
        generations = numericArg(xc, p, args, 4, "xs:integer", convertFallback=0)
        if axis in ('child', 'parent', 'sibling', 'sibling-or-self') and generations != 1:
            raise XPathContext.FunctionArgType(4, "generations must be 1 for 'child', 'parent', 'sibling' or 'sibling-or-self' axis",
                                               errCode="xfie:InvalidConceptRelationParameters")
    elif axis in ('child', 'parent', 'sibling', 'sibling-or-self'):
        generations = 1
    else:
        generations = 0
    if axis in ('child','parent','sibling', 'sibling-or-self'):
        generations = 1
    if axis == 'child':
        axis = 'descendant'
    elif axis == 'parent':
        axis = 'ancestor'
    if lenArgs > 5:
        qnLink = qnameArg(xc, p, args, 5, 'QName', emptyFallback=None)
    else:
        qnLink = None
    if lenArgs > 5:
        qnArc = qnameArg(xc, p, args, 6, 'QName', emptyFallback=None)
    else:
        qnArc = None

    removeSelf = axis == 'sibling'
    relationshipSet = inst.relationshipSet(arcroleURI, linkroleURI, qnLink, qnArc)
    if relationshipSet:
        result = []
        visited = {qnSource}
        if qnSource == XbrlConst.qnXfiRoot:
            if axis in ('sibling', 'sibling-or-self', 'ancestor'):
                return []
            roots = relationshipSet.rootConcepts
            visited = {c.qname for c in roots}
            rels = [rel for c in roots for rel in relationshipSet.fromModelObject(c)]
            if generations == 1:
                return rels
            if generations > 1:
                generations -= 1
        elif axis == 'descendant':
            rels = relationshipSet.fromModelObject(srcConcept)
        elif axis == 'ancestor': # includes first pass on parents of object to get sibling
            rels = relationshipSet.toModelObject(srcConcept)
        elif axis in ('sibling', 'sibling-or-self'):
            rels = relationshipSet.toModelObject(srcConcept)
            if rels:
                rels = relationshipSet.fromModelObject(rels[0].fromModelObject)
                axis = 'descendant'
            else: # must be a root, never has any siblings
                return []
        if rels:
            concept_relationships_step(xc, inst, relationshipSet, rels, axis, generations, result, visited, nestResults)
            if removeSelf:
                for i, rel in enumerate(result):
                    if rel.toModelObject == srcConcept:
                        result.pop(i)
                        break
            return result
    return ()

def concept_relationships_step(xc, inst, relationshipSet, rels, axis, generations, result, visited, nestResults):
    if rels:
        for modelRel in rels:
            concept = modelRel.toModelObject if axis == 'descendant' else modelRel.fromModelObject
            conceptQname = concept.qname
            result.append(modelRel)
            if generations > 1 or (generations == 0 and conceptQname not in visited):
                nextGen = (generations - 1) if generations > 1 else 0
                if generations == 0:
                    visited.add(conceptQname)
                if axis == 'descendant':
                    if relationshipSet.arcrole == "XBRL-dimensions":
                        stepRelationshipSet = inst.relationshipSet("XBRL-dimensions", modelRel.consecutiveLinkrole)
                    else:
                        stepRelationshipSet = relationshipSet
                    stepRels = stepRelationshipSet.fromModelObject(concept)
                else:
                    if relationshipSet.arcrole == "XBRL-dimensions":
                        stepRelationshipSet = inst.relationshipSet("XBRL-dimensions")
                        # search all incoming relationships for those with right consecutiveLinkrole
                        stepRels = [rel
                                    for rel in stepRelationshipSet.toModelObject(concept)
                                    if rel.consectuiveLinkrole == modelRel.linkrole]
                    else:
                        stepRelationshipSet = relationshipSet
                        stepRels = stepRelationshipSet.toModelObject(concept)
                if nestResults: # nested results are in a sub-list
                    nestedList = []
                else: # nested results flattened in top level results
                    nestedList = result
                concept_relationships_step(xc, inst, stepRelationshipSet, stepRels, axis, nextGen, nestedList, visited, nestResults)
                if nestResults and nestedList:  # don't append empty nested results
                    result.append(nestedList)
                if generations == 0:
                    visited.discard(conceptQname)

def relationship_from_concept(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    modelRel = anytypeArg(xc, args, 0, "arelle:ModelRelationship", None)
    if modelRel is not None:
        return modelRel.fromModelObject.qname
    raise XPathContext.FunctionArgType(1,"arelle:modelRelationship")

def relationship_to_concept(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    modelRel = anytypeArg(xc, args, 0, "arelle:ModelRelationship", None)
    if modelRel is not None:
        return modelRel.toModelObject.qname
    raise XPathContext.FunctionArgType(1,"arelle:modelRelationship")

def distinct_nonAbstract_parent_concepts(xc, p, args):
    lenArgs = len(args)
    if not 2 <= lenArgs <= 3: raise XPathContext.FunctionNumArgs()
    inst = instance(xc, p, args, 2)
    linkroleURI = stringArg(xc, args, 0, "xs:string")
    if not linkroleURI:
        linkroleURI = XbrlConst.defaultLinkRole
    arcroleURI = stringArg(xc, args, 1, "xs:string")
    # TBD allow instance as arg 2

    result = set()
    relationshipSet = inst.relationshipSet(arcroleURI, linkroleURI)
    if relationshipSet:
        for rel in relationshipSet.modelRelationships:
            fromModelObject = rel.fromModelObject
            toModelObject = rel.toModelObject
            if (isinstance(fromModelObject, ModelConcept) and
                isinstance(toModelObject, ModelConcept) and
                not fromModelObject.isAbstract and
                not toModelObject.isAbstract):
                result.add(fromModelObject.qname)
    return result

def relationship_element_attribute(xc, p, args, elementParent=False):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    modelRel = anytypeArg(xc, args, 0, "arelle:ModelRelationship", None)
    if modelRel is None: raise XPathContext.FunctionArgType(1,"arelle:modelRelationship")
    qnAttr = qnameArg(xc, p, args, 1, 'QName', emptyFallback=None)
    if qnAttr is None: raise XPathContext.FunctionArgType(2,"xs:QName")
    element = modelRel.arcElement
    if elementParent: element = element.getparent()
    return element_attribute(element, qnAttr)

def element_attribute(element, attrQname):
    attrTag = attrQname.clarkNotation
    modelAttribute = None
    try:
        modelAttribute = element.xAttributes[attrTag]
    except (AttributeError, TypeError, IndexError, KeyError):
        # may be lax or deferred validated
        try:
            xmlValidate(element.modelXbrl, element, attrQname)
            modelAttribute = element.xAttributes[attrTag]
        except (AttributeError, TypeError, IndexError, KeyError):
            pass
    if modelAttribute is None:
        value = element.get(attrTag)
        if value is not None:
            return value
    elif modelAttribute.xValid >= VALID:
        return modelAttribute.xValue
    return ()

def relationship_attribute(xc, p, args):
    return relationship_element_attribute(xc, p, args)

def relationship_link_attribute(xc, p, args):
    return relationship_element_attribute(xc, p, args, elementParent=True)

def element_name(xc, p, args, elementParent=False):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    modelRel = anytypeArg(xc, args, 0, "arelle:ModelRelationship", None)
    if modelRel is None: raise XPathContext.FunctionArgType(1,"arelle:modelRelationship")
    element = modelRel.arcElement
    if elementParent: element = element.getparent()
    return qname(element)

def relationship_name(xc, p, args):
    return element_name(xc, p, args)

def relationship_link_name(xc, p, args):
    return element_name(xc, p, args, elementParent=True)

def xbrl_instance(xc, p, args):
    raise xfiFunctionNotAvailable()

def  format_number(xc, p, args):
    if len(args) != 2: raise XPathContext.FunctionNumArgs()
    value = numericArg(xc, p, args, 0, missingArgFallback='NaN', emptyFallback='NaN')
    picture = stringArg(xc, args, 1, "xs:string", missingArgFallback='', emptyFallback='')
    try:
        return format_picture(xc.modelXbrl.locale, value, picture)
    except ValueError as err:
        raise XPathContext.XPathException(p, 'xfie:invalidPictureSyntax', str(err) )

# note that this function was initially in plugin functionsXmlCreation when it was named xfxc:element
def  create_element(xc, p, args):
    if not 2 <= len(args) <= 4: raise XPathContext.FunctionNumArgs()
    qn = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    attrArg = flattenSequence(args[1])
    # attributes have to be pairs
    if attrArg:
        if (len(attrArg) & 1 or
            any((not isinstance(arg, (QName, str))) or
                (isinstance(arg,str) and NCNamePattern.match(arg) is None)
                for i in range(0, len(attrArg),2)
                for arg in (attrArg[i],))):
            raise XPathContext.FunctionArgType(1,"((xs:qname|xs:string),xs:anyAtomicValue)", errCode="xfie:AttributesNotNameValuePairs")
        else:
            attrParam = [(attrArg[i],attrArg[i+1]) # need name-value pairs for XmlUtil function
                         for i in range(0, len(attrArg),2)]
    else:
        attrParam = None

    value = atomicArg(xc, p, args, 2, "xs:anyAtomicType", emptyFallback='')
    if not value: # be sure '' is None so no text node is created
        value = None
    if len(args) < 4:
        childElements = None
    else:
        childElements = xc.flattenSequence(args[3])
    if value and childElements:
        raise XPathContext.FunctionArgType(1,str(value), errCode="xfie:MixedContentError")

    # scratchpad instance document emulates fn:doc( ) to hold XML nodes
    scratchpadXmlDocUrl = "http://www.xbrl.org/2012/function/creation/xml_scratchpad.xml"
    if scratchpadXmlDocUrl in xc.modelXbrl.urlDocs:
        modelDocument = xc.modelXbrl.urlDocs[scratchpadXmlDocUrl]
    else:
        # create scratchpad xml document
        # this will get the fake instance document in the list of modelXbrl docs so that it is garbage collected
        from arelle import ModelDocument
        modelDocument = ModelDocument.create(xc.modelXbrl,
                                             ModelDocument.Type.UnknownXML,
                                             scratchpadXmlDocUrl,
                                             initialXml="<xfc:dummy xmlns:xfc='http://www.xbrl.org/2012/function/creation'/>")

    newElement = XmlUtil.addChild(modelDocument.xmlRootElement,
                                  qn,
                                  attributes=attrParam,
                                  text=value)
    if childElements:
        for element in childElements:
            if isinstance(element, etree.ElementBase):
                newElement.append(element)

    # node myst be validated for use in instance creation (typed dimension references)
    xmlValidate(xc.modelXbrl, newElement)

    return newElement

def any_identifier(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    for cntx in xc.modelXbrl.contextsInUse:
        return cntx.entityIdentifierElement
    return ()

def unique_identifiers(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    distinctIdentifiers = {}
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.entityIdentifier not in distinctIdentifiers:
            distinctIdentifiers[cntx.entityIdentifier] = cntx.entityIdentifierElement
    return [e for k,e in sorted(distinctIdentifiers.items(), key=lambda i:i[0])]

def single_unique_identifier(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return len(set(cntx.entityIdentifier for cntx in xc.modelXbrl.contextsInUse)) == 1

def any_start_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isStartEndPeriod:
            return cntx.startDatetime
    return ()

def unique_start_dates(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    distinctStartDates = set()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isStartEndPeriod:
            distinctStartDates.add(cntx.startDatetime)
    return [sorted(distinctStartDates, key=lambda d:(d.tzinfo is None,d))]

def single_unique_start_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return len(set(cntx.startDatetime for cntx in xc.modelXbrl.contextsInUse if cntx.isStartEndPeriod)) == 1

def any_end_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isStartEndPeriod:
            return cntx.endDatetime
    return ()

def unique_end_dates(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    distinctStartDates = set()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isStartEndPeriod:
            distinctStartDates.add(cntx.endDatetime)
    return [sorted(distinctStartDates, key=lambda d:(d.tzinfo is None,d))]

def single_unique_end_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return len(set(cntx.endDatetime for cntx in xc.modelXbrl.contextsInUse if cntx.isStartEndPeriod)) == 1

def any_instant_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isInstantPeriod:
            return cntx.instantDatetime
    return ()

def unique_instant_dates(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    distinctStartDates = set()
    for cntx in xc.modelXbrl.contextsInUse:
        if cntx.isInstantPeriod:
            distinctStartDates.add(cntx.instantDatetime)
    return [sorted(distinctStartDates, key=lambda d:(d.tzinfo is None,d))]

def single_unique_instant_date(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return len(set(cntx.instantDatetime for cntx in xc.modelXbrl.contextsInUse if cntx.isInstantPeriod)) == 1

def filingIndicatorValues(inst, filedValue):
    filingIndicators = set()
    for fact in inst.factsByQname[XbrlConst.qnEuFiIndFact]:
        if fact.parentElement.qname == XbrlConst.qnEuFiTuple and fact.get(XbrlConst.cnEuFiIndAttr,"true") == filedValue:
            filingIndicators.add(fact.stringValue.strip())
    for fact in inst.factsByQname[XbrlConst.qnFiFact]:
        if fact.context is not None and XbrlConst.qnFiDim in fact.context.qnameDims and fact.value.strip() == filedValue:
            fiValue = fact.context.qnameDims[XbrlConst.qnFiDim].stringValue.strip()
            if fiValue:
                filingIndicators.add(fiValue)
    return filingIndicators

def positive_filing_indicators(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return sorted(filingIndicatorValues(xc.modelXbrl, "true"))

def positive_filing_indicator(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    ind = anytypeArg(xc, args, 0, "xs:string", None)
    if ind is None: raise XPathContext.FunctionArgType(1,"xs:string")
    return ind in filingIndicatorValues(xc.modelXbrl, "true")

def negative_filing_indicators(xc, p, args):
    if len(args) != 0: raise XPathContext.FunctionNumArgs()
    return sorted(filingIndicatorValues(xc.modelXbrl, "false"))

def negative_filing_indicator(xc, p, args):
    if len(args) != 1: raise XPathContext.FunctionNumArgs()
    ind = anytypeArg(xc, args, 0, "xs:string", None)
    if ind is None: raise XPathContext.FunctionArgType(1,"xs:string")
    return ind in filingIndicatorValues(xc.modelXbrl, "false")

xfiFunctions = {
    'context': context,
    'unit': unit,
    'unit-numerator': unit_numerator,
    'unit-denominator': unit_denominator,
    'measure-name': measure_name,
    'period': period,
    'context-period': context_period,
    'is-start-end-period': is_start_end_period,
    'is-forever-period': is_forever_period,
    'is-duration-period': is_duration_period,
    'is-instant-period': is_instant_period,
    'period-start': period_start,
    'period-end': period_end,
    'period-instant': period_instant,
    'entity' : entity,
    'context-entity' : context_entity,
    'identifier': identifier,
    'context-identifier': context_identifier,
    'entity-identifier': entity_identifier,
    'identifier-value': identifier_value,
    'identifier-scheme': identifier_scheme,
    'segment': segment,
    'entity-segment': entity_segment,
    'context-segment': context_segment,
    'scenario': scenario,
    'context-scenario': context_scenario,
    'fact-identifier-value': fact_identifier_value,
    'fact-identifier-scheme': fact_identifier_scheme,
    'is-non-numeric' : non_numeric,
    'is-numeric' : numeric,
    'is-fraction' : fraction,
    'precision': precision,
    'decimals': decimals,
    'uncovered-aspect' : uncovered_aspect,
    'has-fallback-value' : has_fallback_value,
    'uncovered-non-dimensional-aspects' : uncovered_non_dimensional_aspects,
    'uncovered-dimensional-aspects': uncovered_dimensional_aspects,
    'identical-nodes': identical_nodes,
    's-equal': s_equal,
    'u-equal': u_equal,
    'v-equal': v_equal,
    'c-equal': c_equal,
    'identical-node-set' : identical_node_set,
    's-equal-set': s_equal_set,
    'v-equal-set': v_equal_set,
    'c-equal-set': c_equal_set,
    'u-equal-set': u_equal_set,
    'x-equal': x_equal,
    'duplicate-item': duplicate_item,
    'duplicate-tuple': duplicate_tuple,
    'p-equal': p_equal,
    'cu-equal': cu_equal,
    'pc-equal': pc_equal,
    'pcu-equal': pcu_equal,
    'start-equal': start_equal,
    'end-equal': end_equal,
    'taxonomy-refs': taxonomy_refs,
    'nodes-correspond': nodes_correspond,
    'facts-in-instance': facts_in_instance,
    'items-in-instance': items_in_instance,
    'tuples-in-instance': tuples_in_instance,
    'items-in-tuple': items_in_tuple,
    'tuples-in-tuple': tuples_in_tuple,
    'non-nil-facts-in-instance': non_nil_facts_in_instance,
    'concept-balance': concept_balance,
    'concept-period-type': concept_period_type,
    'concept-custom-attribute': concept_custom_attribute,
    'concept-data-type': concept_data_type,
    'concept-data-type-derived-from' : concept_data_type_derived_from,
    'concept-substitutions': concept_substitutions,
    'concepts-from-local-name': concepts_from_local_name,
    'concepts-from-local-name-pattern': concepts_from_local_name_pattern,
    'filter-member-network-selection' : filter_member_network_selection,
    'filter-member-DRS-selection' : filter_member_DRS_selection,
    'dimension-default': dimension_default,
    'fact-segment-remainder': fact_segment_remainder,
    'fact-scenario-remainder': fact_scenario_remainder,
    'fact-has-explicit-dimension': fact_has_explicit_dimension,
    'fact-has-typed-dimension': fact_has_typed_dimension,
    'fact-has-explicit-dimension-value': fact_has_explicit_dimension_value,
    'fact-explicit-dimension-value': fact_explicit_dimension_value,
    'fact-typed-dimension-value': fact_typed_dimension_value,
    'fact-typed-dimension-simple-value': fact_typed_dimension_simple_value,
    'fact-explicit-dimensions': fact_explicit_dimensions,
    'fact-typed-dimensions': fact_typed_dimensions,
    'fact-dimension-s-equal2': fact_dimension_s_equal2,
    'linkbase-link-roles': linkbase_link_roles,
    'concept-label': concept_label,
    'arcrole-definition': arcrole_definition,
    'role-definition': role_definition,
    'fact-footnotes': fact_footnotes,
    'concept-relationships': concept_relationships,
    'relationship-from-concept': relationship_from_concept,
    'relationship-to-concept': relationship_to_concept,
    'distinct-nonAbstract-parent-concepts': distinct_nonAbstract_parent_concepts,
    'relationship-attribute': relationship_attribute,
    'relationship-link-attribute': relationship_link_attribute,
    'relationship-name': relationship_name,
    'relationship-link-name': relationship_link_name,
    'xbrl-instance': xbrl_instance,
    'format-number':  format_number,
    'create-element': create_element,
    'any-identifier': any_identifier,
    'unique-identifiers': unique_identifiers,
    'single-unique-identifier': single_unique_identifier,
    'any-start-date': any_start_date,
    'unique-start-dates': unique_start_dates,
    'single-unique-start-date': single_unique_start_date,
    'any-end-date': any_end_date,
    'unique-end-dates': unique_end_dates,
    'single-unique-end-date': single_unique_end_date,
    'any-instant-date': any_instant_date,
    'unique-instant-dates': unique_instant_dates,
    'single-unique-instant-date': single_unique_instant_date,
    'positive-filing-indicators': positive_filing_indicators,
    'positive-filing-indicator': positive_filing_indicator,
    'negative-filing-indicators': negative_filing_indicators,
    'negative-filing-indicator': negative_filing_indicator,
     }
