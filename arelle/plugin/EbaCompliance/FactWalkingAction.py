'''
Created on 25 sept. 2014

@author: gmo
'''
from arelle.ModelInstanceObject import ModelFact

defaultENLanguage = "en"
filingIndicatorCodeRole = "http://www.eurofiling.info/xbrl/role/filing-indicator-code";

class FactWalkingAction:
    '''
    Action executed by the walker whenever a fact is met
    '''

    def __init__(self, modelXbrl):
        '''
        Constructor
        :type modelXbrl: ModelXbrl
        '''
        self.modelXbrl = modelXbrl
        self.allFilingIndicatorCodes = set();

    def onFactEvent(self, fact, value, modelTable):
        '''
        Action executed for every met fact.
        :type fact: ModelFact
        :type value: str
        :type modelTable: ModelTable
        '''
        if not fact.isNil:
            filingIndicatorCode = modelTable.genLabel(role=filingIndicatorCodeRole,
                                                      lang=defaultENLanguage)
            if not filingIndicatorCode in self.allFilingIndicatorCodes:
                self.allFilingIndicatorCodes.add(filingIndicatorCode)
                self.modelXbrl.modelManager.cntlr.addToLog("Filing indicator code %s has been added" % filingIndicatorCode)
    def afterAllFactsEvent(self):
        '''
        Action executed at the end, when all facts have been executed
        '''
        pass