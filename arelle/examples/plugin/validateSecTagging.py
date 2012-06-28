from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import XbrlConst
import re

def setup(val):
    val.twoWayPriItemDefLabelPattern = re.compile('|'.join([
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml 
            # Cash Flow
            r"Increase decrease",
            r"Provided by used in",
            r"Net",
            r"Change in",
            r"Proceeds from payments for",
            r"Proceeds from payments to",
            # Income statement
            r"Gain Loss",
            r"Profit Loss",
            r"Income expense",
            r"Per share",
            # Statement of Stockholders Equity
            r"Equity",
            r"Retained Earnings",
            ]).replace(r" ",r"\W+"))
    val.twoWayPriItemStdLabelPattern = re.compile('|'.join([
            # from Eric Cohen
            r"Appreciation Depreciation",
            r"Asset Liability",
            r"Assets Acquired Liabilities Assumed",
            r"Benefit Expense",
            r"Expense Benefit",
            r"Cost Credit",
            r"Costs Credits",
            r"Deductions Charges",
            r"Discount Premium",
            r"Due from to",
            r"Earnings Losses",
            r"Earnings Deficit",
            r"Excess Shortage",
            r"Gains Losses",
            r"Impairment Recovery",
            r"Income Loss",
            r"Liability Refund",
            r"Loss Recovery",
            r"Obligation Asset",
            r"Obligations Assets",
            r"Proceeds from Repayments of",
            r"Proceeds from Repurchase of",
            r"Provided by Used in",
            r"Provisions Recoveries",
            r"Retained Earnings Accumulated Deficit",
            r"\w+ per \w+",
            ]).replace(r" ",r"\W+"))
    val.twoWayMemberStdLabelPattern = re.compile('|'.join([
            # per Eric Cohen
            r"Change in \w+",
            r"\w+ Elimination \w+",
            r"Adjustments for \w+",
            r"Cumulative-Effect Adjustment \w+",
            r"Effect of Illegal Acts in \w+",
            r"Gain Loss \w+",
            r"Gains Losses \w+",
            r"Income Loss \w+",
            r"Netting",
            r"Adjustment", # added when removing below val.twoWayMbrQnamePattern per EC 2012-06-28 
            ]).replace(r" ",r"\W+"))
    ''' believe below was mis-understanding per ED 2012-06-28
    val.twoWayMbrQnamePattern = re.compile('|'.join([
            # per Eric Cohen
            r"us-gaap:AccumulatedDefinedBenefitPlansAdjustmentMember",
            r"us-gaap:AccumulatedTranslationAdjustmentMember",
            r"us-gaap:AdjustmentsForNewAccountingPrincipleEarlyAdoptionMember",
            r"us-gaap:CumulativeEffectAdjustmentConsolidationOfVariableInterestEntityMember",
            r"us-gaap:CumulativeEffectAdjustmentDeconsolidationOfVariableInterestEntityMember",
            r"us-gaap:FairValueAdjustmentToInventoryMember",
            r"us-gaap:FairValueAdjustmentsOnHedgesAndDerivativeContractsMember",
            r"us-gaap:LeasesAcquiredInPlaceMarketAdjustmentMember",
            r"us-gaap:MaterialEffectOnLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseFromChangeInAccountingPrincipleMember",
            r"us-gaap:MaterialErrorInLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseMember",
            r"us-gaap:MinorRestatementOfOpeningLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseSAB108Member",
            r"us-gaap:PurchasePriceAllocationAdjustmentsMember",
            r"us-gaap:RestatementAdjustmentMember",
            r"us-gaap:ScenarioAdjustmentMember",
            r"us-gaap:YearEndAdjustmentMember",
            ]).replace(r" ",r"\W+"))
    '''

def factCheck(val, fact):
    qname = str(fact.qname)
    concept = fact.concept
    context = fact.context
    stdLabel = concept.label(lang="en", fallbackToQname=False)
    defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en-US", fallbackToQname=False)
    
    if not ((defLabel is not None and val.twoWayPriItemDefLabelPattern.search(defLabel, re.IGNORECASE)) or
            (stdLabel is not None and val.twoWayPriItemStdLabelPattern.search(stdLabel, re.IGNORECASE)) or
            context is not None and (
                # only check non-default members (for now)
                any((val.twoWayPriItemStdLabelPattern.search(dim.member.label(lang="en-US", fallbackToQname=False), re.IGNORECASE)
                     # remove per EC 2012-06-28: or val.twoWayMbrQnamePattern.match(str(dim.memberQname))
                     )
                    for dim in context.qnameDims.values()
                    if dim.isExplicit)
                         )
            ) and fact.isNumeric and fact.xValue < 0:
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
