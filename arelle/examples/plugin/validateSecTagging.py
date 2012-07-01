from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import XbrlConst
import re

def compile(list):
    return re.compile('($|\W+)|'.join(list)
                      .replace(r" ",r"\W+") + "($|\W+)", 
                      re.IGNORECASE)
    
def setup(val):
    # determiniation of two way concept label based on pattern
    # definitions (from documentation label) are used if present, otherwise standard label for these tests
    val.twoWayPriItemDefLabelPattern = compile([
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml 
            # Cash Flow
            r"increase (\w+ )?decrease",
            r"provided by (\w+ )?used in",
            r"(^|\s)net",
            r"(^|\s)change in",
            r"proceeds from (\w+ )?payments (for|to)",
            # Income statement
            r"(gain|profit) loss",
            r"income (expense|loss)",
            r"per share",
            # Statement of Stockholders Equity
            r"equity",
            r"retained earnings",
            r"conversion of units",
            ])
    # standard label tests, indicate two-way label
    val.twoWayPriItemStdLabelPattern = compile([
            # from Eric Cohen
            r"appreciation depreciation",
            r"asset liability",
            r"assets acquired liabilities assumed",
            r"benefit expense",
            r"expense benefit",
            r"cost credit",
            r"costs credits",
            r"deductions charges",
            r"discount premium",
            r"due from to",
            r"earnings losses",
            r"earnings deficit",
            r"excess shortage",
            r"gains losses",
            r"impairment recovery",
            r"income loss",
            r"liability refund",
            r"loss recovery",
            r"obligation asset",
            r"obligations assets",
            r"proceeds from repayments of",
            r"proceeds from repurchase of",
            r"provided by used in",
            r"provisions recoveries",
            r"retained earnings accumulated deficit",
            r"\w+ per \w+",
            ])
    # determination of a one-way concept based on standard label
    val.oneWayPriItemStdLabelPattern = compile([
            r"payments of (\w+ )*(dividends|capital)",
            r"(stocks|shares) (\w+ )*issued",
            r"stock (\w+ )*repurchase(d)?",
            r"treasury stock (\w+ )*(beginning|ending|acquired|reissued|retired)",
            r"accumulated depreciation (\w+ )*amortization",
            r"accumulated other-than-temporary impairments",
            r"allowance (\w+ )*doubtful accounts",
            r"amortization (\w+ )*pension costs",
            r"available for sale securities (\w+ )*continuous loss position",
            r"available for sale securities gross unrealized losses",
            ])
    # determination of a two way fact based on any of fact's dimension member label
    val.twoWayMemberStdLabelPattern = compile([
            # per Eric Cohen
            r"(^|\s)change (in|during) \w+", # don't match word with change in it like exchange
            r"\w+ elimination \w+",
            r"adjustment",
            r"adjustments for \w+",
            r"effect\s",
            r"gain loss \w+",
            r"gains losses \w+",
            r"income loss \w+",
            r"(^|\s)net(ting)?",  # don't want to match word with net in it like internet
            ])

def factCheck(val, fact):
    concept = fact.concept
    context = fact.context
    stdLabel = concept.label(lang="en-US", fallbackToQname=False)
    defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
    
    try:
        if fact.isNumeric and not fact.isNil and fact.xValue is not None and fact.xValue < 0 and (
            (not ((defLabel is not None and val.twoWayPriItemDefLabelPattern.search(defLabel)) or
                  (defLabel is None and stdLabel is not None and val.twoWayPriItemDefLabelPattern.search(stdLabel) or
                  (stdLabel is not None and val.twoWayPriItemStdLabelPattern.search(stdLabel))) or
                   context is not None and (
                      any((val.twoWayMemberStdLabelPattern.search(dim.member.label(lang="en-US", fallbackToQname=False))
                          )
                          for dim in context.qnameDims.values()
                          if dim.isExplicit)
                                           )
                  )) or
            ((stdLabel is not None and val.oneWayPriItemStdLabelPattern.search(stdLabel)))
                ):
                val.modelXbrl.warning("secStaffObservation.nonNegativeFact",
                    _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s should be nonnegative"),
                    modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
                    value=fact.effectiveValue)
    except Exception as ex:
        val.modelXbrl.warning("arelle:nonNegFactTestException",
            _("%(fact)s in context %(contextID)s unit %(unitID)s value %(value)s cannot be tested nonnegative"),
            modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID,
            value=fact.effectiveValue)

