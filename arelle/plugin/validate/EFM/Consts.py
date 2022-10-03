'''
See COPYRIGHT.md for copyright information.
'''
import regex as re
from arelle.PythonUtil import attrdict

#qnFasbExtensibleListItemTypes = (qname("{http://fasb.org/us-types/2017-01-31}us-types:extensibleListItemType"),
#                                 qname("{http://fasb.org/srt-types/2018-01-31}srt-types:extensibleListItemType"))

""" removed per PCR22280 5/16/18
ifrsSrtConcepts = { # concepts of ifrs items or axes which have a corresponding srt element
    "CounterpartiesAxis": "CounterpartyNameAxis",
    "MajorCustomersAxis": "MajorCustomersAxis",
    "ProductsAndServicesAxis": "ProductOrServiceAxis",
    "RangeAxis": "RangeAxis"
    }
srtAxisIfrsMembers = { # members of IFRS axes which have SRT corresponding member elements
    "CounterpartyNameAxis": {"CounterpartiesMember", "IndividuallyInsignificantCounterpartiesMember"},
    "MajorCustomersAxis": {"MajorCustomersMember", "GovernmentMember"},
    "ProductOrServiceAxis": {"ProductsAndServicesMember"},
    "RangeAxis": {"RangesMember", "BottomOfRangeMember", "WeightedAverageMember", "TopOfRangeMember"}    }
"""

# doc type requirements are for EFM 6.5.20 and are in some cases a superset of what the submission allows.
docTypes8K = {"8-K", "8-K/A", "8-K12B", "8-K12B/A", "8-K12G3", "8-K12G3/A", "8-K15D5", "8-K15D5/A"}
docTypes1012B = {"10-12B", "10-12B/A"}
docTypes1012G = {"10-12G", "10-12G/A"}
docTypes10K = {"10-K", "10-K/A"}
docTypes10KT = {"10-KT", "10-KT/A"}
docTypes10K10KT = docTypes10K | docTypes10KT
docTypes10Q = {"10-Q", "10-Q/A"}
docTypes10QT = {"10-QT", "10-QT/A"}
docTypes10Q10QT = docTypes10Q | docTypes10QT
docTypes10all = docTypes10K10KT | docTypes10Q10QT
docTypes20F = {"20-F", "20-F/A"}
docTypes40F = {"40-F", "40-F/A"}
docTypes20F40F = docTypes20F | docTypes40F
docTypes20FR = {"20FR12B", "20FR12B/A", "20FR12G", "20FR12G/A"}
docTypes40FR = {"40FR12B", "40FR12B/A", "40FR12G", "40FR12G/A"}
docTypes20FR40FR = docTypes20FR | docTypes40FR
docTypes10all20all = docTypes10all | docTypes20F | docTypes20FR
docTypesCoverTagged = docTypes8K | docTypes1012B | docTypes1012G | docTypes10all | docTypes20F40F | docTypes20FR40FR
docTypesSDR = {"K SDR", "L SDR"}
docTypesRR = {"497", "485APOS", "485BPOS", "485BXT", "N-1A", "N-1A/A"}

submissionTypesNotRequiringPeriodEndDate = docTypes8K | {
                                            "F-1", "F-1/A", "F-3", "F-3/A", "F-4", "F-4/A", "F-10", "F-10/A",
                                            "S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A",
                                            "20-F"}


submissionTypesAllowingPeriodOfReport = docTypes8K | docTypes10all | docTypes20F40F | {
    "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A", "N-Q", "6-K", "6-K/A", "N-Q/A", "SP 15D2", "SP 15D2/A"}
submissionTypesAllowingWellKnownSeasonedIssuer = \
submissionTypesAllowingShellCompanyFlag = \
submissionTypesAllowingVoluntaryFilerFlag = \
submissionTypesAllowingAcceleratedFilerStatus = docTypes10K10KT | docTypes20F
submissionTypesAllowingEntityInvCompanyType = docTypesRR | {
    'N-CSR', 'N-CSR/A', 'N-CSRS', 'N-CSRS/A', 'N-Q', 'N-Q/A'}
