'''
Created on Feb 02, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import XbrlConst

# NOTE: This is an early experimental implementation of statement detection
# it is not in a finished status at this time.
EFMtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    
    # statement detection including root element of presentation link role
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical).*", re.IGNORECASE), 
     ("StatementOfFinancialPositionAbstract",)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical).*", re.IGNORECASE), 
     ("IncomeStatementAbstract","StatementOfIncomeAndComprehensiveIncomeAbstract")),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical).*", re.IGNORECASE), 
     ("StatementOfStockholdersEquityAbstract","StatementOfPartnersCapitalAbstract")),
    ("CF", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical).*", re.IGNORECASE), 
     ("StatementOfCashFlowsAbstract",)),
                 
    # statement detection without considering root elements
    ("DEI", re.compile(r".* - document - .*document\W+.*entity\W+.*information.*", re.IGNORECASE), None),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*balance\W+sheet.*", re.IGNORECASE), None),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*balance\W+sheet.*", re.IGNORECASE), None),
    ("CF", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE), None),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*comprehensive(.*\Wincome|.*\Wloss)", re.IGNORECASE), None),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(equity|capital|deficit).*", re.IGNORECASE), None),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE), None),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE), None),
    ("CFP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE), None),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*loss", re.IGNORECASE), None),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*loss", re.IGNORECASE), None),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".(position|condition)", re.IGNORECASE), None),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*(position|condition)", re.IGNORECASE), None),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*equity\W(\w+\W+)*comprehensive.*", re.IGNORECASE), None),
    ]
HMRCtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    ("DEI", re.compile(r".*entity\W+.*information.*", re.IGNORECASE), None),
    ("BS", re.compile(r".*balance\W+sheet.*", re.IGNORECASE), None),
    ("IS", re.compile(r".*loss", re.IGNORECASE), None),
    ("CF", re.compile(r".*cash\W*flow.*", re.IGNORECASE), None),
    ("SE", re.compile(r".*(shareholder|equity).*", re.IGNORECASE), None),
    ]

def evaluateRoleTypesTableCodes(modelXbrl):
    disclosureSystem = modelXbrl.modelManager.disclosureSystem
    
    if disclosureSystem.EFM or disclosureSystem.HMRC:
        if disclosureSystem.EFM:
            tableCodes = list( EFMtableCodes ) # separate copy of list so entries can be deleted
        elif disclosureSystem.HMRC:
            tableCodes = list( HMRCtableCodes ) # separate copy of list so entries can be deleted
 
        codeRoleURIs = {}  # lookup by code for roleURI
        
        # resolve structural model
        roleTypes = [roleType
                     for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris
                     for roleType in modelXbrl.roleTypes.get(roleURI,())]
        roleTypes.sort(key=lambda roleType: roleType.definition)
        # assign code to table link roles (Presentation ELRs)
        for roleType in roleTypes:
            definition = roleType.definition
            rootConcepts = None
            for i, tableCode in enumerate(tableCodes):
                code, pattern, rootConceptNames = tableCode
                if code not in codeRoleURIs and pattern.match(definition):
                    if rootConceptNames and rootConcepts is None:
                        rootConcepts = modelXbrl.relationshipSet(XbrlConst.parentChild, roleType.roleURI).rootConcepts
                    if (not rootConceptNames or
                        any(rootConcept.name in rootConceptNames for rootConcept in rootConcepts)):
                        codeRoleURIs[roleType.roleURI] = code
                        del tableCodes[i] # done with looking at this code
                        break
        # find defined non-default axes in pre hierarchy for table
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = codeRoleURIs.get(roleType.roleURI)
    else:
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = None
