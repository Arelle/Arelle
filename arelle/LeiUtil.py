'''
Created on Apr 25, 2015

@author: Mark V Systems Limited
(c) Copyright 2015 Mark V Systems Limited, All rights reserved.

Implementation of ISO 17442:2012(E) Appendix A

'''
try:
    import regex as re
except ImportError:
    import re

LEI_VALID = 0
LEI_INVALID_LEXICAL = 1
LEI_INVALID_CHECKSUM = 2

LEI_RESULTS = ("valid", "invalid lexical", "invalid checksum")

leiLexicalPattern = re.compile(r"^[0-9A-Z]{18}[0-9]{2}$")

def checkLei(lei):
    if not leiLexicalPattern.match(lei):
        return LEI_INVALID_LEXICAL
    if not int(
        "".join({"0":"0", "1":"1", "2":"2", "3":"3", "4":"4", "5":"5", "6":"6", "7":"7", "8":"8", "9":"9",
                 "A":"10", "B":"11", "C":"12", "D":"13", "E":"14", "F":"15", "G":"16", "H":"17", "I":"18",
                 "J":"19", "K":"20", "L":"21", "M":"22", "N":"23", "O":"24", "P":"25", "Q":"26", "R":"27",
                 "S":"28", "T":"29", "U":"30", "V":"31", "W":"32", "X":"33", "Y":"34", "Z":"35"
                 }[c] for c in lei)
               ) % 97 == 1:
        return LEI_INVALID_CHECKSUM  
    return LEI_VALID
    
if __name__ == "__main__":
    # test cases
    for lei, name in ( 
                        ("001GPB6A9XPE8XJICC14", "Fidelity Advisor Series I"),
                        ("004L5FPTUREIWK9T2N63", "Hutchin Hill Capital, LP"),
                        ("00EHHQ2ZHDCFXJCPCL46", "Vanguard Russell 1000 Growth Index Trust"),
                        ("00GBW0Z2GYIER7DHDS71", "Aristeia Capital, L.L.C."),
                        ("1S619D6B3ZQIH6MS6B47", "Barclays Vie SA"),
                        ("21380014JAZAUFJRHC43", "BRE/OPERA HOLDINGS"),
                        ("21380016W7GAG26FIJ74", "SOCIETE FRANCAISE ET SUISSE"),
                        ("21380058ERUIT9H53T71", "TOTAN ICAP CO., LTD"),
                        ("213800A9GT65GAES2V60", "BARCLAYS SECURITIES JAPAN LIMITED"),
                        ("213800DELL1MWFDHVN53", "PIRELLI JAPAN"),
                        ("213800A9GT65GAES2V60", "BARCLAYS SECURITIES JAPAN LIMITED"),
                        ("214800A9GT65GAES2V60", "Error 1"),
                        ("213800A9GT65GAE%2V60", "Error 2"),
                        ("213800A9GT65GAES2V62", "Error 3"),
                        ("1234", "Error 4"),
                        ("""    
5299003M8JKHEFX58Y02""", "Error 4")
                        ):
            print ("LEI {} result {} name {}".format(lei, LEI_RESULTS[checkLei(lei)], name)  )