submissionTypesAllowingSeriesClasses = docTypesRR | {
    "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A", 'N-Q', 'N-Q/A'}
invCompanyTypesAllowingSeriesClasses = {"N-1A", "N-3"}

docTypesRequiringPeriodOfReport = {"10", "10-K", "10-Q", "20-F", "40-F", "6-K", "8-K",
    "F-1", "F-10", "F-3", "F-4", "F-9", "S-1", "S-11", "S-3", "S-4", "POS AM", "10-KT", "10-QT", "POS EX",
    "10/A", "10-K/A", "10-Q/A", "20-F/A", "40-F/A", "6-K/A", "8-K/A", "F-1/A", "F-10/A", "F-3/A", "F-4/A",
    "F-9/A", "S-1/A", "S-11/A", "S-3/A", "S-4/A", "10-KT/A", "10-QT/A", "485APOS", "485BPOS", "485BXT", "497",
    "N-CSR", "N-CSRS", "N-Q", "N-CSR/A", "N-CSRS/A", "N-Q/A", "K SDR", "L SDR" }
docTypesRequiringEntityWellKnownSeasonedIssuer = docTypes10K10KT | docTypes20F | docTypes20FR
docTypesRequiringEntityFilerCategory = docTypesCoverTagged - docTypes40F - docTypes40FR | {
    "S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A", "S-11MEF", "S-1MEF", "S-3D", "S-3DPOS", "S-3MEF", "S-4 POS", "S-4EF", "S-4MEF", "POS AM", "S-3ASR"}
submissionTypesAllowingEdgarSmallBusinessFlag = docTypes10all | {
    "S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A", "S-11MEF", "S-1MEF", "S-3D", "S-3DPOS", "S-3MEF", "S-4 POS", "S-4EF", "S-4MEF"}
submissionTypesAllowingEmergingGrowthCompanyFlag = \
submissionTypesAllowingExTransitionPeriodFlag = docTypesCoverTagged | {
    "F-1", "F-1/A", "F-3", "F-3/A", "F-4", "F-4/A",
    "S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A"}

docTypesRequiringRrSchema = \
docTypesExemptFromRoleOrder = \
submissionTypesExemptFromRoleOrder = ('485APOS', '485BPOS','485BXT', '497', 'N-1A', 'N-1A/A',
                                      'N-2', 'N-2/A', 'N-2MEF', 'N-2ASR', 'N-2 POSASR')

docTypesNotAllowingIfrs = ('485APOS', '485BPOS','485BXT', '497', 'N-1A', 'N-1A/A',
                           'N-CSR', 'N-CSR/A', 'N-CSRS', 'N-CSRS/A', 'N-Q', 'N-Q/A',
                           'K SDR', 'L SDR')

docTypesNotAllowingInlineXBRL = {
    "K SDR", "L SDR"}

standardNamespacesPattern = re.compile(
    # non-IFRS groups 1 - authority, 2 - taxonomy (e.g. us-gaap, us-types), 3 - year
    r"http://(xbrl\.us|fasb\.org|xbrl\.sec\.gov)/("
            r"dei|us-gaap|srt|us-types|us-roles|srt-types|srt-roles|rr|cef|country|currency|exch|invest|naics|sic|stpr|vip"
            r")/([0-9]{4}|[0-9]{4}q[1-4])(-[0-9]{2}-[0-9]{2})?$"
    # ifrs groups 4 - year, 5 - taxonomy (e.g. ifrs-full)
    r"|https?://xbrl.ifrs.org/taxonomy/([0-9]{4})-[0-9]{2}-[0-9]{2}/(ifrs[\w-]*)$")

# hidden references
untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                        "token", "language"}

# hideable namespaceURIs
hideableNamespacesPattern = re.compile("http://xbrl.sec.gov/(dei|vip)/")

# RR untransformable facts
rrUntransformableEltsPattern = re.compile(r"(\w*TableTextBlock|BarChart\w+|AnnualReturn(19|20)[0-9][0-9])")

