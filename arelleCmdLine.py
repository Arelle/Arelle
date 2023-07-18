'''

Use this module to start Arelle in command line modes

See COPYRIGHT.md for copyright information.
'''
import itertools
import os
import sys
import regex as re

if sys.platform == "darwin" and getattr(sys, 'frozen', False):
    for i in range(len(sys.path)):  # signed code can't contain python modules
        sys.path.append(sys.path[i].replace("MacOS", "Resources"))

from arelle.SocketUtils import INTERNET_CONNECTIVITY, OFFLINE, warnSocket

conn_regex = rf'(\s|^)--({INTERNET_CONNECTIVITY}|{INTERNET_CONNECTIVITY.lower()})'
offline_regex = rf'{OFFLINE}(\s|$)'
comp_eq = re.compile(conn_regex + '=' + offline_regex)
comp_conn = re.compile(conn_regex)
comp_offline = re.compile(offline_regex)
for arg in sys.argv:
    if re.match(comp_eq, arg):
        warnSocket()
for arg1, arg2 in itertools.pairwise(sys.argv):
    if re.match(comp_conn, arg1) and re.match(comp_offline, arg2):
        warnSocket()

from arelle.BetaFeatures import BETA_OBJECT_MODEL_FEATURE, enableNewObjectModel

# Model transition must be enabled before any other imports to avoid mixing base classes.
if f"--{BETA_OBJECT_MODEL_FEATURE}" in sys.argv or f"--{BETA_OBJECT_MODEL_FEATURE.lower()}" in sys.argv:
    enableNewObjectModel()

from arelle import CntlrCmdLine, CntlrComServer

if '--COMserver' in sys.argv:
    CntlrComServer.main()
elif __name__.startswith('_mod_wsgi_') or os.getenv('wsgi.version'):
    application = CntlrCmdLine.wsgiApplication()
elif __name__ in ('__main__', 'arelleCmdLine__main__', 'arellecmdline__main__'): #cx_Freeze 5 prepends module name to __main__
    CntlrCmdLine.main()
