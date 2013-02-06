'''
sphinxValidator validates Sphinx language expressions in the context of an XBRL DTS and instance.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).

Sphinx is a Rules Language for XBRL described by a Sphinx 2 Primer 
(c) Copyright 2012 CoreFiling, Oxford UK. 
Sphinx copyright applies to the Sphinx language, not to this software.
Mark V Systems conveys neither rights nor license for the Sphinx language. 
'''

from arelle.ModelValue import QName

def validate(logMessage, sphinxContext):
    modelXbrl = sphinxContext.modelXbrl
    hasDTS = modelXbrl is not None
    
    from .SphinxParser import (astSourceFile, astNamespaceDeclaration, astRuleBasePreconditions,
                               astNamespaceDeclaration, astStringLiteral, astFactPredicate,
                               astPreconditionDeclaration, astPreconditionReference,
                               astValidationRule, 
                               namedAxes
                               )
    
    if hasDTS:
        import logging
        initialErrorCount = modelXbrl.logCount.get(logging.getLevelName('ERROR'), 0)
        
    sphinxContext.ruleBasePreconditionsNodes = []
    sphinxContext.preconditionNodes = {}
    
    # accumulate definitions
    for prog in sphinxContext.sphinxProgs:
        for node in prog:
            if isinstance(node, astRuleBasePreconditions):
                sphinxContext.ruleBasePreconditionsNodes.append(node)
            elif isinstance(node, astPreconditionDeclaration):
                preconditionNodes[node.name] = node    

    # check references            
    def checkNodes(nodes):
        if not nodes: return
        for node in nodes:
            if node is None:
                continue
            elif isinstance(node, astRuleBasePreconditions):
                checkNodes(node.preconditionReferences)
            elif isinstance(node, astPreconditionReference):
                for name in node.names:
                    if name not in sphinxContext.preconditionNodes:
                        logMessage("ERROR", "sphinxCompiler:preconditionReferenceI",
                            _("Precondition reference is not defined %(name)s"),
                            sourceFileLine=node.sourceFileLine,
                            name=name)
            elif isinstance(node, astValidationRule):
                checkNodes((node.precondition, node.severity, node.expr, node.message))
            elif isinstance(node, astFactPredicate) and hasDTS:
                # check axes
                for axis, value in node.axes:
                    if (isinstance(axis, QName) and not (
                         axis in modelXbrl.qnnameConcepts and
                         modelXbrl.qnameConcepts[axis].isDimensionItem)):
                        logMessage("ERROR", "sphinxCompiler:axisNotDimension",
                            _("Axis is not a dimension in the DTS %(qname)s"),
                            sourceFileLine=node.sourceFileLine,
                            qname=axis)
                    if (axis not in {"unit", "segment", "scenario"} and
                        isinstance(value, QName) and 
                        not value in modelXbrl.qnnameConcepts): 
                        logMessage("ERROR", "sphinxCompiler:axisNotDimension",
                            _("Hypercube value not in the DTS %(qname)s"),
                            sourceFileLine=node.sourceFileLine,
                            qname=value)
    for prog in sphinxContext.sphinxProgs:
        checkNodes(prog)
                    
    if len(sphinxContext.ruleBasePreconditionsNodes) > 1:
        logMessage("ERROR", "sphinxCompiler:multipleRuleBaseDeclarations",
            _("Multiple rule-base declarations %(preconditions)s"),
            sourceFileLines=[node.sourceFileLine for node in sphinxContext.ruleBasePreconditionsNodes],
            preconditions=", ".join(str(r) for f, r in sphinxContext.ruleBasePreconditionsNodes)) 
        
               

    sphinxContext.ruleBasePreconditionNodes = [preconditionNodes[name]
                                               for node in sphinxContext.ruleBasePreconditionsNodes
                                               for ref in node.preconditionReferences
                                               for name in ref.names
                                               if name in sphinxContext.preconditionNodes]

    if hasDTS:
        # if no errors in checking sphinx
        if initialErrorCount == modelXbrl.logCount.get(logging.getLevelName('ERROR'), 0):
            from .SphinxEvaluator import evaluateRuleBase
            evaluateRuleBase(sphinxContext)
        
        
