'''
Created on Jun 10, 2011
Refactored on Jun 11, 2011 to ModelDtsObject, ModelInstanceObject, ModelTestcaseObject

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''

from arelle import arelle_c

class ModelObjectFactory(arelle_c.ModelObjectFactory):
    def __init__(self, *args):
        super(ModelObjectFactory, self).__init__(*args)        

modelObjectFactoryClassInstance = ModelObjectFactory()

def registerModelObjectClass(*args):
    modelObjectFactoryClassInstance.registerClass(*args)