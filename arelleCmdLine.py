'''
Created on Feb 19, 2011

Use this module to start Arelle in command line modes

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import sys
from arelle import CntlrCmdLine, CntlrComServer

if '--COMserver' in sys.argv:
    CntlrComServer.main()
else:
    CntlrCmdLine.main()