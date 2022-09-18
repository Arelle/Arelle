'''
cdrFormula is an example of a package plug-in to both GUI menu and command line/web service
that compiles a CDR Formula Linbase file to be executed by Arelle XBRL Formula processing.

For description of CDR formula see: 
    http://http://www.ffiec.gov/find/taxonomy/call_report_taxonomy.html
    
Functions are described in:
    http://www.academia.edu/5920257/UBPR_Users_Guide_Technical_Information_Federal_Financial_Institutions_Examination_Council_Users_Guide_for_the_Uniform_Bank_Performance_Report_Technical_Information 

This plug-in is a python package, and can be loaded by referencing the containing
directory (usually, "sphinx"), and selecting this "__init__.py" file within the sphinx
directory (such as in a file chooser).

(c) Copyright 2014 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r). 
'''

import time, os, io, sys
from arelle.ModelValue import qname
from arelle import XmlUtil
from .cdrValidator import hasCdrFormula, validate

logMessage = None
        
def cdrValidater(val, *args, **kwargs):
    if hasCdrFormula(val):
        # CDR formulae are loaded, last step in validation
        validate(val)
        
def cdrFilesOpenMenuEntender(cntlr, menu, *args, **kwargs):
    pass # ensure plug in loads before model object classes are created by parser

def cdrCommandLineOptionExtender(parser, *args, **kwargs):
    pass # ensure plug in loads before model object classes are created by parser

# plugin changes to model object factor classes
from .cdrModelObject import CDR_LINKBASE, CdrFormula, CdrAbsoluteContext, CdrRelativeContext
cdrModelObjectElementSubstitutionClasses = (
     (qname(CDR_LINKBASE, "formula"), CdrFormula),
     (qname(CDR_LINKBASE, "absoluteContext"), CdrAbsoluteContext),
     (qname(CDR_LINKBASE, "relativeContext"), CdrRelativeContext),
    )

__pluginInfo__ = {
    'name': 'CDR Formula Processor',
    'version': '0.9',
    'description': "This plug-in provides a CDR formula linkbase processor.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2014 Mark V Systems Limited, All rights reserved.',
    # plug-in must load before instance is read (so cdr model classes are initialized before parsing)
    'CntlrWinMain.Menu.File.Open': cdrFilesOpenMenuEntender,
    'CntlrCmdLine.Options': cdrCommandLineOptionExtender,
    # classes of mount points (required)
    'ModelObjectFactory.ElementSubstitutionClasses': cdrModelObjectElementSubstitutionClasses, 
    'Validate.Finally': cdrValidater,
}