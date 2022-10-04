from arelle import PluginManager
from arelle.ModelValue import qname
from arelle.Version import copyrightLabel


def setup(val):
    if 'http://fasb.org/us-gaap/2011-01-31' in val.modelXbrl.namespaceDocs:
        nsTbl = {None: 'http://fasb.org/us-gaap/2011-01-31',
                 'country' : 'http://xbrl.sec.gov/country/2011-01-31',
                 'currency': 'http://xbrl.sec.gov/currency/2011-01-31',
                 'dei': 'http://xbrl.sec.gov/dei/2011-01-31',
                 'exch': 'http://xbrl.sec.gov/exch/2011-01-31',
                 'invest': 'http://xbrl.sec.gov/invest/2011-01-31',
                 'naics': 'http://xbrl.sec.gov/naics/2011-01-31',
                 'sic': 'http://xbrl.sec.gov/sic/2011-01-31',
                 'stpr': 'http://xbrl.sec.gov/stpr/2011-01-31',
                 'us-types': 'http://fasb.org/us-types/2011-01-31',
                 'nonnum': 'http://www.xbrl.org/dtr/type/non-numeric',
                 'num': 'http://www.xbrl.org/dtr/type/numeric'}
    elif 'http://xbrl.us/us-gaap/2009-01-31' in val.modelXbrl.namespaceDocs:
        nsTbl = {None: 'http://xbrl.us/us-gaap/2009-01-31',
                 'ar': 'http://xbrl.us/ar/2009-01-31',
                 'country': 'http://xbrl.us/country/2009-01-31',
                 'currency': 'http://xbrl.us/currency/2009-01-31',
                 'exch': 'http://xbrl.us/exch/2009-01-31',
                 'invest': 'http://xbrl.us/invest/2009-01-31',
                 'mda': 'http://xbrl.us/mda/2009-01-31',
                 'mr': 'http://xbrl.us/mr/2009-01-31',
                 'naics': 'http://xbrl.us/naics/2009-01-31',
                 'seccert': 'http://xbrl.us/seccert/2009-01-31',
                 'sec': 'http://xbrl.us/sic/2009-01-31',
                 'stpr': 'http://xbrl.us/stpr/2009-01-31',
                 'dei': 'http://xbrl.us/dei/2009-01-31',
                 'us-types': 'http://xbrl.us/us-types/2009-01-31'}
        
    def q(n): return qname(n, nsTbl) 
    
    ''' matching table
        localName: ( inclusion(dim, mbr), exclusion(dim,mbr), ruleFunction, error code, err descr )
    '''
    def isNegative(f): return f.xValue < 0 
    val.usgaapRules = {        
        q("PaymentsToAcquireNotesReceivable"): 
            ( None, None, isNegative, "xbrlus-cc.cf.nonneg.4291", "may not be nonnegative" ),
        q("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"):
            ( ((q("StatementEquityComponentsAxis"),q("PreferredStockMember")),
               ), 
              None, isNegative, "xbrlus-cc.she.nonneg.2", "may not be nonnegative"),
        q("FairValueAssetsMeasuredOnRecurringBasisLoansReceivable"):
            ( None,
              ((q("dei:LegalEntityAxis"),q("ConsolidationEliminationsMember")),
               (q("StatementBusinessSegmentsAxis"),q("ConsolidationEliminationsMember")),
               (q("StatementBusinessSegmentsAxis"),q("BusinessIntersegmentEliminationsMember")),
               (q("SegmentReportingInformationBySegmentAxis"),q("BusinessIntersegmentEliminationsMember")),
               (q("StatementGeographicalAxis"),q("GeographicalIntersegmentEliminationsMember")),
               (q("ErrorCorrectionsAndPriorPeriodAdjustmentsRestatementByRestatementPeriodAndAmountAxis"),q("RestatementAdjustmentMember")),
               (q("NewAccountingPronouncementsOrChangeInAccountingPrincipleByTypeOfChangeAxis"),q("RestatementAdjustmentMember")),
               (q("StatementScenarioAxis"),q("ScenarioAdjustmentMember")),
               (q("EffectOfFourthQuarterEventsByTypeAxis"),q("YearEndAdjustmentMember")),
               ), 
              isNegative, "xbrlus-cc.fv.nonneg.9329", "may not be nonnegative")
        }

def factCheck(val, fact):
    if fact.qname in val.usgaapRules:
        inclDimMems, exclDimMems, ruleFunction, errCode, descr = val.usgaapRules[fact.qname]
        if (all(fact.context.dimMemberQname(dimMem[0]) == dimMem[1])
                for dimMem in (inclDimMems or []) and
            not any(fact.context.dimMemberQname(dimMem[0]) == dimMem[1])
                for dimMem in (exclDimMems or []) and
            ruleFunction(fact)):
            val.modelXbrl.error(errCode,
                _("%(fact)s in context %(contextID)s %(descr)s"),
                modelObject=fact, fact=fact.qname, contextID=fact.contextID, descr=descr)

def final(val):
    pass

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'US-GAAP Consistency Tests',
    'version': '0.9',
    'description': '''US-GAAP consistency tests.  Includes non-negative rules.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Validate.EFM.Start': setup,
    'Validate.EFM.Fact': factCheck,
    'Validate.EFM.Finally': final
}
