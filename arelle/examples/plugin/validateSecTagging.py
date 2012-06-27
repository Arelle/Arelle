from arelle import PluginManager
from arelle.ModelValue import qname
from arelle import XbrlConst
import re

def setup(val):
    val.twoWayPriItemDefLabelPattern = re.compile(
            # from http://www.sec.gov/spotlight/xbrl/staff-review-observations-061511.shtml 
            # Cash Flow
            r"Increase\s+decrease|"
            r"Provided\s+by\s+used\s+in|"
            r"Net|"
            r"Change\s+in|"
            r"Proceeds\s+from\s+payments\s+for|"
            r"Proceeds\s+from\s+payments\s+to|"
            # Income statement
            r"Gain\s+Loss|"
            r"Profit\s+Loss|"
            r"Income\s+expense|"
            r"Per\s+share|"
            # Statement of Stockholders Equity
            r"Equity|"
            r"Retained\s+Earnings")
    val.twoWayPriItemStdLabelPattern = re.compile(
            # from Eric Cohen
            r"Appreciation\s+\(Depreciation\)|"
            r"Asset\s+\(Liability\)|"
            r"Assets\s+Acquired\s+\(Liabilities\s+Assumed\)|"
            r"Benefit\s+\(Expense\)|"
            r"Expense\s+\(Benefit\)|"
            r"Cost\s+\(Credit\)|"
            r"Costs\s+\(Credits\)|"
            r"Deductions\s+\(Charges\)|"
            r"Discount\s+\(Premium\)|"
            r"Due from\s+\(to\)|"
            r"Earnings\s+\(Losses\)|"
            r"Earnings\s+\(Deficit\)|"
            r"Excess\s+\(Shortage\)|"
            r"Gains\s+\(Losses\)|"
            r"Impairment\s+\(Recovery\)|"
            r"Income\s+\(Loss\)|"
            r"Liability\s+\(Refund\)|"
            r"Loss\s+\(Recovery\)|"
            r"Obligation\s+\(Asset\)|"
            r"Obligations\s+\(Assets\)|"
            r"Proceeds\s+from\s+\(Repayments\s+of\)|"
            r"Proceeds\s+from\s+\(Repurchase\s+of\)|"
            r"Provided\s+by\s+\(Used\s+in\)|"
            r"Provisions\s+\(Recoveries\)|"
            r"Retained\s+Earnings\s+\(Accumulated\s+Deficit\)|"
            r"per\s+\w+")
    val.twoWayMemberStdLabelPattern = re.compile(
            # per Eric Cohen
            r"Change\s+in\s+\w+|"
            r"\w+\s+Elimination\s+\w+|"
            r"Adjustment\(s\)\s+for\s+\w+|"
            r"Cumulative-Effect\s+Adjustment\s+\w+|"
            r"Effect\s+of\s+Illegal\s+Acts\s+in\s+\w+|"
            r"Gain\s+\(Loss\)\s+\w+|"
            r"Gains\s+\(Losses\)\s+\w+|"
            r"Income\s+\(Loss\)\s+\w+|"
            r"Netting")
    val.twoWayMbrQnamePattern = re.compile(
            # per Eric Cohen
            r"us-gaap:AccumulatedDefinedBenefitPlansAdjustmentMember|"
            r"us-gaap:AccumulatedTranslationAdjustmentMember|"
            r"us-gaap:AdjustmentsForNewAccountingPrincipleEarlyAdoptionMember|"
            r"us-gaap:CumulativeEffectAdjustmentConsolidationOfVariableInterestEntityMember|"
            r"us-gaap:CumulativeEffectAdjustmentDeconsolidationOfVariableInterestEntityMember|"
            r"us-gaap:FairValueAdjustmentToInventoryMember|"
            r"us-gaap:FairValueAdjustmentsOnHedgesAndDerivativeContractsMember|"
            r"us-gaap:LeasesAcquiredInPlaceMarketAdjustmentMember|"
            r"us-gaap:MaterialEffectOnLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseFromChangeInAccountingPrincipleMember|"
            r"us-gaap:MaterialErrorInLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseMember|"
            r"us-gaap:MinorRestatementOfOpeningLiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseSAB108Member|"
            r"us-gaap:PurchasePriceAllocationAdjustmentsMember|"
            r"us-gaap:RestatementAdjustmentMember|"
            r"us-gaap:ScenarioAdjustmentMember|"
            r"us-gaap:YearEndAdjustmentMember")

def factCheck(val, fact):
    qname = str(fact.qname)
    concept = fact.concept
    context = fact.context
    stdLabel = concept.label(lang="en", fallbackToQname=False)
    defLabel = concept.label(preferredLabel=XbrlConst.documentationLabel, lang="en", fallbackToQname=False)
    
    if not ((defLabel and val.twoWayPriItemDefLabelPattern.search(defLabel)) or
            (stdLabel and val.twoWayPriItemStdLabelPattern.search(stdLabel)) or
            context is not None and (
                # only check non-default members (for now)
                any((val.twoWayPriItemStdLabelPattern.search(dim.member.label(lang="en", fallbackToQname=False)) or
                     val.twoWayMbrQnamePattern.match(str(dim.memberQname)))
                    for dim in context.qnameDims.values()
                    if dim.isExplicit)
                         )
            ) and fact.isNumeric and fact.xValue < 0:
            val.modelXbrl.warning("arelle.nonNegativeFact",
                _("%(fact)s in context %(contextID)s should be nonnegative"),
                modelObject=fact, fact=fact.qname, contextID=fact.contextID)

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
