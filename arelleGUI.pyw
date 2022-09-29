'''
Use this module to start Arelle in windowing interactive UI

See COPYRIGHT.md for copyright information.
'''
import sys

if sys.platform == "darwin" and getattr(sys, 'frozen', False):
    for i in range(len(sys.path)): # signed code can't contain python modules
        sys.path.append(sys.path[i].replace("MacOS", "Resources"))
        
from arelle import CntlrWinMain

CntlrWinMain.main()
