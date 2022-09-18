'''
Created on Sept 29, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.
'''
import logging
from .cdrParser import compileCdrGrammar, parse, astNode, astQnameLiteral
from .cdrModelObject import CONCEPT_FORMULA_ARCROLE, CdrFormula
from arelle.ModelDtsObject import ModelConcept

def hasCdrFormula(val):
    return bool(val.modelXbrl.relationshipSet(CONCEPT_FORMULA_ARCROLE))

def validate(val):
    modelXbrl = val.modelXbrl
    for e in ("xbrl.5.1.4.3:cycles", "xbrlgene:violatedCyclesConstraint"):
        if e in modelXbrl.errors:
            modelXbrl.info("info", _("CDR Formula validation skipped due to %(error)s error"),
                            modelObject=modelXbrl, error=e)
            return
    
    modelXbrl.profileStat()
    formulaOptions = modelXbrl.modelManager.formulaOptions
    modelXbrl.profileActivity()
    initialErrorCount = val.modelXbrl.logCount.get(logging._checkLevel('ERROR'), 0)
    cntlr = modelXbrl.modelManager.cntlr
    
    # compile grammar
    compileCdrGrammar(cntlr, modelXbrl.log)
    
    # compile formulas
    cdrFormulas = {}
    
    cntlr.modelManager.showStatus(_("compiling CDR formulas"))
    for modelRel in modelXbrl.relationshipSet(CONCEPT_FORMULA_ARCROLE).modelRelationships:
        fromModelObject = modelRel.fromModelObject
        if not isinstance(fromModelObject, ModelConcept):
            val.modelXbrl.error("cdrFormula:conceptFormulaSourceError",
                 _("Invalid concept-formula source object %(element)s"),
                 modelObject=(modelRel, fromModelObject), element=fromModelObject.elementQname)
        else:
            toModelObject = modelRel.toModelObject
            if not isinstance(toModelObject,CdrFormula):
                val.modelXbrl.error("cdrFormula:conceptFormulaTargetError",
                     _("Invalid concept-formula target object %(element)s"),
                     modelObject=(modelRel, toModelObject), element=toModelObject.elementQname)
            else:
                if parse(toModelObject):
                    cdrFormulas[fromModelObject.qname] = toModelObject
                    toModelObject.prog = []
                    toModelObject.formulaDependencies = set()
                
    # get dependencies of ast
    # check references            
    def checkNodes(nodes, formulaDependencies):
        if not nodes: return
        for node in nodes:
            if node is None:
                continue
            elif isinstance(node, (list,set)):
                checkNodes(node, formulaDependencies)
            elif isinstance(node, astQnameLiteral):
                if node.value in cdrFormulas: # qname is a formula
                    formulaDependencies.add(node.value)  # value is a QName literal
            elif isinstance(node, astNode):
                checkNodes([expr
                            for expr in node.__dict__.values() 
                            if isinstance(expr, (astNode, list, set))],
                           formulaDependencies)
    # compile and determine formula dependencies
    cntlr.modelManager.showStatus(_("analayzing CDR formula dependencies"))
    for formula in cdrFormulas.values():
        checkNodes(formula.prog, formula.formulaDependencies)
    orderedFormulaQnames = []
    dependencyResolvedFormulas = set()
    resolvedAFormula = True
    while (resolvedAFormula):
        resolvedAFormula = False
        for formulaQname, formula in cdrFormulas.items():
            if formulaQname not in dependencyResolvedFormulas and \
               len(formula.formulaDependencies - dependencyResolvedFormulas) == 0:
                dependencyResolvedFormulas.add(formulaQname)
                orderedFormulaQnames.append(formulaQname)
                resolvedAFormula = True
    # anything unresolved?
    for formulaQname, formula in cdrFormulas.items():
        if formulaQname not in dependencyResolvedFormulas:
            circularOrUndefDependencies = formula.formulaDependencies - dependencyResolvedFormulas
            undefinedVars = circularOrUndefDependencies - cdrFormulas 
            paramsCircularDep = circularOrUndefDependencies - undefinedVars
            if len(undefinedVars) > 0:
                val.modelXbrl.error("cdrFormula:unresolvedFormulaDependency",
                    _("Undefined dependencies in formula %(name)s, to names %(dependencies)s"),
                    modelObject=formula,
                    name=formulaQname, dependencies=", ".join((str(v) for v in undefinedVars)))
            if len(paramsCircularDep) > 0:
                val.modelXbrl.error("cdrFormula:formulaCyclicDependencies",
                    _("Cyclic dependencies in formula %(name)s, to names %(dependencies)s"),
                    modelObject=formula,
                    name=formulaQname, dependencies=", ".join((str(d) for d in paramsCircularDep)) )
                
    # evaluate formulas
    cntlr.modelManager.showStatus(_("evaluating CDR formulas"))
    if True: # initialErrorCount == val.modelXbrl.logCount.get(logging._checkLevel('ERROR'), 0):
        from .cdrContext import CdrContext
        from .cdrEvaluator import evaluateFormulas
        cdrContext = CdrContext(cdrFormulas, orderedFormulaQnames, modelXbrl)
        evaluateFormulas(cdrContext)
    cntlr.modelManager.showStatus("")
