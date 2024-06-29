import csv
import json
import os
from arelle import XbrlConst
from .MessageNumericId import deiSubTblCodes, ftSubTbl, ftSumTbl, ftOfferingTbl, ftOffsetTbl, ftCmbPrsTbl, ft424iTbl, ftStart, ftTableStartCode, ftValidations, ftRuleCode, efmStart
from .Consts import attachmentDocumentTypeValidationRulesFiles


class FtValidations:
    RULES = {
        "Offering": {
            "Rule457aFlg": "Rule 457(a)",
            "Rule457fFlg": "Rule 457(f)",
            "Rule457oFlg": "Rule 457(o)",
            "Rule457uFlg": "Rule 457(u)",
            "Rule457rFlg": "Rule 457(r)",
            "Rule457sFlg": "Rule 457(s)",
            "Rule011Flg": "Rule 0-11",
            "FeesOthrRuleFlg": "Other Rule",
            "Rule415a6Flg": "Rule 415(a)(6)",
            "GnlInstrIIhiFlg": "General Instruction II.H,I"
        },
        "Offset": {
            "Rule457bOffsetFlg": "Rule 457(b)",
            "Rule011a2OffsetFlg": "Rule 0-11(a)(2)",
            "Rule457pOffsetFlg": "Rule 457(p)"
        },
        "Combined Prospectus": {
            "Rule429CmbndPrspctsFlg": "Rule 429"
        }
    }

    def __init__(self, cntlr, typePattern, outName=None):
        self.cntlr = cntlr
        self.typePattern = typePattern
        self.outName = outName
        self._setup()
        return None

    def generateValidations(self):
        validations = sorted(self.parseValidations(), key=lambda x: x.get("Arelle Validation Rule ID", 0) )
        with open(self.outName, "w", newline="") as outFile:
            writer = csv.DictWriter(outFile, fieldnames=self.columns)
            writer.writeheader()
            for validation in validations:
                writer.writerow(validation)

    def parseValidations(self):
        formTypeSevs = []
        for sev in self.validationsJson["sub-type-element-validations"]:
            if sev.get("efm") == "6.5.20":
                formTypeSevs.append(sev)
            else:
                for validation in self.getValidationsFromSev(sev):
                    yield validation
        yield self._getFormTypeSevsValidation(formTypeSevs)

    def getValidationsFromSev(self, sev):
        if sev.get("validation"):
            xbrlNames = self._getxbrlNames(sev)
            for xbrlName in xbrlNames:
                ruleReferences = self._getRuleReference(xbrlName, sev)
                for ruleReference in ruleReferences:
                    for numericID, subTypes in self._getMessageNumericID(xbrlName, sev, ruleReference):
                        row = {}
                        row["Rule Reference"] = ruleReference
                        row["Data Element"] = self._getDataElement(xbrlName, sev)
                        validationLineType = self._getValidationLineType(xbrlName, sev)
                        row["Fees to be Paid"] = validationLineType["Fees to be Paid"]
                        row["Fees Previously Paid"] = validationLineType["Fees Previously Paid"]
                        row["Offset Claim"] = validationLineType["Offset Claim"]
                        row["Offset Source"] = validationLineType["Offset Source"]
                        row["XBRL Name"] = xbrlName
                        row["Arelle Validation rule name"] = sev.get("efm")
                        row["Arelle Validation Rule ID"] = numericID
                        row["Validation Severity"] = self._getValidationSeverity(sev)
                        row["Validation Description"] = sev.get("comment-validation")
                        row["Validation Message"] = self._getValidationMessage(xbrlName, sev)
                        row["Exception Handling"] = sev.get("comment-exception-handling")
                        row["Submission Types"] = subTypes
                        row["Conversion Requested"] = sev.get("comment-conversion-requested")
                        row["Requesting D/O"] = sev.get("comment-requesting-do")
                        row["Date Requested"] = sev.get("comment-date-requested")
                        row["Reason for Conversion"] =sev.get("comment-reason")
                        yield row

    def _setup(self):
        self.validationFileName = self._getValidationsFileName()
        self.validationFilePath = os.path.join(os.path.dirname(__file__), "resources", self.validationFileName)
        self.validationFileBasePath = os.path.dirname(self.validationFilePath)
        self.columns = [
            "Rule Reference", "Data Element", "Fees to be Paid", "Fees Previously Paid", "Offset Claim", "Offset Source",
            "XBRL Name", "Arelle Validation rule name", "Arelle Validation Rule ID", "Validation Severity",
            "Validation Description", "Validation Message", "Exception Handling", "Submission Types", "Conversion Requested",
            "Requesting D/O", "Date Requested", "Reason for Conversion"
            ]
        with open(self.validationFilePath, "r") as file:
            self.validationsJson = json.load(file)
        self.submissionTypeClasses = self._compileSubmissionTypeClasses()
        if not self.outName:
            self.outName = os.path.join(self.validationFileBasePath, "ft-validations.csv")
        try:
            # SEC FtJsonToOimJson module not published to open source repo.
            from .FtJsonToOimJson import getLatestTaxonomyFamily
        except ModuleNotFoundError as err:
            raise RuntimeError("Private SEC module imported, not of use outside EDGAR.") from err
        latestFFD = getLatestTaxonomyFamily(self.cntlr, "FFD")
        self.cntlr.modelManager.load(latestFFD.href)

    def _getFormTypeSevsValidation(self, formTypeSevs):
        subTypes = self._getSubtypeFormMapping(formTypeSevs)
        for validation in self.getValidationsFromSev(formTypeSevs[0]):
            validation["Submission Types"] = json.dumps(subTypes)
            return validation

    def _getSubtypeFormMapping(self, formTypeSevs):
        mapping = {}
        for formTypeSev in formTypeSevs:
            for subType in formTypeSev.get("sub-types", []):
                if subType in mapping:
                    mapping[subType].extend(formTypeSev.get("value", []))
                else:
                    mapping[subType] = formTypeSev.get("value", [])
        return mapping

    def _compileSubmissionTypeClasses(self):
        STC = self.validationsJson["sub-type-classes"]
        expandedSTC = {}

        def compileSubs(subTypes):
            for subType in subTypes:
                if subType.startswith("@"):
                    for st in compileSubs(STC[subType[1:]]):
                        yield st
                else:
                    yield subType

        for stcName, subTypes in self.validationsJson["sub-type-classes"].items():
            if not "comment" in stcName and not "Comment" in stcName:
                expandedSubTypes = []
                for subType in compileSubs(subTypes):
                    expandedSubTypes.append(subType)
                expandedSTC[stcName] = expandedSubTypes
        return expandedSTC

    def _getMessageFromSev(self, sev):
        if sev.get("message"):
            messageID = sev["message"]
            messageTemplate = self.validationsJson["messages"][messageID]
            return (messageID, messageTemplate)
        if sev.get("validation") and not sev.get("validation") in {"fo", "skip-if-absent"}: # optional validation does not result in any message
            messageID = self.validationsJson["validations"][sev["validation"]]["message"]
            messageTemplate = self.validationsJson["messages"][messageID]
            return (messageID, messageTemplate)
        return (None, None)

    def _getValidationsFileName(self):
        for typePattern, fileName in attachmentDocumentTypeValidationRulesFiles:
            if typePattern == self.typePattern:
                return fileName
        return None

    def _getxbrlNames(self, sev):
        messageID, messageTemplate = self._getMessageFromSev(sev)
        if messageID:
            if sev.get("validation") == "fdepflag-any" and len(self._getAxesFromSev(sev)) > 1:
                return sev["references"][:1]
            if sev.get("validation") == "of-rule":
                return [", ".join(sev["xbrl-names"] if isinstance(sev["xbrl-names"], list) else [sev["xbrl-names"]])]
            if sev.get("axis", sev.get("references-axes")) != sev.get("references-axes", sev.get("axis")):
                # assuming mismatching references-axes would indicate the main axis is being checked.
                return sev["xbrl-names"] if isinstance(sev["xbrl-names"], list) else [sev["xbrl-names"]]
            if sev.get("validation") == "noDups":
                return [f"{tableName} [table]" for tableName in self._getTableNamesFromSev(sev)]
            if "{tag}" in messageID or "{tags}" in messageID:
                return sev["xbrl-names"] if isinstance(sev["xbrl-names"], list) else [sev["xbrl-names"]]
            elif "{otherTag}" in messageID:
                return sev["references"] if isinstance(sev["references"], list) else [sev["references"]]
            elif sev.get("msgCoda"):
                if "{tag}" in sev.get("msgCoda"):
                    return sev["xbrl-names"] if isinstance(sev["xbrl-names"], list) else [sev["xbrl-names"]]
                elif "{otherTag}" in sev.get("msgCoda"):
                    return sev["references"] if isinstance(sev["references"], list) else [sev["references"]]
                else:
                    return sev["xbrl-names"] if isinstance(sev["xbrl-names"], list) else [sev["xbrl-names"]]
        return []

    def _getAxesFromSev(self, sev):
        if sev.get("validation") == "noDups":
            return sev.get("axis", "").split("-")
        if sev.get("axis", sev.get("references-axes")) != sev.get("references-axes", sev.get("axis")):
            # assuming mismatching references-axes would indicate the main axis is being checked.
            return sev.get("axis", "").split("-")
        messageID, messageTemplate = self._getMessageFromSev(sev)
        if messageID:
            if "{tag}" in messageID:
                return sev.get("axis", "").split("-")
            elif "{otherTag}" in messageID:
                return sev.get("references-axes", sev.get("axis", "")).split("-")
            elif sev.get("msgCoda"):
                if "{tag}" in sev.get("msgCoda"):
                    return sev.get("axis", "").split("-")
                elif "{otherTag}" in sev.get("msgCoda"):
                    return sev.get("references-axes", sev.get("axis", "")).split("-")
                else:
                    return sev.get("axis", "").split("-")
        return []

    def _getRuleReferenceText(self, name):
        for tableFlags in self.RULES.values():
            for ruleFlag, ruleText in tableFlags.items():
                if ruleFlag == name:
                    return ruleText

    def _getRulesFromSev(self, sev, table):
        rules = []
        for rule, ruleText in self.RULES[table].items():
            ffdRule = f"ffd:{rule}"
            if ffdRule in sev.get("xbrl-names", []):
                rules.append(ruleText)
            elif ffdRule in sev.get("where", []):
                if True in sev["where"][ffdRule] and not "!not!" in sev["where"][ffdRule]:
                    rules.append(ruleText)
            elif ffdRule in sev.get("references-where", []):
                if True in sev["references-where"][ffdRule] and not "!not!" in sev["references-where"][ffdRule]:
                    rules.append(ruleText)
        if not rules:
            for rule, ruleText in self.RULES[table].items():
                ffdRule = f"ffd:{rule}"
                ruleWhere = sev.get("where", {}).get(ffdRule, []) + sev.get("references-where", {}).get(ffdRule, [])
                if (not "absent" in ruleWhere and not False in ruleWhere) and not (True in ruleWhere and "!not!" in ruleWhere):
                    rules.append(ruleText)
        return rules

    def _getXbrlNameExNS(self, xbrlName):
        return xbrlName.split(":")[-1]

    def _getRuleReference(self, xbrlName, sev):
        xbrlNameExNS = self._getXbrlNameExNS(xbrlName)
        axes = self._getAxesFromSev(sev)
        if sev.get("efm") == "ft.usrSty42":
            return ["Rule Flag Issue"]
        if xbrlName.endswith("Flg") and "Rule" in xbrlName or sev.get("validation", "").startswith("exist-in-axis"):
            if "usrSty" in sev.get("efm"):
                usrStyNumber = sev.get("efm").split(".")[-1].replace("usrSty", "")
                return [f"User Story {usrStyNumber}"]
            return ["Rule Flag Issue"]
        if sev.get("validation") == "noDups":
            if "of" in axes:
                return self._getRulesFromSev(sev, "Offering")
            if "o" in axes:
                return self._getRulesFromSev(sev, "Offset")
            if "cp" in axes:
                return self._getRulesFromSev(sev, "Combined Prospectus")
            if "s424i" in axes:
                return ["Securities, 424I"]
        if xbrlNameExNS in ftSubTbl or xbrlNameExNS in deiSubTblCodes:
            return ["Submission Table"]
        if xbrlNameExNS in ftSumTbl:
            return ["Fees Summary"]
        if (xbrlNameExNS in ftOfferingTbl or "header:" in xbrlName) and "of" in axes:
            return self._getRulesFromSev(sev, "Offering")
        if xbrlNameExNS in ftOffsetTbl and "o" in axes:
            return self._getRulesFromSev(sev, "Offset")
        if xbrlNameExNS in ftCmbPrsTbl and "cp" in axes:
            return self._getRulesFromSev(sev, "Combined Prospectus")
        if xbrlNameExNS in ft424iTbl and "s424i" in axes:
            return ["Securities, 424I"]
        return []

    def _getDataElement(self, xbrlName, sev):
        if sev.get("validation") == "noDups":
            return xbrlName
        if xbrlName.startswith("header:"):
            return xbrlName
        if ", " in xbrlName:
            labels = []
            for name in xbrlName.split(", "):
                xbrlNameExNS = self._getXbrlNameExNS(name)
                concepts = self.cntlr.modelManager.modelXbrl.nameConcepts.get(xbrlNameExNS, "")
                if concepts:
                    labels.append(concepts[0].label(XbrlConst.terseLabel))
            return ", ".join(labels)
        xbrlNameExNS = self._getXbrlNameExNS(xbrlName)
        concepts = self.cntlr.modelManager.modelXbrl.nameConcepts.get(xbrlNameExNS, "")
        if concepts:
            return concepts[0].label(XbrlConst.terseLabel)
        return concepts

    def _getLineType(self, xbrlName, sev, flagName):
        # returns tuple with 2 strings.
        # If the flagName should only be true ("X", "")
        # If the flagName can be true and false ("X", "X")
        # If the flagName not specified in whereClause ("X", "X")
        if flagName in sev.get("where", {}):
            whereValues = sev["where"][flagName]
            if True in whereValues and False in whereValues:
                return ("X", "X")
            if True in whereValues:
                return ("X", "")
        return ("X", "X")

    def _getValidationLineType(self, xbrlName, sev):
        xbrlNameExNS = self._getXbrlNameExNS(xbrlName)
        lineTypes = {
            "Fees to be Paid": "",
            "Fees Previously Paid": "",
            "Offset Claim": "",
            "Offset Source": ""
        }
        if xbrlNameExNS in ftOfferingTbl:
            lineTypes["Fees Previously Paid"], lineTypes["Fees to be Paid"] = self._getLineType(xbrlName, sev, "ffd:PrevslyPdFlg")
        if xbrlNameExNS in ftOffsetTbl:
            lineTypes["Offset Claim"], lineTypes["Offset Source"] = self._getLineType(xbrlName, sev, "ffd:OffsetClmdInd")
        return lineTypes

    def _getTableNamesFromSev(self, sev):
        tableNames = []
        for axis in self._getAxesFromSev(sev):
            if axis == "of":
                tableNames.append("Offering")
            elif axis == "o":
                tableNames.append("Offset")
            elif axis == "cp":
                tableNames.append("Combined Prospectus")
            elif axis == "s424i":
                tableNames.append("Securities, 424I")
        return tableNames

    def _getMessageNumericID(self, xbrlName, sev, ruleReference):
        msgNumId = ftStart
        subTypes = self._getSubTypes(sev)
        xbrlNameExNS = self._getXbrlNameExNS(xbrlName)
        subTypesList = [st.strip() for st in subTypes.split(",")] if subTypes else []

        if not "ft" in sev.get("efm"):
            msgNumId = efmStart
            msgNumId += sum(int(n) * 10**(i*2) for i,n in enumerate(reversed(sev.get("efm", "").split(".")), start=1))
            return [(msgNumId, subTypes)]

        validationName = sev.get("efm").split(".")[-1]
        validationNumber = ftValidations.get(validationName, 0)
        numericIDs = []

        if sev.get("validation") == "fdepflag-any" and len(self._getAxesFromSev(sev)) > 1:
            return [(msgNumId + validationNumber, subTypes)]

        if xbrlNameExNS in deiSubTblCodes:
            msgNumId = deiSubTblCodes[xbrlNameExNS]
            return [(msgNumId + validationNumber, subTypes)]
        elif xbrlNameExNS in ftSubTbl:
            msgNumId += ftTableStartCode[0][0]
            msgNumId += (ftSubTbl.index(xbrlNameExNS) + 1) * 100
            msgNumId += validationNumber
            if "424I" in subTypesList:
                numericIDs.append((msgNumId + 20000, "424I"))
                if len(subTypesList) == 1:
                    return numericIDs
            numericIDs.append((msgNumId + 10000, ", ".join([st for st in subTypesList if st != "424I"])))
            return numericIDs
        elif xbrlNameExNS in ftSumTbl:
            msgNumId += ftTableStartCode[0][0] + 1000000
            msgNumId += (ftSumTbl.index(xbrlNameExNS) + 1) * 100
            msgNumId += validationNumber
            scSubTypes = []
            nonSc424SubTypes = []
            posSubTypes = []
            SubTypes424B = []
            for st in subTypesList:
                if st.startswith("SC") or st.startswith("PRER") or st.startswith("PREM"):
                    scSubTypes.append(st)
                if not (st.startswith("SC") or st.startswith("PRER") or st.startswith("PREM")) and not st == "424I":
                    nonSc424SubTypes.append(st)
                if st.startswith("POS"):
                    posSubTypes.append(st)
                if st.startswith("424B"):
                    SubTypes424B.append(st)

            if "424I" in subTypesList:
                numericIDs.append((msgNumId + 10000, "424I"))
            if scSubTypes:
                numericIDs.append((msgNumId + 20000, ", ".join(scSubTypes)))
            if ftSumTbl.index(xbrlNameExNS) + 1 <= 8 and nonSc424SubTypes:
                numericIDs.append((msgNumId + 30000, ", ".join(nonSc424SubTypes)))
            else:
                if posSubTypes:
                    numericIDs.append((msgNumId + 40000, ", ".join(posSubTypes)))
                if SubTypes424B:
                    numericIDs.append((msgNumId + 50000, ", ".join(SubTypes424B)))
                if nonSc424SubTypes:
                    numericIDs.append((msgNumId, ", ".join(nonSc424SubTypes)))
            return numericIDs
        ruleCode = 0
        if not (xbrlNameExNS.endswith("Flg") and "Rule" in xbrlNameExNS):
            for (ruleNumber, ruleText) in ftRuleCode:
                if ruleText in ruleReference:
                    ruleCode = ruleNumber
                    break
        tableNames = self._getTableNamesFromSev(sev)
        for (code, tblName, tblConcepts) in ftTableStartCode:
            if tblConcepts == None:
                continue
            if sev.get("validation") == "noDups" and tblName in xbrlNameExNS:
                numericIDs.append((msgNumId + code + ruleCode + validationNumber, subTypes))
                break
            if (xbrlNameExNS in tblConcepts or "header:" in xbrlName) and tblName in tableNames:
                conceptCode = 0 if "header:" in xbrlName else (tblConcepts.index(xbrlNameExNS) + 1) * 100
                numericIDs.append((msgNumId + code + ruleCode + conceptCode + validationNumber, subTypes))
            elif xbrlNameExNS in self.RULES.get(tblName, {}):
                numericIDs.append((msgNumId + code + validationNumber, subTypes))
        return numericIDs

    def _getValidationSeverity(self, sev):
        severityMapping = {
            "warning": "W",
            "error": "E",
            "info": "I"
        }
        if sev.get("severity"):
            return severityMapping.get(sev["severity"])
        if sev.get("validation"):
            return severityMapping.get(self.validationsJson["validations"].get(sev["validation"], {}).get("severity"))

    def _processMessageArgs(self, messageTemplate, sev):
        messageArgs = self.validationsJson["validations"][sev["validation"]]
        for messageArg, value in messageArgs.items():
            if sev.get(messageArg) and messageArg != "value":
                messageTemplate = messageTemplate.replace(f"{{{messageArg}}}", sev.get(messageArg))
            else:
                messageTemplate = messageTemplate.replace(f"{{{messageArg}}}", value)
        if "{severityVerb}" in messageTemplate:
            severity = sev.get("severity") or messageArgs.get("severity")
            severityVerb = {"warning": "should", "error": "must", "info": "may"}.get(severity, "{severityVerb}")
            messageTemplate = messageTemplate.replace("{severityVerb}", severityVerb)
        if "{msgCoda}" in messageTemplate and sev.get("msgCoda"):
            messageTemplate = messageTemplate.replace("{msgCoda}", sev["msgCoda"])
        if "{comparison}" in messageTemplate:
            comparison = sev.get("comparison")
            comparisonText = sev.get("comparisonText", messageArgs.get("comparisonText", comparison)).format(comparison=comparison)
            messageTemplate = messageTemplate.replace("{comparison}", comparisonText)
        if "{expectedValue}" in messageTemplate:
            def getExpectValue(key):
                expectedValue = [json.dumps(value) for value in sev[key] if value != "!not!" ]
                expectedValue = "one of " + ", ".join(expectedValue) if len(expectedValue) > 1 else expectedValue[0]
                return expectedValue
            if sev.get("value"):
                expectedValue = getExpectValue("value")
                messageTemplate = messageTemplate.replace("{expectedValue}", expectedValue)
            elif sev.get("validation") == "fdepflag-ref-value":
                expectedValue = getExpectValue("reference-value")
                messageTemplate = messageTemplate.replace("{expectedValue}", expectedValue)
            elif sev.get("value-date-range") or sev.get("value-numeric-range"):
                rangeKey = "value-date-range" if sev.get("value-date-range") else "value-numeric-range"
                expectedValue = f"from {sev[rangeKey][0]} to {sev[rangeKey][1]}"
                messageTemplate = messageTemplate.replace("{expectedValue}", expectedValue)
        return messageTemplate

    def _getValidationMessage(self, xbrlName, sev):
        messageID, messageTemplate = self._getMessageFromSev(sev)
        if messageID:
            xbrlNameExNS = self._getXbrlNameExNS(xbrlName)
            if sev.get("msgCoda"):
                messageTemplate = messageTemplate.replace("{msgCoda}", sev["msgCoda"])
            else:
                messageTemplate = messageTemplate.replace("{msgCoda}", "")

            if "{tag}" in messageID:
                messageID = messageID.replace("{tag}", xbrlNameExNS)
                messageTemplate = messageTemplate.replace("{tag}", xbrlName)
            elif "{tags}" in messageID:
                names = sev.get("xbrl-names", []) if isinstance(sev.get("xbrl-names", []), list) else [sev.get("xbrl-names")]
                xbrlNamesExNS = [self._getXbrlNameExNS(xbrlNm) for xbrlNm in names]
                messageID = messageID.replace("{tags}", "-".join(xbrlNamesExNS))
                messageTemplate = messageTemplate.replace("{tags}", ", ".join(names))
            elif "{otherTag}" in messageID:
                if sev.get("validation") == "fdepflag-any":
                    names = sev.get("references", []) if isinstance(sev.get("references", []), list) else [sev.get("references")]
                    messageID = messageID.replace("{otherTag}", "-".join([self._getXbrlNameExNS(xbrlNm) for xbrlNm in names]))
                    messageTemplate = messageTemplate.replace("{otherTag}", ", ".join([xbrlNm for xbrlNm in sev.get("references", [])]))
                else:
                    messageID = messageID.replace("{otherTag}", xbrlNameExNS)
                    messageTemplate = messageTemplate.replace("{otherTag}", xbrlName)
            elif sev.get("msgCoda"):
                if "{tag}" in sev.get("msgCoda"):
                    messageTemplate = messageTemplate.replace("{tag}", xbrlName)
                elif "{tags}" in sev.get("msgCoda"):
                    names = sev.get("xbrl-names", []) if isinstance(sev.get("xbrl-names", []), list) else [sev.get("xbrl-names")]
                    messageTemplate = messageTemplate.replace("{tags}", ", ".join(names))
                elif "{otherTag}" in sev.get("msgCoda"):
                    messageTemplate = messageTemplate.replace("{otherTag}", xbrlName)
            if "{otherTag}" in messageTemplate:
                names = sev.get("references", []) if isinstance(sev.get("references", []), list) else [sev.get("references")]
                messageTemplate = messageTemplate.replace("{otherTag}", ", ".join(names))
            messageTemplate = self._processMessageArgs(messageTemplate, sev)
            if "{item}" in messageTemplate:
                names = sev.get("references", []) if isinstance(sev.get("references", []), list) else [sev.get("references")]
                messageTemplate = messageTemplate.replace("{item}", ", ".join(names))
            if "{otherLabel}" in messageTemplate:
                names = sev.get("references", []) if isinstance(sev.get("references", []), list) else [sev.get("references")]
                label = self._getDataElement(", ".join(names), sev)
                messageTemplate = messageTemplate.replace("{otherLabel}", label)
        return f"{messageID}: {messageTemplate}"

    def _getSubTypes(self, sev):
        if sev.get("sub-types", "n/a") in ["n/a", ["n/a"]]:
            subTypes = []
            for subType in self.submissionTypeClasses["all-Ixbrl"]:
                subTypes.append(subType)
            return ", ".join(subTypes)
        else:
            subTypes = []
            if "!not!" in sev["sub-types"]:
                subTypesToExclude = set()

                for subType in sev["sub-types"]:
                    if subType.startswith("@"):
                        for st in self.submissionTypeClasses[subType[1:]]:
                            subTypesToExclude.add(st)
                    else:
                        subTypesToExclude.add(subType)

                for subType in self.submissionTypeClasses["all-Ixbrl"]:
                    if not subType in subTypesToExclude:
                        subTypes.append(subType)
            else:
                for subType in sev["sub-types"]:
                    if subType.startswith("@"):
                        for st in self.submissionTypeClasses[subType[1:]]:
                            subTypes.append(st)
                    else:
                        subTypes.append(subType)
            return ", ".join(subTypes)
        return ""
