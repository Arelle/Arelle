'''
Data and content created by government employees within the scope of their employment are not subject
to domestic copyright protection. 17 U.S.C. 105.

Plugin class method which isolates IXDS html components from primary IXDS to secondary IXDSes

Current use:  Exhibit 26 and EX-FILING FEES attachment documents are processed in secondary IXDSes

Returns nested list of secondary IXDSes and nested lists of modelXbrl.ixdsHtmlElements to be processed by each.
'''

def isolateSeparateIXDSes(modelXbrl, args, **kwargs):
    separateIXDSes = []

    for htmlElt in modelXbrl.ixdsHtmlElements:
        for elt in htmlElt.iterfind(f".//{{{htmlElt.modelDocument.ixNS}}}nonNumeric[@name='dei:DocumentType' or @name='ffd:SubmissnTp']"):
            print(f"trace {elt.tag} = {elt.text}")

    return separateIXDSes
