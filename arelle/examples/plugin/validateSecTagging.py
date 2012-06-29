from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import XbrlConst
import re

def setup(val):
    val.twoWayPriItemDefLabelPattern = re.compile('|'.join([
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml 
            # Cash Flow
            r"increase decrease",
            r"provided by used in",
            r"net",
            r"change in",
            r"proceeds from payments (for|to)",
            # Income statement
            r"(gain|profit) loss",
            r"income (expense|loss)",
            r"per share",
            # Statement of Stockholders Equity
            r"equity",
            r"retained earnings",
            r"conversion of units",
            ]).replace(r" ",r"\W+"))
    val.possibleTwoWayPriItemDefLabelPattern = re.compile('|'.join([
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml 
            # Cash Flow
            r"increase (\w+ )+decrease",
            r"provided by (\w+ )+used in",
            r"proceeds from (\w+ )+payments (for|to)",
            ]).replace(r" ",r"\W+"))
    val.twoWayPriItemStdLabelPattern = re.compile('|'.join([
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
            ]).replace(r" ",r"\W+"))
    val.oneWayPriItemStdLabelPattern = re.compile('|'.join([
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
            ]).replace(r" ",r"\W+"))
    val.twoWayMemberStdLabelPattern = re.compile('|'.join([
            # per Eric Cohen
            r"change (in|during) \w+",
            r"\w+ elimination \w+",
            r"adjustment",
            r"adjustments for \w+",
            r"effect\s",
            r"gain loss \w+",
            r"gains losses \w+",
            r"income loss \w+",
            r"net(ting)?",
            ]).replace(r" ",r"\W+"))

def factCheck(val, fact):
    qname = str(fact.qname)
    concept = fact.concept
    context = fact.context
    stdLabel = concept.label(lang="en", fallbackToQname=False)
    defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
    
    if fact.isNumeric and fact.xValue < 0 and (
        (not ((defLabel is not None and val.twoWayPriItemDefLabelPattern.search(defLabel, re.IGNORECASE)) or
              (stdLabel is not None and val.twoWayPriItemStdLabelPattern.search(stdLabel, re.IGNORECASE)) or
               context is not None and (
                  any((val.twoWayPriItemStdLabelPattern.search(dim.member.label(lang="en-US", fallbackToQname=False), re.IGNORECASE)
                     # remove per EC 2012-06-28: or val.twoWayMbrQnamePattern.match(str(dim.memberQname))
                      )
                      for dim in context.qnameDims.values()
                      if dim.isExplicit)
                                       )
              )) or
        ((stdLabel is not None and val.oneWayPriItemStdLabelPattern.search(stdLabel, re.IGNORECASE)))
            ):
            val.modelXbrl.warning("secStaffObservation.nonNegativeFact",
                _("%(fact)s in context %(contextID)s unit %(unitID)s should be nonnegative"),
                modelObject=fact, fact=fact.qname, contextID=fact.contextID, unitID=fact.unitID)

def final(val):
    pass

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
    'Validate.EFM.Finally': final
}
