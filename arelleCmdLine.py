'''

Use this module to start Arelle in command line modes

See COPYRIGHT.md for copyright information.
'''
import sys, os

if sys.platform == "darwin" and getattr(sys, 'frozen', False):
    for i in range(len(sys.path)): # signed code can't contain python modules
        sys.path.append(sys.path[i].replace("MacOS", "Resources"))

from arelle import CntlrCmdLine, CntlrComServer

if '--COMserver' in sys.argv:
    CntlrComServer.main()
elif __name__.startswith('_mod_wsgi_') or os.getenv('wsgi.version'):
    application = CntlrCmdLine.wsgiApplication()
elif __name__ in ('__main__', 'arelleCmdLine__main__', 'arellecmdline__main__'): #cx_Freeze 5 prepends module name to __main__
    CntlrCmdLine.main()