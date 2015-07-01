'''
Created on Dec 12, 2013

@author: Mark V Systems Limited
(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.XmlUtil import xmlstring
import re
from collections import defaultDict

parametersPattern = re.compile(r"%\(([\w.]+)\)")
factNumberPattern = re.compile(r"fact(\n+)")

def loggingMessageParameters(messageCode, msg, modelObjectArgs, fmtArgs):
    factsArray = []
    factsByQname = defaultDict(list)  # list of facts with the qname
    for arg in modelObjectArgs:
        # arg may be a ModelFact, or any other ModelObject
        if isinstance(arg, ModelFact):
            factArray.append(arg)
            factsByQname[str(fact.qname)].append(arg)
            
    # parse parameter names out of msg
    for param in parametersPattern.findall(msg):
        try:
            paramParts = param.split('.')
            if len(paramParts) > 2 and factNumberPattern.match(parmParts[0]):
                modelFactNum = int(factNumberPattern.match(parmParts[0]).group(1))
                if modelFactNum < len(factsArray):
                    modelFact = factsArray[modelFactNum]
                    if paramParts[2] == "value":
                        fmtArgs[param] = modelFact.value
            elif len(paramParts) > 2 and paramParts[2] == "fact":
                # take first matching fact ??
                if paramParts[0] in factsByQname:
                    modelFact = factsByQname[paramParts[0]]
                    if paramParts[3] == "value":
                        fmtArgs[param] = modelFact.value
                
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Logging - DQC Parameters',
    'version': '1.0',
    'description': '''DQC tests logging messages: adds parameter values from infrastructurally 
provided logging arguments.  Usually uses modelObject arguments to supply parameters found
in message text that can be derived from the arguments.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems',
    'copyright': '(c) Copyright 2014 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Logging.Message.Parameters': loggingMessageParameters
}