usDeprecatedLabelPattern = re.compile(r"^.* \(Deprecated (....(-..-..)?)\)$")
usDeprecatedLabelRole = "http://www.xbrl.org/2003/role/label"
ifrsDeprecatedLabelPattern = re.compile(r"^\s*([0-9]{4}-[0-1][0-9]-[0-2][0-9])\s*$")
ifrsDeprecatedLabelRole = "http://www.xbrl.org/2009/role/deprecatedDateLabel"

latestTaxonomyDocs = { # note that these URLs are blocked by EFM validation modes
    # deprecatedLabels may be a single file name or list of file names
    # US FASB/SEC taxonomies
    "country/*": {
        "deprecatedLabels": ["http://xbrl.sec.gov/country/2016/country-lab-2016-01-31.xml",
                             "http://xbrl.sec.gov/country/2017/country-lab-2017-01-31.xml",
                             "https://xbrl.sec.gov/country/2020/country-lab-2020-01-31.xml",
                             "https://xbrl.sec.gov/country/2021/country-entire-2021.xsd",
                             "https://xbrl.sec.gov/country/2022/country-entire-2022.xsd"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "currency/*": {
        "deprecatedLabels": ["https://xbrl.sec.gov/currency/2017/currency-lab-2017-01-31.xml",
                             "https://xbrl.sec.gov/currency/2019/currency-lab-2019-01-31.xml",
                             "https://xbrl.sec.gov/currency/2020/currency-lab-2020-01-31.xml",
                             "https://xbrl.sec.gov/currency/2021/currency-entire-2021.xsd",
                             "https://xbrl.sec.gov/currency/2022/currency-entire-2022.xsd"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "dei/*": {
        "deprecatedLabels": ["http://xbrl.sec.gov/dei/2012/dei-lab-2012-01-31.xml",
                             "https://xbrl.sec.gov/dei/2018/dei-lab-2018-01-31.xml",
                             "https://xbrl.sec.gov/dei/2019/dei-lab-2019-01-31.xml",
                             "https://xbrl.sec.gov/dei/2021/dei-2021_lab.xsd",
                             "https://xbrl.sec.gov/dei/2022/dei-2022_lab.xsd"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "exch/*": {
        "deprecatedLabels": ["https://xbrl.sec.gov/exch/2018/exch-lab-2018-01-31.xml",
                             "https://xbrl.sec.gov/exch/2019/exch-lab-2019-01-31.xml",
                             "https://xbrl.sec.gov/exch/2020/exch-lab-2020-01-31.xml",
                             "https://xbrl.sec.gov/exch/2021/exch-entire-2021.xsd",
                             "https://xbrl.sec.gov/exch/2022/exch-entire-2022.xsd"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "invest/*": {
        # do not rebuild, all labels are deprecated
        "deprecatedLabels": "https://xbrl.sec.gov/invest/2013/invest-lab-2013-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "rr/*": {
        "deprecatedLabels": ["http://xbrl.sec.gov/rr/2012/rr-lab-2012-01-31.xml",
                             "https://xbrl.sec.gov/rr/2018/rr-lab-2018-01-31.xml",
                             "https://xbrl.sec.gov/rr/2021/rr-2021_lab.xsd",
                             "https://xbrl.sec.gov/rr/2022/rr-2022_lab.xsd"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "srt/*": {
        "deprecatedLabels": ["http://xbrl.fasb.org/srt/2018/elts/srt-lab-2018-01-31.xml",
                             "http://xbrl.fasb.org/srt/2019/elts/srt-lab-2019-01-31.xml",
                             "http://xbrl.fasb.org/srt/2020/elts/srt-lab-2020-01-31.xml",
                             "https://xbrl.fasb.org/srt/2021/elts/srt-lab-2021-01-31.xml",
                             "https://xbrl.fasb.org/srt/2022/elts/srt-lab-2022.xml"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "stpr/*": {
        "deprecatedLabels": "https://xbrl.sec.gov/stpr/2018/stpr-lab-2018-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "us-gaap/*": {
        "deprecatedLabels": ["http://xbrl.fasb.org/us-gaap/2018/elts/us-gaap-lab-2018-01-31.xml",
                             "http://xbrl.fasb.org/us-gaap/2019/elts/us-gaap-lab-2019-01-31.xml",
                             "http://xbrl.fasb.org/us-gaap/2020/elts/us-gaap-lab-2020-01-31.xml",
                             "https://xbrl.fasb.org/us-gaap/2021/elts/us-gaap-lab-2021-01-31.xml",
                             "https://xbrl.fasb.org/us-gaap/2022/elts/us-gaap-lab-2022.xml"],
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern,
        "dqcRuleArcrole": "http://fasb.org/dqcRules/arcrole/concept-rule",
        },
    # International taxonomies
    "ifrs-full/*": {
        "deprecatedLabels": ["http://xbrl.ifrs.org/taxonomy/2018-03-16/deprecated/depr-lab_full_ifrs-en_2018-03-16.xml",
                             "http://xbrl.ifrs.org/taxonomy/2019-03-27/deprecated/depr-lab_full_ifrs-en_2019-03-27.xml",
                             "http://xbrl.ifrs.org/taxonomy/2020-03-16/deprecated/depr-lab_full_ifrs-en_2020-03-16.xml",
                             "http://xbrl.ifrs.org/taxonomy/2021-03-24/deprecated/depr-lab_full_ifrs-en_2021-03-24.xml"],
        "deprecatedLabelRole": ifrsDeprecatedLabelRole,
        "deprecationDatePattern": ifrsDeprecatedLabelPattern
        }
    }
''' Moved to Ugt resource files
latestDqcrtDocs = {
    "us-gaap/2020": "http://xbrl.fasb.org/us-gaap/2020/dqcrules/dqcrules-2020-01-31.xsd",
    "us-gaap/2021": "http://xbrl.fasb.org/us-gaap/2021/dqcrules/dqcrules-2021-01-31.xsd"
    }
'''
latestEntireUgt = {
    "us-gaap/2019": ["http://xbrl.fasb.org/us-gaap/2019/entire/us-gaap-entryPoint-std-2019-01-31.xsd", None],
    "us-gaap/2020": ["http://xbrl.fasb.org/us-gaap/2020/entire/us-gaap-entryPoint-std-2020-01-31.xsd",
                     # use 2021 DQCRT for 2020 us-gaap checks
                     "http://xbrl.fasb.org/us-gaap/2021/dqcrules/dqcrules-2021-01-31.xsd"],
    "us-gaap/2021": ["http://xbrl.fasb.org/us-gaap/2021/entire/us-gaap-entryPoint-std-2021-01-31.xsd",
                     # "http://xbrl.fasb.org/us-gaap/2021/dqcrules/dqcrules-2021-01-31.xsd"
                     "https://xbrl.fasb.org/us-gaap/2022/dqcrules/dqcrules-entire-2022.xsd"],
    "us-gaap/2022": ["https://xbrl.fasb.org/us-gaap/2022/entire/us-gaap-entryPoint-std-2022.xsd",
                     "https://xbrl.fasb.org/us-gaap/2022/dqcrules/dqcrules-entire-2022.xsd"]
    }

linkbaseValidations = {
    "cef": attrdict(
        efmPre = "6.12.10",
        efmCal = "6.14.06",
        efmDef = "6.16.10",
        elrPre = re.compile("http://xbrl.sec.gov/cef/role/N2"),
        elrDefInNs = re.compile("http://xbrl.sec.gov/cef/role/N2"),
        elrDefExNs = re.compile("http://xbrl.sec.gov/cef/role/(Security|Risk)Only"),
        preSources = ("AllSecuritiesMember", "AllRisksMember")
    ),
    "vip": attrdict(
        efmPre = "6.12.11",
        efmCal = "6.14.07",
        efmDef = "6.16.11",
        elrPre = re.compile("http://xbrl.sec.gov/vip/role/N[346]"),
        elrDefInNs = re.compile("http://xbrl.sec.gov/vip/role/.*Only"),
        elrDefExNs = re.compile("http://xbrl.sec.gov/vip/role/.*Only"),
        preSources = ()
    )
}
