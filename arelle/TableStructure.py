'''
Created on Feb 02, 2014

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import XbrlConst

EFMtableCodes = [
    # ELRs are parsed for these patterns in sort order until there is one match per code
    # sheet(s) may be plural
    ("DEI", re.compile(r".* - document - .*document\W+.*entity\W+.*information.*", re.IGNORECASE)),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*balance\W+sheet.*", re.IGNORECASE)),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*balance\W+sheet.*", re.IGNORECASE)),
    ("CF", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*comprehensive(.*\Wincome|.*\Wloss)", re.IGNORECASE)),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(equity|capital|deficit).*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE)),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*(income|operations)", re.IGNORECASE)),
    ("CFP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*cash\W*flow.*", re.IGNORECASE)),
    ("IS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*loss", re.IGNORECASE)),
    ("ISP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                      r".*loss", re.IGNORECASE)),
    ("BS", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".(position|condition)", re.IGNORECASE)),
    ("BSP", re.compile(r".* - statement - (?!.*details)(?=.*parenthetical)"
                       r".*(position|condition)", re.IGNORECASE)),
    ("SE", re.compile(r".* - statement - (?!.*details)(?!.*parenthetical)"
                      r".*equity\W(\w+\W+)*comprehensive.*", re.IGNORECASE)),
    ]

def evaluateRoleTypesTableCodes(modelXbrl):
    disclosureSystem = modelXbrl.modelManager.disclosureSystem
    if disclosureSystem.EFM:
        tableCodes = list( EFMtableCodes ) # separate copy of list so entries can be deleted
        codeRoleURIs = {}  # lookup by code for roleURI
        
        # resolve structural model
        roleTypes = [roleType
                     for roleURI in modelXbrl.relationshipSet(XbrlConst.parentChild).linkRoleUris
                     for roleType in modelXbrl.roleTypes.get(roleURI,())]
        roleTypes.sort(key=lambda roleType: roleType.definition)
        # assign code to table link roles (Presentation ELRs)
        for roleType in roleTypes:
            definition = roleType.definition
            for i, tableCode in enumerate(tableCodes):
                code, pattern = tableCode
                if code not in codeRoleURIs and pattern.match(definition):
                    codeRoleURIs[roleType.roleURI] = code
                    del tableCodes[i] # done with looking at this code
                    break
        # find defined non-default axes in pre hierarchy for table
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = codeRoleURIs.get(roleType.roleURI)
    else:
        for roleTypes in modelXbrl.roleTypes.values():
            for roleType in roleTypes:
                roleType._tableCode = None
