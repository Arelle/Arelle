'''
Created on Feb 19, 2011

Use this module to start Arelle in command line modes

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import sys, os
from arelle import CntlrCmdLine, CntlrComServer

if '--COMserver' in sys.argv:
    CntlrComServer.main()
elif __name__.startswith('_mod_wsgi_') or os.getenv('wsgi.version'):
    application = CntlrCmdLine.wsgiApplication()
elif __name__ in ('__main__', 'arelleCmdLine__main__', 'arellecmdline__main__'): #cx_Freeze 5 prepends module name to __main__
    CntlrCmdLine.main()