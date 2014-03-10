'''
Created on Feb 02, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import XbrlConst

# regular expression components
STMT = r".* - statement - "
notDET = r"(?!.*details)"
notCMPRH = r"(?!.*comprehensive)"
isCMPRH = r"(?=.*comprehensive)"
''' common mis-spellings of parenthetical to match successfully (from 2013 SEC filings)
    paranthetical
    parenthical
    parentheical
    parenthtical
    parenthethical
    parenthentical
    prenthetical
    parenethetical
    
use a regular expression that is forgiving on at least the above
and doens't match variations of parent, transparent, etc.
'''
rePARENTHETICAL = r"pa?r[ae]ne?tht?[aei]+n?t?h?i?c"
notPAR = "(?!.*" + rePARENTHETICAL + ")"
isPAR = "(?=.*" + rePARENTHETICAL + ")"

def RE(*args):
    return re.compile(''.join(args), re.IGNORECASE)

# NOTE: This is an early experimental implementation of statement detection
# it is not in a finished status at this time.
EFMtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    
    # statement detection including root element of presentation link role
    ("BS", RE(STMT, notDET, notPAR), ("StatementOfFinancialPositionAbstract",)),
    ("BSP", RE(STMT, notDET, isPAR), ("StatementOfFinancialPositionAbstract",)),
    ("IS", RE(STMT, notDET, notPAR), ("IncomeStatementAbstract",)),
    ("ISP", RE(STMT, notDET, isPAR), ("IncomeStatementAbstract",)),
    ("CI", RE(STMT, notDET, notPAR), ("StatementOfIncomeAndComprehensiveIncomeAbstract",)),
    ("CIP", RE(STMT, notDET, isPAR), ("StatementOfIncomeAndComprehensiveIncomeAbstract",)),
    ("EQ", RE(STMT, notDET, notPAR), ("StatementOfStockholdersEquityAbstract","StatementOfPartnersCapitalAbstract")),
    ("EQP", RE(STMT, notDET, isPAR), ("StatementOfStockholdersEquityAbstract","StatementOfPartnersCapitalAbstract")),
    ("CF", RE(STMT, notDET, notPAR), ("StatementOfCashFlowsAbstract",)),
    ("CFP", RE(STMT, notDET, isPAR), ("StatementOfCashFlowsAbstract",)),
    ("CA", RE(STMT, notDET, notPAR), ("CapitalizationLongtermDebtAndEquityAbstract",)),
    ("CAP", RE(STMT, notDET, isPAR), ("CapitalizationLongtermDebtAndEquityAbstract",)),
    ("IN", RE(STMT, notDET, notPAR), ("ScheduleOfInvestmentsAbstract",)),
    ("INP", RE(STMT, notDET, isPAR), ("ScheduleOfInvestmentsAbstract",)),
                 
    # statement detection without considering root elements
    ("DEI", RE(r".* - (document|statement) - .*document\W+.*entity\W+.*information"), None),
    ("BS", RE(STMT, notDET, notPAR, r".*balance\W+sheet"), None),
    ("BSP", RE(STMT, notDET, isPAR, r".*balance\W+sheet"), None),
    ("CF", RE(STMT, notDET, notPAR, r".*cash\W*flow"), None),
    ("IS", RE(STMT, notDET, notPAR, notCMPRH, r".*(income|loss)"), None),
    ("ISP", RE(STMT, notDET, isPAR, notCMPRH, r".*(income|loss)"), None),
    ("CI", RE(STMT, notDET, notPAR, isCMPRH, r".*(income|loss|earnings)"), None),
    ("CIP", RE(STMT, notDET, isPAR, isCMPRH, r".*(income|loss|earnings)"), None),
    ("CA", RE(STMT, notDET, notPAR, r".*capitali[sz]ation"), None),
    ("CAP", RE(STMT, notDET, isPAR, r".*capitali[sz]ation"), None),
    ("EQ", RE(STMT, notDET, notPAR, r".*(equity|capital)"), None),
    ("EQP", RE(STMT, notDET, isPAR, r".*(equity|capital)"), None),
    ("IS", RE(STMT, notDET, notPAR, r".*(income|operations|earning)"), None),
    ("EQ", RE(STMT, notDET, notPAR, r".*def[ei][cs]it"), None),
    ("ISP", RE(STMT, notDET, isPAR, r".*(income|operations|earning)"), None),
    ("CFP", RE(STMT, notDET, isPAR, r".*cash\W*flow.*"), None),
    ("IS", RE(STMT, notDET, notPAR, r".*loss"), None),
    ("ISP", RE(STMT, notDET, isPAR, r".*loss"), None),
    ("BS", RE(STMT, notDET, notPAR, r".*(position|condition)"), None),
    ("BSP", RE(STMT, notDET, isPAR, r".*(position|condition)"), None),
    ("SE", RE(STMT, notDET, notPAR, r"(?=.*equity).*comprehensive"), None),
    ("EQ", RE(STMT, notDET, notPAR, r".*shareholder[']?s[']?\W+investment"), None),
    ("EQP", RE(STMT, notDET, isPAR, r".*shareholder[']?s[']?\W+investment"), None),
    ("EQ", RE(STMT, notDET, notPAR, r".*retained\W+earning"), None),
    ("IN", RE(STMT, notDET, notPAR, r".*investment"), None),
    ("INP", RE(STMT, notDET, isPAR, r".*investment"), None),
    ("LA", RE(STMT, notDET, notPAR, r"(?!.*changes)(?=.*assets).*liquidati"), None),
    ("LC", RE(STMT, notDET, notPAR, r"(?=.*changes)(?=.*assets).*liquidati"), None),
    ("IS", RE(STMT, notDET, notPAR, r"(?=.*disc).*operation"), None),
    ("BS", RE(STMT, notDET, notPAR, r"(?!.*changes).*assets"), None),
    ("BSP", RE(STMT, notDET, isPAR, r"(?!.*changes).*assets"), None),
    ("EQ", RE(STMT, notDET, notPAR, r"(?=.*changes).*assets"), None),
    ("EQP", RE(STMT, notDET, isPAR, r"(?=.*changes).*assets"), None),
    ("FH", RE(STMT, notDET, notPAR, r"(?=.*financial).*highlight"), None),
    ("FHP", RE(STMT, notDET, isPAR, r"(?=.*financial).*highlight"), None),
    ("EQ", RE(STMT, notDET, notPAR, r"(?=.*reserve).*trust"), None),
    ("EQP", RE(STMT, notDET, isPAR, r"(?=.*reserve).*trust"), None),
    ("LC", RE(STMT, notDET, notPAR, r"(?=.*activities).*liquidati"), None),
    ("EQP", RE(STMT, notDET, isPAR, r".*def[ei][cs]it"), None),
    ]
HMRCtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    ("DEI", RE(r".*entity\W+.*information.*"), None),
    ("BS", RE(r".*balance\W+sheet.*"), None),
    ("IS", RE(r".*loss"), None),
    ("CF", RE(r".*cash\W*flow.*"), None),
    ("SE", RE(r".*(shareholder|equity).*"), None),
    ]

def evaluateRoleTypesTableCodes(modelXbrl):
    disclosureSystem = modelXbrl.modelManager.disclosureSystem
    
    if disclosureSystem.EFM or disclosureSystem.HMRC:
        detectMultipleOfCode = False
        if disclosureSystem.EFM:
            tableCodes = list( EFMtableCodes ) # separate copy of list so entries can be deleted
            # for Registration and resubmission allow detecting multiple of code
            detectMultipleOfCode = any(v and any(v.startswith(dt) for dt in ('S-', 'F-', '8-K', '6-K'))
                                       for docTypeConcept in modelXbrl.nameConcepts.get('DocumentType', ())
                                       for docTypeFact in modelXbrl.factsByQname.get(docTypeConcept.qname, ())
                                       for v in (docTypeFact.value,))
        elif disclosureSystem.HMRC:
            tableCodes = list( HMRCtableCodes ) # separate copy of list so entries can be deleted
 
        codeRoleURI = {}  # lookup by code for roleURI
        roleURICode = {}  # lookup by roleURI
        
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
                if (detectMultipleOfCode or code not in codeRoleURI) and pattern.match(definition):
                    if rootConceptNames and rootConcepts is None:
                        rootConcepts = modelXbrl.relationshipSet(XbrlConst.parentChild, roleType.roleURI).rootConcepts
                    if (not rootConceptNames or
                        any(rootConcept.name in rootConceptNames for rootConcept in rootConcepts)):
                        codeRoleURI[code] = roleType.roleURI
                        roleURICode[roleType.roleURI] = code
                        if not detectMultipleOfCode:
                            del tableCodes[i] # done with looking at this code
                        break
        # find defined non-default axes in pre hierarchy for table
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = roleURICode.get(roleType.roleURI)
    else:
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = None
