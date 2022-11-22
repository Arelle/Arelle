'''
See COPYRIGHT.md for copyright information.
'''
import regex as re
from collections import defaultdict
import os, io, json
from datetime import datetime, timedelta
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.XmlValidate import VALID

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
rePARENTHETICAL = r"pa?r[ae]ne?th\w?[aei]+\w?t?h?i?c"
notPAR = "(?!.*" + rePARENTHETICAL + ")"
isPAR = "(?=.*" + rePARENTHETICAL + ")"

UGT_TOPICS = None

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

    if disclosureSystem.validationType in ("EFM", "HMRC"):
        detectMultipleOfCode = False
        if disclosureSystem.validationType == "EFM":
            tableCodes = list( EFMtableCodes ) # separate copy of list so entries can be deleted
            # for Registration and resubmission allow detecting multiple of code
            detectMultipleOfCode = any(v and any(v.startswith(dt) for dt in ('S-', 'F-', '8-K', '6-K'))
                                       for docTypeConcept in modelXbrl.nameConcepts.get('DocumentType', ())
                                       for docTypeFact in modelXbrl.factsByQname.get(docTypeConcept.qname, ())
                                       for v in (docTypeFact.value,))
        elif disclosureSystem.validationType == "HMRC":
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

def evaluateTableIndex(modelXbrl, lang=None):
    usgaapRoleDefinitionPattern = re.compile(r"([0-9]+) - (Statement|Disclosure|Schedule|Document) - (.+)")
    ifrsRoleDefinitionPattern = re.compile(r"\[([0-9]+)\] (.+)")
    # build EFM rendering-compatible index
    definitionElrs = dict((modelXbrl.roleTypeDefinition(roleURI, lang), roleType)
                          for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris
                          for roleType in modelXbrl.roleTypes.get(roleURI,()))
    sortedRoleTypes = sorted(definitionElrs.items(), key=lambda item: item[0])
    disclosureSystem = modelXbrl.modelManager.disclosureSystem
    _usgaapStyleELRs = _isJpFsa = _ifrsStyleELRs = False
    if disclosureSystem.validationType == "EFM":
        _usgaapStyleELRs = True
    elif "jp-fsa" in modelXbrl.modelManager.disclosureSystem.names:
        _isJpFsa = True
    else:
        # attempt to determine type
        if any(usgaapRoleDefinitionPattern.match(r[0]) for r in sortedRoleTypes if r[0]):
            _usgaapStyleELRs = True
        elif any(ifrsRoleDefinitionPattern.match(r[0]) for r in sortedRoleTypes if r[0]):
            _ifrsStyleELRs = True
    if _usgaapStyleELRs:
        COVER    = "1Cover"
        STMTS    = "2Financial Statements"
        NOTES    = "3Notes to Financial Statements"
        POLICIES = "4Accounting Policies"
        TABLES   = "5Notes Tables"
        DETAILS  = "6Notes Details"
        UNCATEG  = "7Uncategorized"
        isRR = any(ns.startswith("http://xbrl.sec.gov/rr/") for ns in modelXbrl.namespaceDocs.keys() if ns)
        tableGroup = None
        firstTableLinkroleURI = None
        firstDocumentLinkroleURI = None
        for roleDefinition, roleType in sortedRoleTypes:
            roleType._tableChildren = []
            match = usgaapRoleDefinitionPattern.match(roleDefinition) if roleDefinition else None
            if not match:
                roleType._tableIndex = (UNCATEG, "", roleType.roleURI)
                continue
            seq, tblType, tblName = match.groups()
            if isRR:
                tableGroup = COVER
            elif not tableGroup:
                tableGroup = ("Paren" in tblName and COVER or tblType == "Statement" and STMTS or
                              "(Polic" in tblName and NOTES or "(Table" in tblName and TABLES or
                              "(Detail" in tblName and DETAILS or COVER)
            elif tableGroup == COVER:
                tableGroup = (tblType == "Statement" and STMTS or
                              ("Paren" in tblName or tblType == "Document") and COVER or
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
                    if fact.context is not None and fact.context.endDatetime is not None:
                        reportingPeriods.add((None, fact.context.endDatetime)) # for instant
                        reportingPeriods.add((fact.context.startDatetime, fact.context.endDatetime)) # for startEnd
                        nextEnd = fact.context.startDatetime
                        duration = (fact.context.endDatetime - fact.context.startDatetime).days + 1
                        break
        if "DocumentType" in deiFact:
            fact = deiFact["DocumentType"]
            if fact.xValid >= VALID and "-Q" in (fact.xValue or ""): # fact may be invalid
                # need quarterly and yr to date durations
                endDatetime = fact.context.endDatetime
                # if within 2 days of end of month use last day of month
                endDatetimeMonth = endDatetime.month
                if (endDatetime + timedelta(2)).month != endDatetimeMonth:
                    # near end of month
                    endOfMonth = True
                    while endDatetime.month == endDatetimeMonth:
                        endDatetime += timedelta(1) # go forward to next month
                else:
                    endOfMonth = False
                startYr = endDatetime.year
                startMo = endDatetime.month - 3
                if startMo <= 0:
                    startMo += 12
                    startYr -= 1
                start_datetime_day = endDatetime.day
                # check if we are in Feb past the 28th
                if startMo == 2 and start_datetime_day > 28:
                    import calendar
                    if endOfMonth:
                        # reset day to the last day of Feb.
                        start_datetime_day = 29 if calendar.isleap(startYr) else 28
                    else:
                        # probably 52-53 weeks fiscal year, 2 cases only, current qtr ends on May 29th or 30th (31st then endOfMonth is True)
                        if start_datetime_day == 29:
                            if not calendar.isleap(startYr):
                                start_datetime_day = 1
                                # step into March
                                startMo +=1
                        elif start_datetime_day == 30:
                            start_datetime_day = 1 if calendar.isleap(startYr) else 2
                            # step into March
                            startMo +=1
                startDatetime = datetime(startYr, startMo, start_datetime_day, endDatetime.hour, endDatetime.minute, endDatetime.second)
                if endOfMonth:
                    startDatetime -= timedelta(1)
                    endDatetime -= timedelta(1)
                reportingPeriods.add((startDatetime, endDatetime))
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

        sortedRoleTypes.reverse() # now in descending order
        for i, roleTypes in enumerate(sortedRoleTypes):
            roleDefinition, roleType = roleTypes
            # find defined non-default axes in pre hierarchy for table
            tableFacts = set()
            tableGroup, tableSeq, tableName = roleType._tableIndex
            roleURIdims, priItemQNames = EFMlinkRoleURIstructure(modelXbrl, roleType.roleURI)
            for priItemQName in priItemQNames:
                for fact in factsByQname.get(priItemQName,()):
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

            # find parent if any
            closestParentType = None
            closestParentMatchLength = 0
            for _parentRoleDefinition, parentRoleType in sortedRoleTypes[i+1:]:
                matchLen = parentNameMatchLen(tableName, parentRoleType)
                if matchLen > closestParentMatchLength:
                    closestParentMatchLength = matchLen
                    closestParentType = parentRoleType
            if closestParentType is not None:
                closestParentType._tableChildren.insert(0, roleType)

            # remove lesser-matched children if there was a parent match
            unmatchedChildRoles = set()
            longestChildMatchLen = 0
            numChildren = 0
            for childRoleType in roleType._tableChildren:
                matchLen = parentNameMatchLen(tableName, childRoleType)
                if matchLen < closestParentMatchLength:
                    unmatchedChildRoles.add(childRoleType)
                elif matchLen > longestChildMatchLen:
                    longestChildMatchLen = matchLen
                    numChildren += 1
            if numChildren > 1:
                # remove children that don't have the full match pattern length to parent
                for childRoleType in roleType._tableChildren:
                    if (childRoleType not in unmatchedChildRoles and
                        parentNameMatchLen(tableName, childRoleType) < longestChildMatchLen):
                        unmatchedChildRoles.add(childRoleType)

            for unmatchedChildRole in unmatchedChildRoles:
                roleType._tableChildren.remove(unmatchedChildRole)

            for childRoleType in roleType._tableChildren:
                childRoleType._tableParent = roleType

            unmatchedChildRoles = None # dereference

        global UGT_TOPICS
        if UGT_TOPICS is None:
            try:
                from arelle import FileSource
                fh = FileSource.openFileStream(modelXbrl.modelManager.cntlr,
                                               os.path.join(modelXbrl.modelManager.cntlr.configDir, "ugt-topics.zip/ugt-topics.json"),
                                               'r', 'utf-8')
                UGT_TOPICS = json.load(fh)
                fh.close()
                for topic in UGT_TOPICS:
                    topic[6] = set(topic[6]) # change concept abstracts list into concept abstracts set
                    topic[7] = set(topic[7]) # change concept text blocks list into concept text blocks set
                    topic[8] = set(topic[8]) # change concept names list into concept names set
            except Exception as ex:
                    UGT_TOPICS = None

        if UGT_TOPICS is not None:
            def roleUgtConcepts(roleType):
                roleConcepts = set()
                for rel in modelXbrl.relationshipSet(XbrlConst.parentChild, roleType.roleURI).modelRelationships:
                    if isinstance(rel.toModelObject, ModelConcept):
                        roleConcepts.add(rel.toModelObject.name)
                    if isinstance(rel.fromModelObject, ModelConcept):
                        roleConcepts.add(rel.fromModelObject.name)
                if hasattr(roleType, "_tableChildren"):
                    for _tableChild in roleType._tableChildren:
                        roleConcepts |= roleUgtConcepts(_tableChild)
                return roleConcepts
            topicMatches = {} # topicNum: (best score, roleType)

            for roleDefinition, roleType in sortedRoleTypes:
                roleTopicType = 'S' if roleDefinition.startswith('S') else 'D'
                if getattr(roleType, "_tableParent", None) is None:
                    # rooted tables in reverse order
                    concepts = roleUgtConcepts(roleType)
                    for i, ugtTopic in enumerate(UGT_TOPICS):
                        if ugtTopic[0] == roleTopicType:
                            countAbstracts = len(concepts & ugtTopic[6])
                            countTextBlocks = len(concepts & ugtTopic[7])
                            countLineItems = len(concepts & ugtTopic[8])
                            if countAbstracts or countTextBlocks or countLineItems:
                                _score = (10 * countAbstracts +
                                          1000 * countTextBlocks +
                                          countLineItems / len(concepts))
                                if i not in topicMatches or _score > topicMatches[i][0]:
                                    topicMatches[i] = (_score, roleType)
            for topicNum, scoredRoleType in topicMatches.items():
                _score, roleType = scoredRoleType
                if _score > getattr(roleType, "_tableTopicScore", 0):
                    ugtTopic = UGT_TOPICS[topicNum]
                    roleType._tableTopicScore = _score
                    roleType._tableTopicType = ugtTopic[0]
                    roleType._tableTopicName = ugtTopic[3]
                    roleType._tableTopicCode = ugtTopic[4]
                    # print ("Match score {:.2f} topic {} preGrp {}".format(_score, ugtTopic[3], roleType.definition))
        return (firstTableLinkroleURI or firstDocumentLinkroleURI), None # no restriction on contents linkroles
    elif _isJpFsa:
        # find ELR with only iod:identifierItem subs group concepts
        roleElrs = dict((roleURI, roleType)
                        for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris
                        for roleType in modelXbrl.roleTypes.get(roleURI,()))
        roleIdentifierItems = {}
        for roleURI, roleType in roleElrs.items():
            roleType._tableChildren = []
            relSet = modelXbrl.relationshipSet(XbrlConst.parentChild, roleURI)
            for rootConcept in relSet.rootConcepts:
                if rootConcept.substitutionGroupQname and rootConcept.substitutionGroupQname.localName == "identifierItem":
                    roleIdentifierItems[rootConcept] = roleType
        linkroleUri = None
        for roleURI, roleType in roleElrs.items():
            relSet = modelXbrl.relationshipSet(XbrlConst.parentChild, roleURI)
            def addRoleIdentifiers(fromConcept, parentRoleType, visited):
                for rel in relSet.fromModelObject(fromConcept):
                    _fromConcept = rel.fromModelObject
                    _toConcept = rel.toModelObject
                    if isinstance(_fromConcept, ModelConcept) and isinstance(_toConcept, ModelConcept):
                        _fromSubQn = _fromConcept.substitutionGroupQname
                        _toSubQn = _toConcept.substitutionGroupQname
                        if ((parentRoleType is not None or
                             (_fromSubQn and _fromSubQn.localName == "identifierItem" and _fromConcept in roleIdentifierItems )) and
                            _toSubQn and _toSubQn.localName == "identifierItem" and
                            _toConcept in roleIdentifierItems):
                            if parentRoleType is None:
                                parentRoleType = roleIdentifierItems[_fromConcept]
                            _toRoleType = roleIdentifierItems[_toConcept]
                            if _toConcept not in parentRoleType._tableChildren:
                                parentRoleType._tableChildren.append(_toRoleType)
                            if _toConcept not in visited:
                                visited.add(_toConcept)
                                addRoleIdentifiers(_toConcept, _toRoleType, visited)
                                visited.discard(_toConcept)
                        elif _toConcept not in visited:
                            visited.add(_toConcept)
                            addRoleIdentifiers(_toConcept, parentRoleType, visited)
                            visited.discard(_toConcept)
            for rootConcept in relSet.rootConcepts:
                addRoleIdentifiers(rootConcept, None, set())
                if not linkroleUri and len(roleType._tableChildren) > 0:
                    linkroleUri = roleURI
        return linkroleUri, linkroleUri  # only show linkroleUri in index table
    elif _ifrsStyleELRs:
        for roleType in definitionElrs.values():
            roleType._tableChildren = []
        return sortedRoleTypes[0][1].roleURI, None # first link role in order
    return None, None

def parentNameMatchLen(tableName, parentRoleType):
    lengthOfMatch = 0
    parentName = parentRoleType._tableIndex[2]
    parentNameLen = len(parentName.partition('(')[0])
    fullWordFound = False
    for c in tableName.partition('(')[0]:
        fullWordFound |= c.isspace()
        if lengthOfMatch >= parentNameLen or c != parentName[lengthOfMatch]:
            break
        lengthOfMatch += 1
    return fullWordFound and lengthOfMatch

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
