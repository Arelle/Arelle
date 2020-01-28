'''
Created on June 6, 2018

Filer Guidelines: esma32-60-254_esef_reporting_manual.pdf



@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''

from arelle.ModelValue import qname

allowedImgMimeTypes = (
        "data:image/gif;base64", 
        "data:image/jpeg;base64", "data:image/jpg;base64", # note both jpg and jpeg are in use
        "data:image/png;base64")
        
browserMaxBase64ImageLength = 1000000

standardTaxonomyURIs = {
    "http://www.esma.europa.eu/",
    "http://xbrl.ifrs.org/taxonomy/",
    "http://www.xbrl.org/taxonomy/int/lei/"
    }

WiderNarrower = "http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower"
DefaultDimensionLinkrole = "http://www.esma.europa.eu/xbrl/esef/role/ifrs-dim_role-990000"

qnDomainItemType = qname("{http://www.xbrl.org/dtr/type/non-numeric}nonnum:domainItemType")

mandatory = set() # mandatory element qnames

# hidden references
untransformableTypes = {"anyURI", "base64Binary", "hexBinary", "NOTATION", "QName", "time",
                        "token", "language"}


                  