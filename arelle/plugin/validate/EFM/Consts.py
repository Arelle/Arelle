'''
Created on Jun 30, 2018

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re

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

edgarDocumentTypes = {
	"10-12B",
    "10-12B/A",
    "10-12G",
    "10-12G/A",
    "10-K",
    "10-K/A",
    "10-KT",
    "10-KT/A",
    "10-Q",
    "10-Q/A",
    "10-QT",
    "10-QT/A",
    "20-F",
    "20-F/A",
    "20FR12B",
    "20FR12B/A",
    "20FR12G",
    "20FR12G/A",
    "40-F",
    "40-F/A",
    "40FR12B",
    "40FR12B/A",
    "40FR12G",
    "40FR12G/A",
    "485APOS",
    "485BPOS",
    "485BXT",
    "497",
    "N-1A",
    "N-1A/A",
    "6-K",
    "6-K/A",
    "8-K",
    "8-K/A",
    "8-K12B",
    "8-K12B/A",
    "8-K12G3",
    "8-K12G3/A",
    "8-K15D5",
    "8-K15D5/A",
    "F-1",
    "F-1/A",
    "F-10",
    "F-10/A",
    "F-10EF",
    "F-10POS",
    "F-1MEF",
    "F-3",
    "F-3/A",
    "F-3ASR",
    "F-3D",
    "F-3DPOS",
    "F-3MEF",
    "F-4 POS",
    "F-4",
    "F-4/A",
    "F-4EF",
    "F-4MEF",
    "F-6",
    "F-9 POS",
    "F-9",
    "F-9/A",
    "F-9EF",
    "K SDR",
    "L SDR",
    "N-1A", 
    "N-1A/A",
    "N-CSR",
    "N-CSR/A",
    "N-CSRS",
    "N-CSRS/A",
    "N-Q",
    "N-Q/A",
    "Other",
    "POS AM",
    "POS EX",
    "POSASR",
    "S-1",
    "S-1/A",
    "S-11",
    "S-11/A",
    "S-11MEF",
    "S-1MEF",
    "S-3",
    "S-3/A",
    "S-3ASR",
    "S-3D",
    "S-3DPOS",
    "S-3MEF",
    "S-4 POS",
    "S-4",
    "S-4/A",
    "S-4EF",
    "S-4MEF",
    "SD",
    "SD",
    "SD/A",
    "SD/A",
    "SP 15D2",
    "SP 15D2/A"
  }
  
edgarSubmissionTypeAllowedDocumentTypes = { 
	"10-12B": ("10-12B", "Other"),
	"10-12B/A": ("10-12B/A", "Other"),
	"10-12G": ("10-12G", "Other"),
	"10-12G/A": ("10-12G/A", "Other"),
	"10-K": ("10-K",),
	"10-K/A": ("10-K", "10-K/A"),
	"10-KT": ("10-K","10-KT","Other"),
	"10-KT/A": ("10-K", "10-KT", "10-KT/A", "Other"),
	"10-Q": ("10-Q",),
	"10-Q/A": ("10-Q", "10-Q/A"),
	"10-QT": ("10-Q", "10-QT", "Other"),
	"10-QT/A": ("10-Q", "10-QT", "10-QT/A", "Other"),
	"20-F": ("20-F",),
	"20-F/A": ("20-F", "20-F/A"),
	"20FR12B": ("20FR12B", "Other"),
	"20FR12B/A": ("20FR12B/A", "Other"),
	"20FR12G": ("20FR12G", "Other"),
	"20FR12G/A": ("20FR12G/A", "Other"),
	"40-F": ("40-F",),
	"40-F/A": ("40-F", "40-F/A"),
	"40FR12B": ("40FR12B", "Other"),
	"40FR12B/A": ("40FR12B/A", "Other"),
	"40FR12G": ("40FR12G", "Other"),
	"40FR12G/A": ("40FR12G/A", "Other"),
    "485APOS": ("485APOS",),
    "485BPOS": ("485BPOS",),
    "485BXT": ("485BXT",),
	"497": ("497", "Other"),
    "N-1A": ("N-1A",),
    "N-1A/A": ("N-1A/A"),
	"6-K": ("6-K",),
	"6-K/A": ("6-K", "6-K/A"),
	"8-K": ("8-K",),
	"8-K/A": ("8-K", "8-K/A"),
	"8-K12B": ("8-K12B", "Other"),
	"8-K12B/A": ("8-K12B/A", "Other"),
	"8-K12G3": ("8-K12G3", "Other"),
	"8-K12G3/A": ("8-K12G3/A", "Other"),
	"8-K15D5": ("8-K15D5", "Other"),
	"8-K15D5/A": ("8-K15D5/A", "Other"),
	"F-1": ("F-1",),
	"F-1/A": ("F-1", "F-1/A"),
	"F-10": ("F-10",),
	"F-10/A": ("F-10", "F-10/A"),
	"F-10EF": ("F-10EF", "Other"),
	"F-10POS": ("F-10POS", "Other"),
	"F-1MEF": ("F-1MEF",),
	"F-3": ("F-3",),
	"F-3/A": ("F-3", "F-3/A"),
	"F-3ASR": ("F-3", "F-3ASR"),
	"F-3D": ("F-3", "F-3D"),
	"F-3DPOS": ("F-3", "F-3DPOS"),
	"F-3MEF": ("F-3MEF",),
	"F-4": ("F-4",),
	"F-4 POS": ("F-4", "F-4 POS"),
	"F-4/A": ("F-4", "F-4/A"),
	"F-4EF": ("F-4", "F-4EF"),
	"F-4MEF": ("F-4MEF",),
	"F-9": ("F-9",),
	"F-9 POS": ("F-9", "F-9 POS"),
	"F-9/A": ("F-9", "F-9/A"),
	"F-9EF": ("F-9", "F-9EF"),
	"N-CSR": ("N-CSR",),
	"N-CSR/A": ("N-CSR/A",),
	"N-CSRS": ("N-CSRS",),
	"N-CSRS/A": ("N-CSRS/A",),
	"N-Q": ("N-Q",),
	"N-Q/A": ("N-Q/A",),
	"POS AM": ("F-1", "F-3", "F-4", "F-6", "Other", 
	           "POS AM", "S-1", "S-11", "S-3", "S-4"),
	"POS EX": ("F-3", "F-4", "Other", 
	           "POS EX", "S-1", "S-3", "S-4"),
	"POSASR": ("F-3", "Other", "POSASR", "S-3"),
	"S-1": ("S-1",),
	"S-1/A": ("S-1", "S-1/A"),
	"S-11": ("S-11",),
	"S-11/A": ("S-11/A",),
	"S-11MEF": ("S-11MEF",),
	"S-1MEF": ("S-1MEF",),
	"S-3": ("S-3",),
	"S-3/A": ("S-3", "S-3/A"),
	"S-3ASR": ("S-3", "S-3ASR"),
	"S-3D": ("S-3", "S-3D"),
	"S-3DPOS": ("S-3", "S-3DPOS"),
	"S-3MEF": ("S-3MEF",),
	"S-4": ("S-4",),
	"S-4 POS": ("S-4", "S-4 POS"),
	"S-4/A": ("S-4", "S-4/A"),
	"S-4EF": ("S-4", "S-4EF"),
	"S-4MEF": ("S-4MEF",),
	"SD": ("SD",),
	"SD/A": ("SD/A",),
	"SP 15D2": ("SP 15D2",),
	"SP 15D2/A": ("SP 15D2/A",),
	"SDR": ("K SDR", "L SDR"),
	"SDR/A": ("K SDR", "L SDR"),
	"SDR-A": ("K SDR", "L SDR"),
	"SDR/W ": ("K SDR", "L SDR")
 }

submissionTypesAllowingEmergingGrowthCompanyFlag = \
submissionTypesAllowingExTransitionPeriodFlag = {"10-12B", "10-12B/A", "10-12G", "10-12G/A", "10-K", "10-KT", "10-K/A", "10-KT/A", "10-Q", "10-Q/A", "10-QT", "10-QT/A", 
                 "20-F", "20-F/A", "20FR12B", "20FR12B/A", "20FR12G", "20FR12G/A",
                 "40-F", "40-F/A", "40FR12B", "40FR12B/A", "40FR12G", "40FR12G/A",
                 "8-K", "8-K/A", "8-K12B", "8-K12B/A", "8-K12G3", "8-K12G3/A", "8-K15D5", "8-K15D5/A",
                 "F-1", "F-1/A", "F-3", "F-3/A", "F-4", "F-4/A", 
                 "S-1", "S-1/A", "S-3", "S-3/A", "S-4", "S-4/A", "S-11", "S-11/A"}
submissionTypesAllowingPeriodOfReport={
    "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A", "N-Q", "10-Q", "10-Q/A", "10-QT", "10-QT/A", "10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A",
    "8-K", "8-K/A", "6-K", "6-K/A", "8-K12B", "8-K12B/A", "8-K12G3", "8-K12G3/A", "8-K15D5", "8-K15D5/A", "N-Q/A", "SP 15D2", "SP 15D2/A", 
    }
submissionTypesAllowingWellKnownSeasonedIssuer = \
submissionTypesAllowingShellCompanyFlag = \
submissionTypesAllowingVoluntaryFilerFlag = \
submissionTypesAllowingAcceleratedFilerStatus = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A"}
submissionTypesAllowingEdgarSmallBusinessFlag = {"10-K", "10-K/A", "10-KT", "10-KT/A", "10-Q", "10-Q/A", "10-QT", "10-QT/A", "S-1", "S-1/A", "S-3", "S-3/A", "S-4", 
                                                 "S-4/A", "S-11", "S-11/A", "10-12B", "10-12B/A", "10-12G", "10-12G/A", "S-11MEF", "S-1MEF", "S-3D", "S-3DPOS", "S-3MEF", 
                                                 "S-4 POS", "S-4EF", "S-4MEF"}
submissionTypesAllowingEntityInvCompanyType = {'497', '485APOS', '485BPOS', '485BXT', 'N-1A', 'N-1A/A', 'N-CSR', 'N-CSR/A', 'N-CSRS', 'N-CSRS/A', 'N-Q', 'N-Q/A'}
submissionTypesAllowingSeriesClasses = {"485APOS", "485BPOS", "485BXT", "497", "N-1A", "N-1A/A", "N-CSR", "N-CSR/A", "N-CSRS", "N-CSRS/A", 'N-Q', 'N-Q/A'}
# doc type requirements are for EFM 6.5.20 and are in some cases a superset of what the submission allows.
docTypesRequiringPeriodOfReport = {"10", "10-K", "10-Q", "20-F", "40-F", "6-K", "8-K", 
    "F-1", "F-10", "F-3", "F-4", "F-9", "S-1", "S-11", "S-3", "S-4", "POS AM", "10-KT", "10-QT", "POS EX", 
    "10/A", "10-K/A", "10-Q/A", "20-F/A", "40-F/A", "6-K/A", "8-K/A", "F-1/A", "F-10/A", "F-3/A", "F-4/A", 
    "F-9/A", "S-1/A", "S-11/A", "S-3/A", "S-4/A", "10-KT/A", "10-QT/A", "485APOS", "485BPOS", "485BXT", "497", 
    "N-CSR", "N-CSRS", "N-Q", "N-CSR/A", "N-CSRS/A", "N-Q/A", "K SDR", "L SDR" }
docTypesRequiringEntityWellKnownSeasonedIssuer = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A"}
docTypesRequiringEntityVolFilersAndPubFloat = {"10-K", "10-KT", "10-K/A", "10-KT/A" }
docTypesRequiringEntityFilerCategory = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "10-Q", "10-Q/A", "10-QT", "10-QT/A", "S-1", "S-1/A", "S-3", "S-3/A",
                                         "S-4", "S-4/A", "S-11", "S-11/A", "S-11MEF", "S-1MEF", "S-3D", "S-3DPOS", "S-3MEF", "S-4 POS", "S-4EF", "S-4MEF", "POS AM", "S-3ASR"}

docTypeDeiItems = ( # ({set of doc types}, (list of dei Names required - list is for repeatability)), ...
      ({"10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F",
        "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A", "40-F/A",
        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
        "6-K/A", "NCSR/A", "N-CSR/A", "N-CSRS/A", "N-Q/A",
        "10", "S-1", "S-3", "S-4", "S-11", "POS AM",
        "10/A", "S-1/A", "S-3/A", "S-4/A", "S-11/A", 
        "8-K", "F-1", "F-3", "F-10", "497", "485APOS", "485BPOS", "485BXT", "N-1A", "N-1A/A",
        "8-K/A", "F-1/A", "F-3/A", "F-10/A", "K SDR", "L SDR",
        "Other"},
        ("EntityRegistrantName", "EntityCentralIndexKey")),
      ({"10-K", "10-KT", "20-F", "40-F",
        "10-K/A", "10-KT/A", "20-F/A", "40-F/A"},
       ("EntityCurrentReportingStatus",)),
     (docTypesRequiringEntityVolFilersAndPubFloat,
      ("EntityVoluntaryFilers", "EntityPublicFloat")),
      ({"10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F",
        "10-K/A", "10-KT/A", "10-Q/A", "10-QT/A", "20-F/A", "40-F/A",
        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
        "6-K/A", "NCSR/A", "N-CSR/A", "N-CSRS/A", "N-Q/A", "K SDR", "L SDR"},
        ("CurrentFiscalYearEndDate", "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus")),
      (docTypesRequiringEntityFilerCategory,
        ("EntityFilerCategory",)),
       (docTypesRequiringEntityWellKnownSeasonedIssuer,
         ("EntityWellKnownSeasonedIssuer",)),
       ({"SD", "SD/A"},
         ("EntityReportingCurrencyISOCode", ))
    )

docTypesRequiringRrSchema = \
docTypesExemptFromRoleOrder = \
submissionTypesExemptFromRoleOrder = ('485APOS', '485BPOS','485BXT', '497', 'N-1A', 'N-1A/A')

docTypesNotAllowingIfrs = ('485APOS', '485BPOS','485BXT', '497', 'N-1A', 'N-1A/A',
                           'N-CSR', 'N-CSR/A', 'N-CSRS', 'N-CSRS/A', 'N-Q', 'N-Q/A',
                           'K SDR', 'L SDR')

docTypesNotAllowingInlineXBRL = {
    "K SDR", "L SDR"}

standardNamespacesPattern = re.compile(
    # non-IFRS groups 1 - authority, 2 - taxonomy (e.g. us-gaap, us-types), 3 - year
    r"http://(xbrl\.us|fasb\.org|xbrl\.sec\.gov)/("
            r"dei|us-gaap|srt|us-types|us-roles|srt-types|srt-roles|rr|country|currency|exch|invest|naics|sic|stpr"
            r")/([0-9]{4})-[0-9]{2}-[0-9]{2}$"
    # ifrs groups 4 - year, 5 - taxonomy (e.g. ifrs-full)
    r"|http://xbrl.ifrs.org/taxonomy/([0-9]{4})-[0-9]{2}-[0-9]{2}/(ifrs[\w-]*)$")

# hidden references
untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                        "token", "language"}
# RR untransformable facts
rrUntransformableEltsPattern = re.compile(r"(\w*TableTextBlock|BarChart\w+|AnnualReturn(19|20)[0-9][0-9])")

usDeprecatedLabelPattern = re.compile(r"^.* \(Deprecated (....-..-..)\)$")
usDeprecatedLabelRole = "http://www.xbrl.org/2003/role/label"
ifrsDeprecatedLabelPattern = re.compile(r"^\s*([0-9]{4}-[0-1][0-9]-[0-2][0-9])\s*$")
ifrsDeprecatedLabelRole = "http://www.xbrl.org/2009/role/deprecatedDateLabel"

latestTaxonomyDocs = { # note that these URLs are blocked by EFM validation modes
    # US FASB/SEC taxonomies
    "country/*": {
        "namespace": "http://xbrl.sec.gov/country/2017-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/country/2017/country-lab-2017-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "currency/*": {
        "namespace": "http://xbrl.sec.gov/currency/2017-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/currency/2017/currency-lab-2017-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "dei/*": {
        "namespace": "http://xbrl.sec.gov/dei/2018-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/dei/2018/dei-lab-2018-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "exch/*": {
        "namespace": "http://xbrl.sec.gov/exch/2019-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/exch/2019/exch-lab-2019-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    # under consideration for a future release
    #"invest/*": {
    #    "namespace": "http://xbrl.sec.gov/invest/2013-01-31",
    #    "deprecatedLabels": "https://xbrl.sec.gov/exch/2013/invest-lab-2013-01-31.xml",
    #    "deprecatedLabelRole": usDeprecatedLabelRole,
    #    "deprecationDatePattern": usDeprecatedLabelPattern
    #    },
    "rr/*": {
        "namespace": "http://xbrl.sec.gov/rr/2018-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/rr/2018/rr-lab-2018-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "srt/*": {
        "namespace": "http://fasb.org/srt/2019-01-31",
        "deprecatedLabels": "http://xbrl.fasb.org/srt/2019/elts/srt-lab-2019-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "stpr/*": {
        "namespace": "http://xbrl.sec.gov/stpr/2018-01-31",
        "deprecatedLabels": "https://xbrl.sec.gov/stpr/2018/stpr-lab-2018-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    "us-gaap/*": {
        "namespace": "http://fasb.org/us-gaap/2019-01-31",
        "deprecatedLabels": "http://xbrl.fasb.org/us-gaap/2019/elts/us-gaap-lab-2019-01-31.xml",
        "deprecatedLabelRole": usDeprecatedLabelRole,
        "deprecationDatePattern": usDeprecatedLabelPattern
        },
    # International taxonomies
    "ifrs-full/*": {
        "namespace": "http://xbrl.ifrs.org/taxonomy/2018-03-16/ifrs-full",
        "deprecatedLabels": "http://xbrl.ifrs.org/taxonomy/2018-03-16/deprecated/depr-lab_full_ifrs-en_2018-03-16.xml",
        "deprecatedLabelRole": ifrsDeprecatedLabelRole,
        "deprecationDatePattern": ifrsDeprecatedLabelPattern
        }
    }