def final(val):
    del val.twoWayPriItemDefLabelPattern
    del val.twoWayPriItemStdLabelPattern
    del val.oneWayPriItemStdLabelPattern
    del val.twoWayMemberStdLabelPattern
    
def saveDtsMatches(dts, secDtsTagMatchesFile):
    setup(dts)
    
    priItemsTwoWay = []
    priItemsOneWay = []
    membersTwoWay = []
    
    for qname, concept in sorted(dts.qnameConcepts.items(), key=lambda item: item[0]):
        if concept.isItem and concept.isPrimaryItem: # both pri item and domain members
            stdLabel = concept.label(lang="en-US", fallbackToQname=False)
            defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
            if concept.type is not None and concept.type.isDomainItemType:
                if stdLabel is not None and dts.twoWayMemberStdLabelPattern.search(stdLabel):
                    membersTwoWay.append(str(qname))
            else: # not dimension domain/member
                if ((defLabel is not None and dts.twoWayPriItemDefLabelPattern.search(defLabel)) or
                    (defLabel is not None and stdLabel is not None and dts.twoWayPriItemDefLabelPattern.search(stdLabel)) or
                    (stdLabel is not None and dts.twoWayPriItemStdLabelPattern.search(stdLabel))):
                    priItemsTwoWay.append(str(qname))
                elif (stdLabel is not None and dts.oneWayPriItemStdLabelPattern.search(stdLabel)):
                    priItemsOneWay.append(str(qname))
    
    with open(secDtsTagMatchesFile, "w", encoding='utf-8') as fh:
        fh.write('DTS Primary Item Two-way Matches\n\n')
        fh.write('\n'.join(priItemsTwoWay))
        fh.write('\n\nDTS Primary Item One-way Matches\n\n')
        fh.write('\n'.join(priItemsOneWay))
        fh.write('\n\nDTS Dimension Member Two-way Matches\n\n')
        fh.write('\n'.join(membersTwoWay))
        fh.write('\n') # ending newline for file

    dts.info("info:saveSecDtsTagMatches",
             _("SecDtsTagMatches entry %(entryFile)s has %(numberOfTwoWayPriItems)s two way primary items, %(numberOfOneWayPriItems)s one way primary items, %(numberOfTwoWayMembers)s two way members in output file %(secDtsTagMatchesFile)s."),
             modelObject=dts,
             entryFile=dts.uri, 
             numberOfTwoWayPriItems=len(priItemsTwoWay), 
             numberOfOneWayPriItems=len(priItemsOneWay), 
             numberOfTwoWayMembers=len(membersTwoWay),
             secDtsTagMatchesFile=secDtsTagMatchesFile)

    final(dts)

def saveDtsMatchesMenuEntender(cntlr, menu):
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
            title=_("Save SEC DTS tag matches text file"),
            filetypes=[(_("DTS tag matches .txt file"), "*.txt")],
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

def saveDtsMatchesCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-sec-tag-dts-matches", 
                      action="store", 
                      dest="secDtsTagMatchesFile", 
                      help=_("Save SEC DTS tag matches text file."))

def saveDtsMatchesCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    if options.secDtsTagMatchesFile:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        saveDtsMatches(cntlr.modelManager.modelXbrl, options.secDtsTagMatchesFile)

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate SEC Tagging',
    'version': '0.9',
    'description': '''SEC Tagging Validation.  Includes non-negative rules.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final,
    'CntlrWinMain.Menu.Tools': saveDtsMatchesMenuEntender,
    'CntlrCmdLine.Options': saveDtsMatchesCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveDtsMatchesCommandLineXbrlRun,
}
