# -*- coding: utf-8 -*-
'''
Created by staff of the U.S. Securities and Exchange Commission.
Data and content created by government employees within the scope of their employment are not subject
to domestic copyright protection. 17 U.S.C. 105.

Provides an integer code for each message
'''
from regex import compile as re_compile
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl

ftStart   = 10000000 # fee tagging messages
efmStart  = 20000000 # EFM check messages
ixStart   = 30000000 # inline XBRL messages
xbrlStart = 40000000 # XBRL 2.1 messates
xml1Start = 51000000 # XML value
xml2Start = 52000000 # XML element issue in traditional XML (Python check)
xml3Start = 52000000 # XML element issue in inline XML (LXML schema check)
unknown   = 60000000 # no pattern match

ignoredCodes = {
    "debug", "info", "info:profileStats", None}
codesPatterns = (
    (efmStart,  re_compile(r"EFM\.([0-9]+(.[0-9]+)*).*"), "."),
    (ixStart,   re_compile(r"ix11\.([0-9]+(.[0-9]+)*).*"), "."),
    (efmStart,  re_compile(r"xbrl\.([0-9]+(.[0-9]+)*).*"), "."),
    (xbrlStart, re_compile(r"EFM\.([0-9]+(.[0-9]+)*).*"), "."),
    (xml1Start, re_compile(r"xmlSchema.valueError"), "."),
    (xml2Start, re_compile(r"xmlSchema"), "."),
    (xml3Start, re_compile(r"lxml.SCHEMA[A-Za-z_]*([0-9]+(_[0-9]+)*).*"), "_"),
    )
deiSubTblCodes = {"DocumentType": 26050020, "EntityRegistrantName": 26050021, "EntityCentralIndexKey": 26050021}
ftSubTbl = ["RegnFileNb", "FormTp", "SubmissnTp", "FeeExhibitTp", "IssrNm", "IssrBizAdrStrt1", "IssrBizAdrStrt2", "IssrBizAdrCity", "IssrBizAdrStatOrCtryCd", "IssrBizAdrZipCd", "CeasedOprsDt", "RptgFsclYrEndDt"]
ftSumTbl = ["TtlOfferingAmt", "TtlPrevslyPdAmt", "TtlFeeAmt", "TtlTxValtn", "FeeIntrstAmt", "TtlOffsetAmt", "NrrtvDsclsr", "NetFeeAmt", "NrrtvMaxAggtOfferingPric", "NrrtvMaxAggtAmt", "FnlPrspctsFlg", "TtlFeeAndIntrstAmt"]
ftOfferingTbl = ["PrevslyPdFlg", "OfferingSctyTp", "OfferingSctyTitl", "AmtSctiesRegd", "MaxOfferingPricPerScty", "MaxAggtOfferingPric", "TxValtn", "FeeRate", "FeeAmt", "CfwdPrrFileNb", "CfwdFormTp", "CfwdPrrFctvDt", "CfwdPrevslyPdFee", "GnlInstrIIhiFlg", "AmtSctiesRcvd", "ValSctiesRcvdPerShr", "ValSctiesRcvd", "CshPdByRegistrantInTx", "CshRcvdByRegistrantInTx", "FeeNoteMaxAggtOfferingPric", "OfferingNote"]
ftOffsetTbl = ["OffsetClmdInd", "OffsetPrrFilerNm", "OffsetPrrFormTp", "OffsetPrrFileNb", "OffsetClmInitlFilgDt", "OffsetSrcFilgDt", "OffsetClmdAmt", "OffsetPrrSctyTp", "OffsetPrrSctyTitl", "OffsetPrrNbOfUnsoldScties", "OffsetPrrUnsoldOfferingAmt", "OffsetPrrFeeAmt", "OffsetExpltnForClmdAmt", "OffsetNote", "TermntnCmpltnWdrwl"]
ftCmbPrsTbl = ["Rule429EarlierFileNb", "Rule429EarlierFormTp", "Rule429InitlFctvDt", "Rule429SctyTp", "Rule429SctyTitl", "Rule429NbOfUnsoldScties", "Rule429AggtOfferingAmt", "Rule429PrspctsNote"]
ft424iTbl = ["PrevslyPdFlg", "OfferingSctyTitl", "AggtSalesPricFsclYr", "AggtRedRpPricFsclYr", "AggtRedRpPricPrrFsclYr", "AmtRedCdts", "NetSalesAmt", "FeeRate", "FeeAmt", "FeeNote"]
ftTableStartCode = (
    (1000000, "Submission / Fees Summary", None),
    (3000000, "Offering", ftOfferingTbl),
    (4000000, "Offset", ftOffsetTbl),
    (5000000, "Combined Prospectus", ftCmbPrsTbl),
    (6000000, "Securities, 424I", ft424iTbl),
    (0, "", None)) # catch all
