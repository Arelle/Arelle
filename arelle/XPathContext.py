'''
Created on Dec 30, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle.XPathParser import (VariableRef, QNameDef, OperationDef, RangeDecl, Expr, ProgHeader,
                          exceptionErrorIndication)
from arelle import (ModelXbrl, XbrlConst, XmlUtil)
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact
from arelle.ModelValue import (qname,QName,dateTime, DateTime, DATEUNION, DATE, DATETIME, anyURI, AnyURI)

class XPathException(Exception):
    def __init__(self, progStep, code, message):
        self.column = None
        if isinstance(progStep, OperationDef):
            self.line = progStep.sourceStr
            self.column = progStep.loc
        elif isinstance(progStep, ProgHeader):
            self.line = progStep.sourceStr
        self.code = code
        self.message = message
        self.args = ( self.__repr__(), )
    def __repr__(self):
        if self.column:
            return _('[{0}] exception at {1} in {2}').format(self.code, self.column, self.message)
        else:
            return _('[{0}] exception {1}').format(self.code, self.message)
    @property
    def sourceErrorIndication(self):
        return exceptionErrorIndication(self)
            
    
class FunctionNumArgs(Exception):
    def __init__(self):
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("Exception: Number of arguments mismatch")
    
class FunctionArgType(Exception):
    def __init__(self, argIndex, expectedType):
        self.argNum = argIndex + 1
        self.expectedType = expectedType
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("Exception: Arg {0} expected type {1}").format(self.argNum, self.expectedType)
    
class FunctionNotAvailable(Exception):
    def __init__(self, name=None):
        self.name = name
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _("Exception, function not available: {0}").format(self.name)
    
   
def create(modelXbrl, inputXbrlInstance=None, sourceElement=None):
    return XPathContext(modelXbrl, 
                        inputXbrlInstance if inputXbrlInstance else modelXbrl.modelDocument,
                        sourceElement)

class XPathContext:
    def __init__(self, modelXbrl, inputXbrlInstance, sourceElement, inScopeVars=None):
        self.modelXbrl = modelXbrl
        self.inputXbrlInstance = inputXbrlInstance
        self.outputLastContext = {}   # last context element output per output instance
        self.outputLastUnit = {}
        self.outputLastFact = {}
        self.sourceElement = sourceElement
        self.contextItem = self.inputXbrlInstance.xmlRootElement
        self.progHeader = None
        self.traceType = None
        self.variableSet = None
        self.inScopeVars = {} if inScopeVars is None else inScopeVars
        if inputXbrlInstance: 
            self.inScopeVars[XbrlConst.qnStandardInputInstance] = inputXbrlInstance.modelXbrl
        
    @property
    def formulaOptions(self):
        return self.modelXbrl.modelManager.formulaOptions
        
    def evaluate(self, exprStack, contextItem=None, resultStack=None, parentOp=None):
        if resultStack is None: resultStack =  []
        if contextItem is None: contextItem = self.contextItem
        setProgHeader = False
        for p in exprStack:
            result = None
            if isinstance(p,(str,int,float)):
                result = p
            elif isinstance(p,VariableRef):
                if p.name in self.inScopeVars:
                    result = self.inScopeVars[p.name]
            elif isinstance(p,QNameDef):
                # step axis operation
                if len(resultStack) == 0 or not self.isNodeSequence(resultStack[-1]):
                    resultStack.append( [ contextItem, ] )
                result = self.stepAxis(parentOp, p, resultStack.pop() )
            elif isinstance(p,OperationDef):
                op = p.name
                if isinstance(op, QNameDef): # function call
                    args = self.evaluate(p.args, contextItem=contextItem)
                    ns = op.namespaceURI; localname = op.localName
                    try:
                        from arelle import (FunctionXs, FunctionFn, FunctionXfi, FunctionCustom)
                        if op in self.modelXbrl.modelCustomFunctionSignatures:
                            result = FunctionCustom.call(self, p, op, contextItem, args)
                        elif op.unprefixed and localname in {'attribute', 'comment', 'document-node', 'element', 
                           'item', 'node', 'processing-instruction', 'schema-attribute', 'schema-element', 'text'}:
                            # step axis operation
                            if len(resultStack) == 0 or not self.isNodeSequence(resultStack[-1]):
                                if isinstance(contextItem, (tuple,list)):
                                    resultStack.append( contextItem )
                                else:
                                    resultStack.append( [ contextItem, ] )
                            result = self.stepAxis(parentOp, p, resultStack.pop() )
                        elif op.unprefixed or ns == XbrlConst.fn:
                            result = FunctionFn.call(self, p, localname, contextItem, args)
                        elif ns == XbrlConst.xfi or ns == XbrlConst.xff:
                            result = FunctionXfi.call(self, p, localname, args)
                        elif ns == XbrlConst.xsd:
                            result = FunctionXs.call(self, p, localname, args)
                        else:
                            raise XPathException(p, 'err:XPST0017', _('Function call not identified.'))
                    except FunctionNumArgs:
                        raise XPathException(p, 'err:XPST0017', _('Number of arguments do not match signature arity.'))
                    except FunctionArgType as err:
                        raise XPathException(p, 'err:XPTY0004', _('Argument {0} does not match expected type {1}.')
                                             .format(err.argNum, err.expectedType))
                    except FunctionNotAvailable:
                        raise XPathException(p, 'arelle:functDeferred', _('Function {0} is not available in this build.')
                                             .format(str(op)))
                elif op in {'+', '-', '*', 'div', 'idiv', 'mod', 'to', 'gt', 'ge', 'eq', 'ne', 'lt', 'le'}:
                    # binary arithmetic operations and value comparisons
                    s1 = self.atomize( p, resultStack.pop() ) if len(resultStack) > 0 else []
                    s2 = self.atomize( p, self.evaluate(p.args, contextItem=contextItem) )
                    # value comparisons
                    if len(s1) > 1 or len(s2) > 1:
                        raise XPathException(p, 'err:XPTY0004', _("Value operation '{0}' sequence length error").format(op))
                    if len(s1) == 0 or len(s2) == 0:
                        result = []
                    else:
                        op1 = s1[0]
                        op2 = s2[0]
                        from arelle.FunctionUtil import (testTypeCompatiblity)
                        testTypeCompatiblity( self, p, op, op1, op2 )
                        if op == '+':
                            result = op1 + op2 
                        elif op == '-':
                            result = op1 - op2
                        elif op == '*':
                            result = op1 * op2
                        elif op in ('div', 'idiv', "mod"):
                            try:
                                if op == 'div':
                                    result = op1 / op2
                                elif op == 'idiv':
                                    result = op1 // op2
                                elif op == 'mod':
                                    result = op1 % op2
                            except ZeroDivisionError:
                                raise XPathException(p, 'err:FOAR0001', _('Attempt to divide by zero: {0} {1} {2}.')
                                                     .format(op1, op, op2))
                        elif op == 'ge':
                            result = op1 >= op2
                        elif op == 'gt':
                            result = op1 > op2
                        elif op == 'le':
                            result = op1 <= op2
                        elif op == 'lt':
                            result = op1 < op2
                        elif op == 'eq':
                            result = op1 == op2
                        elif op == 'ne':
                            result = op1 != op2
                        elif op == 'to':
                            result = range( int(op1), int(op2) + 1 )
                elif op in {'>', '>=', '=', '!=', '<', '<='}:
                    # general comparisons
                    s1 = self.atomize( p, resultStack.pop() ) if len(resultStack) > 0 else []
                    s2 = self.atomize( p, self.evaluate(p.args, contextItem=contextItem) )
                    result = [];
                    for op1 in s1:
                        for op2 in s2:
                            if op == '>=':
                                result = op1 >= op2
                            elif op == '>':
                                result = op1 > op2
                            elif op == '<=':
                                result = op1 <= op2
                            elif op == '<':
                                result = op1 < op2
                            elif op == '=':
                                result = op1 == op2
                            elif op == '!=':
                                result = op1 != op2
                            if result:
                                break
                        if result:
                            break
                elif op in {'is', '>>', '<<'}:
                    # node comparisons
                    s1 = resultStack.pop() if len(resultStack) > 0 else []
                    s2 = self.evaluate(p.args, contextItem=contextItem)
                    if len(s1) > 1 or len(s2) > 1 or not self.isNodeSequence(s1) or not self.isNodeSequence(s2[0]):
                        raise XPathException(p, 'err:XPTY0004', _('Node comparison sequence error'))
                    if len(s1) == 0 or len(s2[0]) == 0:
                        result = []
                    else:
                        n1 = s1[0]
                        n2 = s2[0][0]
                        result = False;
                        for op1 in s1:
                            for op2 in s2:
                                if op == 'is':
                                    result = n1 == n2
                                elif op == '>>':
                                    result = op1 > op2
                                elif op == '<<':
                                    result = op1 <= op2
                            if result:
                                break
                elif op in {'intersect','except','union','|'}:
                    # node comparisons
                    s1 = resultStack.pop() if len(resultStack) > 0 else []
                    s2 = self.flattenSequence(self.evaluate(p.args, contextItem=contextItem))
                    if not self.isNodeSequence(s1) or not self.isNodeSequence(s2):
                        raise XPathException(p, 'err:XPTY0004', _('Node operation sequence error'))
                    set1 = set(s1)
                    set2 = set(s2)
                    if op == 'intersect':
                        resultset = set1 & set2
                    elif op == 'except':
                        resultset = set1 - set2
                    elif op == 'union' or op == '|':
                        resultset = set1 | set2
                    # convert to a list in document order
                    result = self.documentOrderedNodes(resultset)
                elif op in {'and', 'or'}:
                    # general comparisons
                    if len(resultStack) == 0:
                        result = []
                    else:
                        op1 = self.effectiveBooleanValue( p, resultStack.pop() )
                        op2 = self.effectiveBooleanValue( p, self.evaluate(p.args, contextItem=contextItem) )
                        result = False;
                        if op == 'and':
                            result = op1 and op2
                        elif op == 'or':
                            result = op1 or op2
                elif op in {'u+', 'u-'}:
                    s1 = self.atomize( p, self.evaluate(p.args, contextItem=contextItem) )
                    if len(s1) > 1:
                        raise XPathException(p, 'err:XPTY0004', _('Unary expression sequence length error'))
                    if len(s1) == 0:
                        result = []
                    else:
                        op1 = s1[0]
                        if op == 'u+':
                            result = op1 
                        elif op == 'u-':
                            result = -op1
                elif op == 'instance':
                    result = False
                    s1 = self.flattenSequence( resultStack.pop() ) if len(resultStack) > 0 else []
                    arity = len(s1)
                    if len(p.args) > 1:
                        occurenceIndicator = p.args[1]
                        if (occurenceIndicator == '?' and arity in (0,1) ) or \
                           (occurenceIndicator == '+' and arity >= 1) or \
                           (occurenceIndicator == '*'):
                            result = True
                    elif arity == 1:
                        result = True
                    if result and len(p.args) > 0:
                        t = p.args[0]
                        for x in s1:
                            if isinstance(t, QNameDef):
                                if t.namespaceURI == XbrlConst.xsd:
                                    type = {
                                           "integer": int,
                                           "string": str,
                                           "decimal": float,
                                           "double": float,
                                           "float": float,
                                           "boolean": bool,
                                           "QName": QName,
                                           "anyURI": AnyURI,
                                           "date": DateTime,
                                           "dateTime": DateTime,
                                            }.get(t.localName)
                                    if type:
                                        result = isinstance(x, type)
                                        if result and type == DateTime:
                                            result = x.dateOnly == (t.localName == "date")
                            elif isinstance(t, OperationDef):
                                if t.name == "element" and isinstance(x,ModelObject):
                                    if len(t.args) >= 1:
                                        qn = t.args[0]
                                        if qn== '*' or (isinstance(qn,QNameDef) and qn == x):
                                            result = True
                                            if len(t.args) >= 2 and isinstance(t.args[1],QNameDef):
                                                modelXbrl = x.modelDocument.modelXbrl
                                                modelConcept = modelXbrl.qnameConcepts.get(qname(x))
                                                if not modelConcept.instanceOfType(t.args[1]):
                                                    result = False
                            if not result: 
                                break
                elif op == 'sequence':
                    result = self.evaluate(p.args, contextItem=contextItem)
                elif op == 'predicate':
                    result = self.predicate(p, resultStack.pop())
                elif op in {'for','some','every'}: # for, some, every
                    result = []
                    self.evaluateRangeVars(op, p.args[0], p.args[1:], contextItem, result)
                elif op == 'if':
                    test = self.effectiveBooleanValue( p, self.evaluate(p.args[0].expr[0], contextItem=contextItem) )
                    result = self.evaluate(p.args[1 if test else 2].args, contextItem=contextItem)
                elif op == '.':
                    result = contextItem
                elif op == '..':
                    result = XmlUtil.parent(contextItem)
                elif op in ('/', '//', 'rootChild', 'rootDescendant'):
                    if op in ('rootChild', 'rootDescendant'):
                        # fix up for multi-instance
                        resultStack.append( [self.inputXbrlInstance.xmlDocument,] )
                        op = '/' if op == 'rootChild' else '//'
                    # contains QNameDefs and predicates
                    if len(resultStack) > 0:
                        innerFocusNodes = resultStack.pop()
                    else:
                        innerFocusNodes = contextItem
                    navSequence = []
                    for innerFocusNode in self.flattenSequence(innerFocusNodes):
                        self.evaluate(p.args, contextItem=innerFocusNode, resultStack=navSequence, parentOp=op)
                    result = self.documentOrderedNodes(self.flattenSequence(navSequence))
            elif isinstance(p,ProgHeader):
                self.progHeader = p
                from arelle.ModelFormulaObject import Trace
                if p.traceType not in (Trace.MESSAGE, Trace.CUSTOM_FUNCTION): 
                    self.traceType = p.traceType
                setProgHeader = True
            if result is not None:   # note: result can be False which gets appended to resultStack
                resultStack.append( self.flattenSequence( result ) )  
        if setProgHeader:
            self.progHeader = None                  
        return resultStack
    
    def evaluateBooleanValue(self, exprStack, contextItem=None):
        if len(exprStack) > 0 and isinstance(exprStack[0], ProgHeader):
            progHeader = exprStack[0]
            return self.effectiveBooleanValue(progHeader, self.evaluate(exprStack,contextItem))
        return False
                    
    def evaluateAtomicValue(self, exprStack, type, contextItem=None):
        if exprStack and len(exprStack) > 0 and isinstance(exprStack[0], ProgHeader):
            progHeader = exprStack[0]
            result = self.atomize( progHeader, self.evaluate( exprStack, contextItem=contextItem ) )
            if isinstance(type, QName) and type.namespaceURI == XbrlConst.xsd:
                type = "xs:" + type.localName
            if isinstance(type,str):
                prefix,sep,localName = type.partition(':')
                if prefix == 'xs':
                    if localName.endswith('*'): localName = localName[:-1]
                    if hasattr(result, "__iter__") and not isinstance(result, str):
                        from arelle import (FunctionXs)
                        if type.endswith('*'):
                            return[FunctionXs.call(self,progHeader,localName,(r,)) for r in result]
                        elif len(result) > 0:
                            return FunctionXs.call(self,progHeader,localName,(result[0],))
            else: # no conversion
                if len(result) == 0: return None
                elif len(result) == 1: return result[0]
                else: return result
        return None
                    
    def evaluateRangeVars(self, op, p, args, contextItem, result):
        if isinstance(p, RangeDecl):
            r = self.evaluate(p.bindingSeq, contextItem=contextItem)
            if len(r) == 1: # should be an expr single
                r = r[0]
                if hasattr(r, '__iter__') and not isinstance(r, str):
                    if len(r) == 1 and isinstance(r[0],range):
                        r = r[0]
                    rvQname = p.rangeVar.name
                    hasPrevValue = rvQname in self.inScopeVars
                    if hasPrevValue: 
                        prevValue = self.inScopeVars[rvQname]
                    for rv in r:
                        self.inScopeVars[rvQname] = rv 
                        self.evaluateRangeVars(op, args[0], args[1:], contextItem, result)
                        if op != 'for' and len(result) > 0:
                            break	# short circuit evaluation
                    if op == 'every' and len(result) == 0:
                        result.append( True )   # true if no false result returned during iteration
                    if hasPrevValue: 
                        self.inScopeVars[rvQname] = prevValue
        elif isinstance(p, Expr):
            if p.name == 'return':
                result.append( self.evaluate(p.expr, contextItem=contextItem) )
            elif p.name == 'satisfies':
                boolresult = self.effectiveBooleanValue(p, self.evaluate(p.expr, contextItem=contextItem))
                if (op == 'every') != boolresult:
                    # stop short circuit eval
                    result.append( boolresult )
            
    def isNodeSequence(self, x):
        for el in x:
            if not isinstance(el,ModelObject):
                return False
        return True

    def stepAxis(self, op, p, sourceSequence):
        targetSequence = []
        for node in sourceSequence:
            if not isinstance(node,ModelObject):
                raise XPathException(p, 'err:XPTY0020', _('Axis step {0} context item is not a node: {1}').format(op, node))
            targetNodes = []
            if isinstance(p,QNameDef):
                ns = p.namespaceURI; localname = p.localName
                if p.isAttribute:
                    if node.get(p.clarkNotation) is not None:
                        targetNodes.append(node.get(p.clarkNotation))
                elif op == '/' or op is None:
                    targetNodes = XmlUtil.children(node, ns, localname)
                elif op == '//':
                    targetNodes = XmlUtil.descendants(node, ns, localname)
                elif op == '..':
                    targetNodes = [ XmlUtil.parent(node) ]
            elif isinstance(p, OperationDef) and isinstance(p.name,QNameDef):
                if p.name.localName == "text":
                    targetNodes = [XmlUtil.text(node)]
                # todo: add element, attribute, node, etc...
            targetSequence.extend(targetNodes)
        return targetSequence
        
    def predicate(self, p, sourceSequence):
        targetSequence = []
        sourcePosition = 0
        for item in sourceSequence:
            sourcePosition += 1
            predicateResult = self.evaluate(p.args, contextItem=item)
            if len(predicateResult) == 1: predicateResult = predicateResult[0] # first result
            if len(predicateResult) == 1 and isinstance(predicateResult[0],(int,float)):
                result = predicateResult[0]
                if isinstance(result, bool):  # note that bool is subclass of int
                    if result:
                        targetSequence.append(item)
                elif sourcePosition == result:
                    targetSequence.append(item)
            elif self.effectiveBooleanValue(p, predicateResult):
                    targetSequence.append(item)
        return targetSequence
            
    def atomize(self, p, x):
        # sequence
        if hasattr(x, '__iter__') and not isinstance(x, str):
            sequence = []
            for item in self.flattenSequence(x):
                atomizedItem = self.atomize(p, item)
                if atomizedItem != []:
                    sequence.append(atomizedItem)
            return sequence
        # individual items
        if isinstance(x, range): 
            return x
        baseXsdType = None
        e = None
        if isinstance(x, ModelFact):
            if x.isTuple:
                raise XPathException(p, 'err:FOTY0012', _('Atomizing tuple {0} that does not have a typed value').format(x))
            if x.isNil:
                return []
            baseXsdType = x.concept.baseXsdType
            v = x.value # resolves default value
            e = x
        else:
            if isinstance(x, ModelObject):
                e = x
            if e:
                if e.getAttributeNS(XbrlConst.xsi,"nil") == "true":
                    return []
                modelXbrl = x.ownerDocument.modelDocument.modelXbrl
                modelConcept = modelXbrl.qnameConcepts.get(qname(x))
                if modelConcept:
                    baseXsdType = modelConcept.baseXsdType
                v = XmlUtil.text(x)
        if baseXsdType in ("decimal", "float", "double"):
            try:
                x = float(v)
            except ValueError:
                raise XPathException(p, 'err:FORG0001', _('Atomizing {0} to a {1} does not have a proper value').format(x,baseXsdType))
        elif baseXsdType in ("integer",):
            try:
                x = int(v)
            except ValueError:
                raise XPathException(p, 'err:FORG0001', _('Atomizing {0} to an integer does not have a proper value').format(x))
        elif baseXsdType == "boolean":
            x = (v == "true" or v == "1")
        elif baseXsdType == "QName" and e:
            x = qname(e, v)
        elif baseXsdType == "anyURI":
            x = anyURI(v.strip())
        elif baseXsdType in ("normalizedString","token","language","NMTOKEN","Name","NCName","ID","IDREF","ENTITY"):
            x = v.strip()
        elif baseXsdType == "XBRLI_DATEUNION":
            x = dateTime(v, type=DATEUNION)
        elif baseXsdType == "date":
            x = dateTime(v, type=DATE)
        elif baseXsdType == "dateTime":
            x = dateTime(v, type=DATETIME)
        elif baseXsdType:
            x = str(v)
        return x
    
    def effectiveBooleanValue(self, p, x):
        from arelle.FunctionFn import boolean
        return boolean( self, p, None, (self.atomize( p, x ),) )

    # flatten into a sequence
    def flattenSequence(self, x, sequence=None):
        if sequence is None: 
            if isinstance(x, str) or isinstance(x,range) or not hasattr(x, '__iter__'):
                return [x]
            sequence = []
        for el in x:
            if hasattr(el, '__iter__') and not isinstance(el, str):
                self.flattenSequence(el, sequence=sequence)
            else:
                sequence.append(el)
        return sequence
    
    # order nodes
    def documentOrderedNodes(self, x):
        l = set()  # must have unique nodes only
        for e in x:
            if isinstance(e,ModelObject):
                h = e.objectIndex
            else:
                h = 0
            l.add((h,e))
        return [e for h,e in sorted(l)]
    
    def modelItem(self, x):
        modelItem = None
        if isinstance(x, (ModelFact, ModelInlineFact)) and x.isItem:
            return x
        return None

    def modelInstance(self, x):
        if isinstance(x, ModelXbrl.ModelXbrl):
            return x
        if isinstance(x, ModelObject):
            return x.modelXbrl
        return None
              