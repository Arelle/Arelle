'''
See COPYRIGHT.md for copyright information.
'''

from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import XbrlConst
from arelle.Version import copyrightLabel
import regex as re
from collections import defaultdict

def compile(list, traceRows):
    if traceRows:
        # compile so each row can be traced by separate expression (slow)
        return [(rowNbr, re.compile(r"(^|\s)" + pattern + r"($|\W+)", re.IGNORECASE))
                for rowNbr, pattern in list]
    else:
        # compile single expression for fast execution
        return re.compile(r"(^|\s)" +  # always be sure first word starts at start or after space
                          r"($|\W+)|(^|\s)".join(pattern for rowNbr, pattern in list)
                          .replace(r" ",r"\W+") + r"($|\W+)",
                          re.IGNORECASE)

def setup(val, traceRows=False, *args, **kwargs):
    if not val.validateLoggingSemantic:  # all checks herein are SEMANTIC
        return
    # determiniation of two way concept label based on pattern
    # definitions (from documentation label) are used if present, otherwise standard label for these tests
    val.twoWayPriItemDefLabelPattern = compile([
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml
            # Cash Flow
            (4, r"increase (\w+ )?decrease"),
            (5, r"provided by (\w+ )?used in"),
            (7, r"net cash inflow or outflow"),
            (6, r"net"),
            (8, r"change in"),
            (9, r"proceeds from (\w+ )?payments (for|to)"),
            # Income statement
            (13, r"(gain|profit) loss"),
            (16, r"income (expense|loss)"),
            (18, r"per share"),
            # Statement of Stockholders Equity
            (22, r"equity"),
            (23, r"retained earnings"),
            # removed? r"conversion of units",
            ], traceRows)
    # standard label tests, indicate two-way label
    val.twoWayPriItemStdLabelPattern = compile([
            # from Eric Cohen
            (4, r"Increase \(Decrease\)"),
            (5, r"Provided by \(Used in\)"),
            (6, r"Net"),
            (8, r"Change in"),
            (9, r"Proceeds from \(Payments for\)"),
            (10, r"Proceeds from \(Payments to\)"),
            (11, r"Payments for \(Proceeds from\)"),
            (12, r"Proceeds from \(Repayments of\)"),
            (13, r"Gain \(Loss\)"),
            (14, r"Profit \(Loss\)"),
            (15, r"Loss \(Gain\)"),
            (16, r"Income \(Loss\)"),
            (17, r"Income \(Expense\)"),
            (18, r"Per Share"),
            (19, r"Per Basic Share"),
            (20, r"Per Diluted Share"),
            (21, r"Per Basic and Diluted"),
            (24, r"Appreciation \(Depreciation\)"),
            (25, r"Asset \(Liability\)"),
            (26, r"Assets Acquired \(Liabilities Assumed\)"),
            (27, r"Benefit \(Expense\)"),
            (28, r"Expense \(Benefit\)"),
            (29, r"Cost[s] \(Credit[s]\)"),
            (30, r"Deductions \(Charges\)"),
            (31, r"Discount \(Premium\)"),
            (32, r"Due from \(to\)"),
            (33, r"Earnings \(Losses\)"),
            (34, r"Earnings \(Deficit\)"),
            (35, r"Excess \(Shortage\)"),
            (36, r"Gains \(Losses\)"),
            (37, r"Impairment \(Recovery\)"),
            (38, r"Income \(Loss\)"),
            (39, r"Liability \(Refund\)"),
            (40, r"Loss \(Recovery\)"),
            (41, r"Obligation[s] \(Asset[s]\)"),
            (42, r"Proceeds from \(Repayments of\)"),
            (43, r"Proceeds from \(Repurchase of\)"),
            (44, r"Provided by \(Used in\)"),
            (45, r"Provisions \(Recoveries\)"),
            (46, r"Retained Earnings \(Accumulated Deficit\)"),
            (47, r"per (\w+ )+"),
            (70, r"Conversion of Units"),
            (71, r"Effective (\w+ )?Rate"),
            ], traceRows)
    # determination of a one-way concept based on standard label
    val.oneWayPriItemDefLabelPattern = compile([
            (49, r"dividend (\w+ )*(paid|received)"),
            ], traceRows)

    val.oneWayPriItemStdLabelPattern = compile([
            (48, r"Payments of (\w+ )*\((Dividends|Capital)\)"),
            (49, r"Dividends (\w+ )*\((Pay(ment)?|Receive|Outstanding)\)"),
            (50, r"(Stock|Shares) Issued"),
            (51, r"Stock (\w+ )*Repurchased"),
            (52, r"(Stock|Shares) (\w+ )*Repurchase[d]?"),
            (53, r"Treasury Stock (\w+ )*(Beginning (\w+ )*Balance[s]?|Ending (\w+ )*Balance[s]?)"),
            (54, r"Treasury Stock (\w+ )*Acquired"),
            (55, r"Treasury Stock (\w+ )*Reissued"),
            (56, r"Treasury Stock (\w+ )*Retired"),
            (57, r"Accumulated Depreciation (\w+ )*Amortization"),
            (58, r"Accumulated Other Than Temporary Impairments"),
            (59, r"Allowance (\w+ )*Doubtful Accounts"),
            (60, r"Amortization (\w+ )*Pension Costs"),
            (61, r"Available for Sale Securities (\w+ )*Continuous Loss Position"),
            (62, r"Available for Sale Securities Bross Unrealized Losses"),
            (63, r"Accounts"),
            ], traceRows)
    # determination of a two way fact based on any of fact's dimension member label
    val.twoWayMemberStdLabelPattern = compile([
            # per Eric Cohen
            (64, r"Change (in|during) \w+"), # don't match word with change in it like exchange
            (65, r"\w+ Elimination \w+"),
            (66, r"Adjustment"),
            (67, r"Effect\s"),
            (68, r"Gain(s)? (\w+ )*Loss(es)?"),
            (69, r"Income \(Loss\)"),
            (70, r"Net(ting)?"),  # don't want to match word with net in it like internet
            ], traceRows)
    val.schedules = {}
    val.elrMatches = (("1statement", re.compile(r"-\s+Statement\s+-\s+", re.IGNORECASE)),
                      ("2disclosure", re.compile(r"-\s+Disclosure\s+-\s+", re.IGNORECASE)),
                      ("3schedule", re.compile(r"-\s+Schedule\s+-\s+", re.IGNORECASE)))

