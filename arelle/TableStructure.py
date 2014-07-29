'''
Created on Feb 02, 2014

@author: Mark V Systems Limited
(c) Copyright 2014 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re
from collections import defaultdict
from datetime import datetime, timedelta
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept

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
    ("BSV", RE(STMT, notDET,notPAR, r".*net\W+asset\W+value"), None), 
    ("CFS", RE(STMT, notDET,notPAR, r".*cash\W*flows\W+supplemental"), None),
    ("LAP", RE(STMT, notDET, isPAR, r".*(?!.*changes)(?=.*assets).*liquidati"), None)
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

def evaluateTableIndex(modelXbrl):
    disclosureSystem = modelXbrl.modelManager.disclosureSystem
    if disclosureSystem.EFM:
        COVER    = "1Cover"
        STMTS    = "2Financial Statements"
        NOTES    = "3Notes to Financial Statements"
        POLICIES = "4Accounting Policies"
        TABLES   = "5Notes Tables"
        DETAILS  = "6Notes Details"
        UNCATEG  = "7Uncategorized"
        roleDefinitionPattern = re.compile(r"([0-9]+) - (Statement|Disclosure|Schedule|Document) - (.+)")
        # build EFM rendering-compatible index
        definitionElrs = dict((roleType.definition, roleType)
                              for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris
                              for roleType in modelXbrl.roleTypes.get(roleURI,()))
        isRR = any(ns.startswith("http://xbrl.sec.gov/rr/") for ns in modelXbrl.namespaceDocs.keys())
        tableGroup = None
        firstTableLinkroleURI = None
        firstDocumentLinkroleURI = None
        sortedRoleTypes = sorted(definitionElrs.items(), key=lambda item: item[0])
        for roleDefinition, roleType in sortedRoleTypes:
            match = roleDefinitionPattern.match(roleDefinition)
            if not match: 
                roleType._tableIndex = (UNCATEG, roleType.roleURI)
                continue
            seq, tblType, tblName = match.groups()
            if isRR:
                tableGroup = COVER
            elif not tableGroup:
                tableGroup = ("Paren" in tblName and COVER or tblType == "Statement" and STMTS or
                              "(Polic" in tblName and NOTES or "(Table" in tblName and TABLES or
                              "(Detail" in tblName and DETAILS or COVER)
            elif tableGroup == COVER:
                tableGroup = (tblType == "Statement" and STMTS or "Paren" in tblName and COVER or
                              "(Polic" in tblName and NOTES or "(Table" in tblName and TABLES or
                              "(Detail" in tblName and DETAILS or NOTES)
            elif tableGroup == STMTS:
                tableGroup = ((tblType == "Statement" or "Paren" in tblName) and STMTS or
                              "(Polic" in tblName and NOTES or "(Table" in tblName and TABLES or
                              "(Detail" in tblName and DETAILS or NOTES)
            elif tableGroup == NOTES:
                tableGroup = ("(Polic" in tblName and POLICIES or "(Table" in tblName and TABLES or 
                              "(Detail" in tblName and DETAILS or tblType == "Disclosure" and NOTES or UNCATEG)
            elif tableGroup == POLICIES:
                tableGroup = ("(Table" in tblName and TABLES or "(Detail" in tblName and DETAILS or 
                              ("Paren" in tblName or "(Polic" in tblName) and POLICIES or UNCATEG)
            elif tableGroup == TABLES:
                tableGroup = ("(Detail" in tblName and DETAILS or 
                              ("Paren" in tblName or "(Table" in tblName) and TABLES or UNCATEG)
            elif tableGroup == DETAILS:
                tableGroup = (("Paren" in tblName or "(Detail" in tblName) and DETAILS or UNCATEG)
            else:
                tableGroup = UNCATEG
            if firstTableLinkroleURI is None and tableGroup == COVER:
                firstTableLinkroleURI = roleType.roleURI
            if tblType == "Document" and not firstDocumentLinkroleURI:
                firstDocumentLinkroleURI = roleType.roleURI
            roleType._tableIndex = (tableGroup, seq, tblName)

        # flow allocate facts to roles (SEC presentation groups)
        if not modelXbrl.qnameDimensionDefaults: # may not have run validatino yet
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
        reportedFacts = set() # facts which were shown in a higher-numbered ELR table
        factsByQname = modelXbrl.factsByQname
        reportingPeriods = set()
        nextEnd = None
        deiFact = {}
        for conceptName in ("DocumentPeriodEndDate", "DocumentType", "CurrentFiscalPeriodEndDate"):
            for concept in modelXbrl.nameConcepts[conceptName]:
                for fact in factsByQname[concept.qname]:
                    deiFact[conceptName] = fact
                    if fact.context is not None:
                        reportingPeriods.add((None, fact.context.endDatetime)) # for instant
                        reportingPeriods.add((fact.context.startDatetime, fact.context.endDatetime)) # for startEnd
                        nextEnd = fact.context.startDatetime
                        duration = (fact.context.endDatetime - fact.context.startDatetime).days + 1
                        break
        if "DocumentType" in deiFact:
            fact = deiFact["DocumentType"]
            if "-Q" in fact.xValue:
                # need quarterly and yr to date durations
                endDatetime = fact.context.endDatetime
                startYr = endDatetime.year
                startMo = endDatetime.month - 3
                if startMo < 0:
                    startMo += 12
                    startYr -= 1
                reportingPeriods.add((datetime(startYr, startMo, endDatetime.day, endDatetime.hour, endDatetime.minute, endDatetime.second),
                                      endDatetime))
                duration = 91
        # find preceding compatible default context periods
        while (nextEnd is not None):
            thisEnd = nextEnd
            prevMaxStart = thisEnd - timedelta(duration * .9)
            prevMinStart = thisEnd - timedelta(duration * 1.1)
            nextEnd = None
            for cntx in modelXbrl.contexts.values():
                if (cntx.isStartEndPeriod and not cntx.qnameDims and thisEnd == cntx.endDatetime and
                    prevMinStart <= cntx.startDatetime <= prevMaxStart):
                    reportingPeriods.add((None, cntx.endDatetime))
                    reportingPeriods.add((cntx.startDatetime, cntx.endDatetime))
                    nextEnd = cntx.startDatetime
                    break
                elif (cntx.isInstantPeriod and not cntx.qnameDims and thisEnd == cntx.endDatetime):
                    reportingPeriods.add((None, cntx.endDatetime))
        stmtReportingPeriods = set(reportingPeriods)       

        for roleDefinition, roleType in reversed(sortedRoleTypes):
            if roleType.definition.startswith('0025'):
                pass
            # find defined non-default axes in pre hierarchy for table
            tableFacts = set()
            tableGroup = roleType._tableIndex[0]
            roleURIdims, priItemQNames = EFMlinkRoleURIstructure(modelXbrl, roleType.roleURI)
            for priItemQName in priItemQNames:
                for fact in factsByQname[priItemQName]:
                    cntx = fact.context
                    # non-explicit dims must be default
                    if (cntx is not None and
                        all(dimQn in modelXbrl.qnameDimensionDefaults
                            for dimQn in (roleURIdims.keys() - cntx.qnameDims.keys())) and
                        all(mdlDim.memberQname in roleURIdims[dimQn]
                            for dimQn, mdlDim in cntx.qnameDims.items()
                            if dimQn in roleURIdims)):
                        # the flow-up part, drop
                        cntxStartDatetime = cntx.startDatetime
                        cntxEndDatetime = cntx.endDatetime
                        if (tableGroup != STMTS or
                            (cntxStartDatetime, cntxEndDatetime) in stmtReportingPeriods and
                             (fact not in reportedFacts or
                              all(dimQn not in cntx.qnameDims # unspecified dims are all defaulted if reported elsewhere
                                  for dimQn in (cntx.qnameDims.keys() - roleURIdims.keys())))):
                            tableFacts.add(fact)
                            reportedFacts.add(fact)
            roleType._tableFacts = tableFacts
            
        return firstTableLinkroleURI or firstDocumentLinkroleURI # did build _tableIndex attributes
    return None

def EFMlinkRoleURIstructure(modelXbrl, roleURI):
    relSet = modelXbrl.relationshipSet(XbrlConst.parentChild, roleURI)
    dimMems = {} # by dimension qname, set of member qnames
    priItems = set()
    for rootConcept in relSet.rootConcepts:
        EFMlinkRoleDescendants(relSet, rootConcept, dimMems, priItems)
    return dimMems, priItems
        
def EFMlinkRoleDescendants(relSet, concept, dimMems, priItems):
    if concept is not None:
        if concept.isDimensionItem:
            dimMems[concept.qname] = EFMdimMems(relSet, concept, set())
        else:
            if not concept.isAbstract:
                priItems.add(concept.qname)
            for rel in relSet.fromModelObject(concept):
                EFMlinkRoleDescendants(relSet, rel.toModelObject, dimMems, priItems)

def EFMdimMems(relSet, concept, memQNames):
    for rel in relSet.fromModelObject(concept):
        dimConcept = rel.toModelObject
        if isinstance(dimConcept, ModelConcept) and dimConcept.isDomainMember:
            memQNames.add(dimConcept.qname)
            EFMdimMems(relSet, dimConcept, memQNames)
    return memQNames