ftRuleCode = (
    (90000, "Rule 457(f)"), # should be first since it is combined with another rule.
    (10000, "Rule 457(a)"),
    (20000, "Rule 457(o)"),
    (30000, "Rule 457(r)"),
    (40000, "Rule 457(s)"),
    (50000, "Rule 457(u)"),
    (60000, "Other Rule"),
    (70000, "Rule 415(a)(6)"),
    # 0-11 below under 0-11(a(2)
    (10000, "Rule 457(b)"),
    (20000, "Rule 0-11(a)(2)"),
    (80000, "Rule 0-11"), # check after preceding longer string check
    (30000, "Rule 457(p)"),
    (10000, "Rule 429"),
    (10000, "Securities, 424I"),
    (0, "")) # catch all

def messageNumericId(modelXbrl, level, messageCode, args):
    if messageCode in ignoredCodes:
        return messageCode, None
    modelObject = args.get("modelObject")
    if isinstance(modelObject, (tuple, list)) and len(modelObject) > 0:
        modelObject = modelObject[0]
    ftContext = args.get("ftContext")
    if isinstance(modelObject, (ModelFact,ModelXbrl)) and ftContext and messageCode.startswith("EFM.ft."):
        if isinstance(modelObject, (ModelFact, ModelXbrl)):
            tagName = None
            if "{tag}" in args.get("edgarCode"):
                tagName = args.get("tag")
            elif "{otherTag}" in args.get("edgarCode"):
                tagName = args.get("otherTag")
            elif args.get("msgCoda"):
                if "{tag}" in args.get("msgCoda"):
                    tagName = args.get("tag")
                elif "{otherTag}" in args.get("msgCoda"):
                    tagName = args.get("otherTag")
                else:
                    tagName = args.get("tag")
            conceptLn = tagName.split(":")[-1] if tagName else None
        else:
            conceptLn = None
        subType = args.get("subType", "")
        msgNumId = ftStart
        for i, (code, tblName, tblConcepts) in enumerate(ftTableStartCode):
            if ftContext.startswith(tblName):
                if i == 0:
                    if conceptLn in deiSubTblCodes:
                        msgNumId = deiSubTblCodes[conceptLn]
                    elif conceptLn in ftSubTbl:
                        msgNumId += code
                        msgNumId += ftSubTbl.index(conceptLn) + 1
                        if subType.startswith("424I"):
                            msgNumId += 20000
                        else:
                            msgNumId += 10000
                    elif conceptLn in ftSumTbl:
                        conceptLnNumeric = ftSumTbl.index(conceptLn) + 1
                        msgNumId += code + 1000000
                        msgNumId += conceptLnNumeric
                        if subType.startswith("424I"):
                            msgNumId += 10000
                        elif subType.startswith("SC"):
                            msgNumId += 20000
                        elif conceptLnNumeric < 8:
                            msgNumId += 30000
                        elif subType.startswith("POS"):
                            msgNumId += 40000
                        elif subType.startswith("424B"):
                            msgNumId += 50000
                else:
                    msgNumId += code
                    if tblConcepts and conceptLn in tblConcepts:
                        msgNumId += tblConcepts.index(conceptLn) + 1
                    # add in rule column only when it's not a rule issue.
                    for ruleCode, ruleName in ftRuleCode:
                        if ruleName in ftContext:
                            if not conceptLn and not (args.get("tags", "").endswith("Flg") and "Rule" in args.get("tags", "")):
                                msgNumId += ruleCode
                            elif conceptLn and not (conceptLn.endswith("Flg") and "Rule" in conceptLn):
                                msgNumId += ruleCode
                            break
                break
        if msgNumId:
            messageCodeId = f".{(msgNumId//1000000)%10}.{(msgNumId//10000)%100}.{msgNumId%1000}."
            if msgNumId < 20000000:
                messageCode = messageCode.replace(".ft.", ".FT" + messageCodeId)
            else:
                messageCode = messageCode.replace(".ft.", messageCodeId)
            return messageCode, msgNumId
    for code, pattern, splitChar in codesPatterns:
        m = pattern.match(messageCode)
        if m and m.lastindex is not None and m.lastindex >= 1:
            return  messageCode, code + sum(int(n) * 100**i
                                            for i,n in enumerate(reversed(m.group(1).split(splitChar))))
    return messageCode, unknown
