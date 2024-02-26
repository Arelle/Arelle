'''
debugInfo.py provides python path display for debugging frozen code installation issues.

(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''
import sys, os, logging

def showInfo(cntlr, options, *args, **kwargs):
    cntlr.addToLog("Python {}".format(sys.version), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("environment variables...", messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("sys.path={}".format(sys.path), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("LD_LIBRARY_PATH={}".format(os.environ.get("LD_LIBRARY_PATH","")), messageCode="info", level=logging.DEBUG)
    cntlr.addToLog("options...")
    for name, value in sorted(options.__dict__.items(), key=lambda i:i[0]):
        if value is not None:
            cntlr.addToLog("{}={}".format(name,value), messageCode="info", level=logging.DEBUG)
__pluginInfo__ = {
    'name': 'System Info',
    'version': '1.0',
    'description': "This plug-in displays system information such as system path for debugging frozen installation.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2018 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrCmdLine.Utility.Run': showInfo
}
