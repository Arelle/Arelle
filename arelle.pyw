'''
Use this module to start Arelle in windowing interactive UI or command line modes

If no arguments, start in GUI mode

If any argument, start in command line mode

See COPYRIGHT.md for copyright information.
'''
import sys
from arelle import CntlrWinMain, CntlrCmdLine

if len(sys.argv) == 1:  # no command line arguments
    CntlrWinMain.main()
else:
    CntlrCmdLine.main()