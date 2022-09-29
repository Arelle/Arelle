'''
This module is Arelle's COM server controller

(This module can be a pattern for custom integration of Arelle into an application.
It is provided for future referenced but not used in the production code.
It cannot be used in cx_freeze or py2app installer-built deployment, but must be used as source code.
Future source-code plugins may possibly use this mechanism.)

See COPYRIGHT.md for copyright information.
'''
from arelle import PythonUtil # define 2.1 or 3.2 string types
import gettext, time, datetime, os, shlex, sys, traceback
from optparse import OptionParser
from arelle import Cntlr
import logging
import datetime

debugging = 0
useDispatcher = None

def main():
    gettext.install("arelle") # needed for options messages
    import win32com.server.register
    if '--debug' in sys.argv:
        global debugging, useDispatcher
        debugging = 1
        from win32com.server.dispatcher import DefaultDebugDispatcher
        useDispatcher = DefaultDebugDispatcher
    win32com.server.register.UseCommandLine(CntlrComServer, debug=debugging)

class CntlrComServer(Cntlr.Cntlr):
    _public_methods_ = [ 'Load' ]
    _public_attrs_ = [ ]
    _readonly_attrs_ = [ ]
    _reg_progid_ = "Arelle.XbrlServer"
    _reg_clsid_ = "{C0E35073-789A-406B-B93B-3C5698CE4314}"
    _reg_desc_ = "Arelle Open Source XBRL COM Server"


    def __init__(self, logFileName=None):
        #super(CntlrComServer, self).__init__(logFileName=logFileName if logFileName else "logToPrint",
        #                 logFormat="[%(messageCode)s] %(message)s - %(file)s %(sourceLine)s")
        print (sys.path)
        self.startedAt = datetime.datetime.now().microsecond
        self.last = "({0})".format(self.startedAt)
        pass


    def Load(self, url):
        last = self.last
        self.last = url
        return "inst: {0} this: {1}  prev: {2}".format(self.startedAt, url, last)