def schedules(val, concept):
    try:
        return val.schedules[concept.qname]
    except KeyError:
        schedules = defaultdict(int)
        for rel in val.modelXbrl.relationshipSet(XbrlConst.parentChild).toModelObject(concept):
            for roleType in val.modelXbrl.roleTypes.get(rel.linkrole,()):
                for elrType, elrPattern in val.elrMatches:
                    if elrPattern.search(roleType.definition):
                        schedules[elrType] += 1
        scheduleStr = ""
        for elrType, num in sorted(schedules.items()):
            scheduleStr += ", {0} {1}{2}".format(num, elrType[1:], "s" if num > 1 else "")
        val.schedules[concept.qname] = scheduleStr
        return scheduleStr


def factCheck(val, fact, *args, **kwargs):
    if not val.validateLoggingSemantic:  # all checks herein are SEMANTIC
        return
    concept = fact.concept
    context = fact.context
    stdLabel = concept.label(lang="en-US", fallbackToQname=False)
    defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)

    try:
        if fact.isNumeric and not fact.isNil and fact.xValue is not None and fact.xValue < 0:
            # is fact an explicit non neg
            if ((defLabel is not None and val.oneWayPriItemDefLabelPattern.search(defLabel)) or
                (stdLabel is not None and val.oneWayPriItemStdLabelPattern.search(stdLabel))):
                if context.qnameDims:  # if fact has a member
                    if any((val.twoWayMemberStdLabelPattern.search(dim.member.label(lang="en-US", fallbackToQname=False))
                            for dim in context.qnameDims.values()
                            if dim.isExplicit)):  # any two way exception member
                        val.modelXbrl.log('INFO-SEMANTIC', "secStaffObservation.nonNegativeFact.info.A",
                            _("Negative fact of an explicit non-negative concept is tagged with a member expected to allow negative values: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                            value=fact.effectiveValue, elrTypes=schedules(val,concept))
                    else:
                        val.modelXbrl.log('WARNING-SEMANTIC', "secStaffObservation.nonNegativeFact.warning.B",
                            _("Negative fact of an explicit non-negative concept, member may or not justify a negative value: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                            value=fact.effectiveValue, elrTypes=schedules(val,concept))
                else: # no member
                    val.modelXbrl.log('INCONSISTENCY', "secStaffObservation.nonNegativeFact.inconsistency.C",
                        _("Negative fact of an explicit non-negative concept: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s %(elrTypes)s"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                        value=fact.effectiveValue, elrTypes=schedules(val,concept))
            # else test if fact meets two way rules
            elif ((defLabel is not None and val.twoWayPriItemDefLabelPattern.search(defLabel)) or
                  (stdLabel is not None and val.twoWayPriItemStdLabelPattern.search(stdLabel))):
                val.modelXbrl.log('INFO-SEMANTIC', "secStaffObservation.nonNegativeFact.info.D",
                    _("Negative fact of concept expected to have positive and negative values: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                    modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                    value=fact.effectiveValue, elrTypes=schedules(val,concept))
            else:
                if context.qnameDims:  # if fact has a member
                    if any((val.twoWayMemberStdLabelPattern.search(dim.member.label(lang="en-US", fallbackToQname=False))
                            for dim in context.qnameDims.values()
                            if dim.isExplicit)):  # any two way exception member
                        val.modelXbrl.log('INFO-SEMANTIC', "secStaffObservation.nonNegativeFact.info.E",
                            _("Negative fact for typically non-negative concept, but tagged with a member expected to allow negative values: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                            value=fact.effectiveValue, elrTypes=schedules(val,concept))
                    else:
                        val.modelXbrl.log('WARNING-SEMANTIC', "secStaffObservation.nonNegativeFact.warning.F",
                            _("Negative fact of a typically non-negative concept, member may or not justify a negative value: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                            value=fact.effectiveValue, elrTypes=schedules(val,concept))
                else: # no member
                    val.modelXbrl.log('INCONSISTENCY', "secStaffObservation.nonNegativeFact.inconsistency.G",
                        _("Negative fact of a \"presumed by default\" non-negative concept: %(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s"),
                        modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                        value=fact.effectiveValue, elrTypes=schedules(val,concept))
    except Exception as ex:
        val.modelXbrl.log('WARNING-SEMANTIC', "arelle:nonNegFactTestException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s%(elrTypes)s cannot be tested nonnegative"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue, elrTypes=schedules(val,fact))

def final(val, conceptsUsed, *args, **kwargs):
    if not val.validateLoggingSemantic:  # all checks herein are SEMANTIC
        return
    del val.twoWayPriItemDefLabelPattern
    del val.twoWayPriItemStdLabelPattern
    del val.oneWayPriItemStdLabelPattern
    del val.twoWayMemberStdLabelPattern
    del val.schedules


def saveDtsMatches(dts, secDtsTagMatchesFile):
    setup(dts, True)
    import sys, csv
    csvOpenMode = 'w'
    csvOpenNewline = ''
    csvFile = open(secDtsTagMatchesFile, csvOpenMode, newline=csvOpenNewline)
    csvWriter = csv.writer(csvFile, dialect="excel")
    csvWriter.writerow(("Concept", "Rule", "Row", "Pattern", "Label", "Documentation"))
    num1wayConcepts = 0
    num2wayConcepts = 0
    num2wayMembers = 0

    for qname, concept in sorted(dts.qnameConcepts.items(), key=lambda item: item[0]):
        if concept.isItem and concept.isPrimaryItem: # both pri item and domain members
            stdLabel = concept.label(lang="en-US", fallbackToQname=False)
            defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
            if concept.type is not None and concept.type.isDomainItemType:
                if stdLabel is not None:
                    for rowNbr, pattern in dts.twoWayMemberStdLabelPattern:
                        if pattern.search(stdLabel):
                            csvWriter.writerow((str(qname), "member-2-way", rowNbr, pattern.pattern[6:-7], stdLabel, defLabel))
                            num2wayMembers += 1
            elif concept.isNumeric and not concept.isAbstract: # not dimension domain/member
                if defLabel is not None:
                    for rowNbr, pattern in dts.twoWayPriItemDefLabelPattern:
                        if pattern.search(defLabel):
                            csvWriter.writerow((str(qname), "concept-2-way-doc", rowNbr, pattern.pattern[6:-7], stdLabel, defLabel))
                            num2wayConcepts += 1
                    for rowNbr, pattern in dts.oneWayPriItemDefLabelPattern:
                        if pattern.search(defLabel):
                            csvWriter.writerow((str(qname), "concept-1-way-doc", rowNbr, pattern.pattern[6:-7], stdLabel, defLabel))
                            num1wayConcepts += 1
                if stdLabel is not None:
                    for rowNbr, pattern in dts.twoWayPriItemStdLabelPattern:
                        if pattern.search(stdLabel):
                            csvWriter.writerow((str(qname), "concept-2-way-lbl", rowNbr, pattern.pattern[6:-7], stdLabel, defLabel))
                            num2wayConcepts += 1
                    for rowNbr, pattern in dts.oneWayPriItemStdLabelPattern:
                        if pattern.search(stdLabel):
                            csvWriter.writerow((str(qname), "concept-1-way-lbl", rowNbr, pattern.pattern[6:-7], stdLabel, defLabel))
                            num1wayConcepts += 1

    csvFile.close()

    dts.log('INFO-SEMANTIC', "info:saveSecDtsTagMatches",
             _("SecDtsTagMatches entry %(entryFile)s has %(numberOfTwoWayPriItems)s two way primary items, %(numberOfOneWayPriItems)s one way primary items, %(numberOfTwoWayMembers)s two way members in output file %(secDtsTagMatchesFile)s."),
             modelObject=dts,
             entryFile=dts.uri,
             numberOfTwoWayPriItems=num2wayConcepts,
             numberOfOneWayPriItems=num1wayConcepts,
             numberOfTwoWayMembers=num2wayMembers,
             secDtsTagMatchesFile=secDtsTagMatchesFile)

    final(dts)

def saveDtsMatchesMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save SEC tag matches",
                     underline=0,
                     command=lambda: saveDtsMatchesMenuCommand(cntlr) )

def saveDtsMatchesMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return

        # get file name into which to save log file while in foreground thread
    secDtsTagMatchesFile = cntlr.uiFileDialog("save",
            title=_("Save SEC DTS tag matches file"),
            filetypes=[(_("DTS tag matches .csv file"), "*.csv")],
            defaultextension=".txt")
    if not secDtsTagMatchesFile:
        return False

    try:
        saveDtsMatches(cntlr.modelManager.modelXbrl, secDtsTagMatchesFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("SEC DTS Tags Matches exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveDtsMatchesCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--save-sec-tag-dts-matches",
                      action="store",
                      dest="secDtsTagMatchesFile",
                      help=_("Save SEC DTS tag matches CSV file."))

def saveDtsMatchesCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "secDtsTagMatchesFile", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        saveDtsMatches(cntlr.modelManager.modelXbrl, options.secDtsTagMatchesFile)

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate US SEC Tagging',
    'version': '0.9',
    'description': '''US SEC Tagging Validation.  Includes non-negative rules.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final,
    'CntlrWinMain.Menu.Tools': saveDtsMatchesMenuEntender,
    'CntlrCmdLine.Options': saveDtsMatchesCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveDtsMatchesCommandLineXbrlRun,
}
