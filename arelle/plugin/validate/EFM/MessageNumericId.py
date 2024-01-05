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
    (efmStart,  re_compile(r"EFM\.([0-9]+(\.[0-9]+)*).*"), "."),
    (ixStart,   re_compile(r"ix11\.([0-9]+(\.[0-9]+)*).*"), "."),
    (efmStart,  re_compile(r"xbrl\.([0-9]+(\.[0-9]+)*).*"), "."),
    (xbrlStart, re_compile(r"EFM\.([0-9]+(\.[0-9]+)*).*"), "."),
    (xml1Start, re_compile(r"xmlSchema.valueError"), "."),
    (xml2Start, re_compile(r"xmlSchema"), "."),
    (xml3Start, re_compile(r"lxml.SCHEMA[A-Za-z_]*([0-9]+(_[0-9]+)*).*"), "_"),
    )
deiSubTblCodes = {"DocumentType": 26052000, "EntityRegistrantName": 26052400, "EntityCentralIndexKey": 26052300}
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
    (100000, "General Instruction II.H,I"), # should be first since it is combined with another rule.
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

# when assigning a new number need to make sure it won't collide with a number already assigned for that element
# numbers from 1 to 99
ftValidations = {
    "amdFileNb": 1, "cpFuture": 2, "dailyFeeRate": 3, "dateFldRange": 4, "dbtVal4": 5, "dbtVal5": 6,
    "dbtVal6": 7, "dbtVal7": 8, "dbtVal8": 9, "duplicateItem": 10, "netFeeAmt": 11, "newFeeAmt": 12,
    "numAggAmt": 13, "numAmtSec": 14, "numCdtsAmt": 15, "numFeeAmt": 16, "numPerSec": 17, "oClmNAFlds": 18,
    "oClmRqdFlds": 19, "oClmSrc": 20, "ofPrvPd": 21, "oFrmTyp": 22, "ofRqdFlds": 23, "oFuture": 24, "omitableFeeRate": 25,
    "oPrrFileNb": 26, "oRqdFlds": 27, "oSrcAmt": 28, "oSrcNAFlds": 29, "oSrcRqdFlds": 30, "otherFeeAmt": 31, "otherMAOP": 32,
    "otherNoOf0TotFee": 33, "otherRqdFlds": 34, "otherSecType": 35, "r011CEFTxVal": 36, "r011Flg": 37, "r011NewRqdFlds": 38,
    "r011RqdFlds": 39, "r011TxVal": 40, "r415a6FrmTyp": 41, "r415a6NAFlds": 42, "r415a6RqdFlds": 43, "r415a6SecType": 44,
    "r424iAdrDep": 45, "r424iAmtDue": 46, "r424iDateDiff": 47, "r424iDaysLate": 48, "r424iEndDate": 49, "r424iFeeAmt": 50,
    "r424iFeeOf": 51, "r424iFeeOfUnsold": 52, "r424iFileNb": 53, "r424iFutureDate": 54, "r424iIntDue": 55, "r424iNetSls": 56,
    "r424iNetSls0": 57, "r424iOfSrc": 58, "r424iRdmtCr": 59, "r424iRdmtCr0": 60, "r424iRqdFeeInt": 61, "r424iRqdFlds": 62,
    "r424iRqdNetSls": 63, "r424iRqdRdmtCr": 64, "r424iRqdTtlFee": 65, "r424iRuleRef": 66, "r424iStatCtry": 67, "r429FileNb": 68,
    "r429FileNbNotClm": 69, "r429FrmTyp": 70, "r429RqdFlds": 71, "r429SecType": 72, "r457aMAOP": 73, "r457aNewRqdFlds": 74,
    "r457aRqdFlds": 75, "r457aSecType": 76, "r457b011ClmNAFlds": 77, "r457bO11Expl": 78, "r457bO11SrcDate": 79,
    "r457f457aRqdFlds": 80, "r457fMAOP": 81, "r457fMAOPsums": 82, "r457fNAFlds": 83, "r457fNegMAOP": 84,
    "r457fNewFeeAmt": 85, "r457fNewRqdFlds": 86, "r457fRqdFlds": 87, "r457fRuleRef": 88, "r457fSecType": 89,
    "r457fValSecRcvd": 90, "r457oFeeAmt": 91, "r457oNewRqdFlds": 92, "r457oOmitableFlds": 93, "r457oRqdFlds": 94,
    "r457oSecType": 95, "r457pClmPrrSctyTyp": 96, "r457pClmRqdFlds": 97, "r457pClmSecTitle": 98, "r457pFileNb": 99,
    "r457rMAOP": 1, "r457rOmitableFlds": 2, "r457rRqdFlds": 3, "r457rSecType": 4, "r457rWKSI": 5, "r457sMAOP": 6,
    "r457sOmitableFlds": 7, "r457sRqdFlds": 8, "r457sSecType": 9, "r457uNAFlds": 10, "r457uRqdFlds": 11,
    "r457uSecType": 12, "rqdFileNb": 13, "ttlFeeAmt": 14, "ttlOfAmt": 15, "ttlOfstAmt": 16, "ttlOfstLeTotFee": 17,
    "ttlRqdFlds": 18, "ttlTxValtn": 19, "txtFldChars": 20, "usrSty27": 21, "usrSty30": 22, "usrSty32": 23,
    "usrSty3334MAOP": 24, "usrSty3334MAOPsums": 25, "usrSty3334valSecRcvd": 26, "usrSty3334RqdFlds": 87, "usrSty42": 30, "usrSty43": 31, "usrSty50": 32, "usrSty6a": 33, "usrSty6b": 34, "usrSty6c": 35,
    "usrSty9": 36, "uusFileNb": 37, "uusNAflds": 38, "usrSty2": 41, "usrSty10": 40, "uusRqdChild": 42, "footNoteLen": 27,
    "subTpMismatch": 1, "numRate": 66, "r415a6FileNb": 51
}

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
                        msgNumId += (ftSubTbl.index(conceptLn) + 1) * 100
                        if subType.startswith("424I"):
                            msgNumId += 20000
                        else:
                            msgNumId += 10000
                    elif conceptLn in ftSumTbl:
                        conceptLnNumeric = ftSumTbl.index(conceptLn) + 1
                        msgNumId += code + 1000000
                        msgNumId += conceptLnNumeric * 100
                        if subType.startswith("424I"):
                            msgNumId += 10000
                        elif subType.startswith("SC"):
                            msgNumId += 20000
                        elif conceptLnNumeric <= 8:
                            msgNumId += 30000
                        elif subType.startswith("POS"):
                            msgNumId += 40000
                        elif subType.startswith("424B"):
                            msgNumId += 50000
                else:
                    msgNumId += code
                    if tblConcepts and conceptLn in tblConcepts:
                        msgNumId += (tblConcepts.index(conceptLn) + 1) * 100
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
            messageCodeId = f".{(msgNumId//1000000)%10}.{(msgNumId//10000)%100}.{msgNumId//100%100}."
            if msgNumId < 20000000:
                messageCode = messageCode.replace(".ft.", ".FT" + messageCodeId)
                # add validation number id
                # not needed for dei codes in the 20,000,000 range inly for FT codes
                msgNumId += ftValidations.get(messageCode.split(".")[-1], 0)
            else:
                messageCode = messageCode.replace(".ft.", messageCodeId)
            return messageCode, msgNumId
    for code, pattern, splitChar in codesPatterns:
        m = pattern.match(messageCode)
        if m and m.lastindex is not None and m.lastindex >= 1:
            # numeric id format = 20,000,000 efm start
            # 6,000,000 efm chapter
            # 050,000 efm section
            # 2,100 efm subsection
            return  messageCode, code + sum(int(n) * 10**(i*2)
                                            for i,n in enumerate(reversed(m.group(1).split(splitChar)), start=1))
    return messageCode, unknown
