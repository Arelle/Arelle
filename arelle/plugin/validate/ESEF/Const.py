'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf



@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

from arelle.ModelValue import qname
from arelle.XbrlConst import all, notAll, hypercubeDimension, dimensionDomain, domainMember, dimensionDefault

allowedImgMimeTypes = (
        "data:image/gif;base64", 
        "data:image/jpeg;base64", "data:image/jpg;base64", # note both jpg and jpeg are in use
        "data:image/png;base64")
        
browserMaxBase64ImageLength = 1000000

standardTaxonomyURIs = {
    "http://www.esma.europa.eu/",
    "http://xbrl.ifrs.org/taxonomy/",
    "http://www.xbrl.org/taxonomy/int/lei/",
    "http://www.xbrl.org/20",
    "http://www.xbrl.org/dtr/",
    "http://www.xbrl.org/lrr/",
    "http://www.xbrl.org/utr/",
    "http://www.w3.org/1999/xlink/",
    }

esefTaxonomyNamespaceURIs = {
    "http://xbrl.ifrs.org/taxonomy/20",
    "http://xbrl.ifrs.org/taxonomy/20",
    }

WiderNarrower = "http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower"
DefaultDimensionLinkrole = "http://www.esma.europa.eu/xbrl/esef/role/ifrs-dim_role-990000"

qnDomainItemType = qname("{http://www.xbrl.org/dtr/type/non-numeric}nonnum:domainItemType")

mandatory = set() # mandatory element qnames

# hidden references
untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                        "token", "language"}

esefDefinitionArcroles = {
    all, notAll, hypercubeDimension, dimensionDomain, domainMember, dimensionDefault,
    WiderNarrower
    }

esefPrimaryStatementPlaceholders = {
    # to be augmented with future IFRS releases as they come known, as well as further PFS placeholders
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}IncomeStatementAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfComprehensiveIncomeAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfCashFlowsAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfChangesInEquityAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfChangesInNetAssetsAvailableForBenefitsAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfFinancialPositionAbstract"),
    qname("{http://xbrl.ifrs.org/taxonomy/2019-03-27/ifrs-full}StatementOfProfitOrLossAndOtherComprehensiveIncomeAbstract"),
    }

                  