"""

Use this module to start Arelle in command line modes

See COPYRIGHT.md for copyright information.
"""
import os
import sys

# Only imports for modules distributed as part of the standard Python library may go above this line.
# All other imports will result in module not found exceptions on the frozen macOS build.
if sys.platform == "darwin" and getattr(sys, "frozen", False):
    for i in range(len(sys.path)):  # signed code can't contain python modules
        sys.path.append(sys.path[i].replace("MacOS", "Resources"))

import regex as re

from arelle.SocketUtils import INTERNET_CONNECTIVITY, OFFLINE, WORK_OFFLINE, warnSocket

internetConnectivityArgPattern = rf"--({INTERNET_CONNECTIVITY}|{INTERNET_CONNECTIVITY.lower()})"
internetConnectivityArgRegex = re.compile(internetConnectivityArgPattern)
internetConnectivityEqualsRegex = re.compile(rf"{internetConnectivityArgPattern}=(.*)")
workOffline = False
prevArg = ""
for arg in sys.argv[1:]:
    if arg in (f"--{WORK_OFFLINE}", f"--{WORK_OFFLINE.lower()}"):
        workOffline = True
    elif match := internetConnectivityEqualsRegex.fullmatch(arg):
        workOffline = match.group(2) == OFFLINE
    elif internetConnectivityArgRegex.fullmatch(prevArg):
        workOffline = arg == OFFLINE
    prevArg = arg
if workOffline:
    warnSocket()

from arelle import CntlrCmdLine

if __name__.startswith("_mod_wsgi_") or os.getenv("wsgi.version"):
    application = CntlrCmdLine.wsgiApplication()
elif __name__ in ("__main__", "arelleCmdLine__main__", "arellecmdline__main__"): #cx_Freeze 5 prepends module name to __main__
    CntlrCmdLine.main()
