"""
System Info plugin provides python path display for debugging frozen code installation issues.

See COPYRIGHT.md for copyright information.
"""

import logging
import os
import sys
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.RuntimeOptions import RuntimeOptions
from arelle.utils.PluginHooks import PluginHooks
from arelle.Version import authorLabel, copyrightLabel


class ShowInfoPlugin(PluginHooks):

    @staticmethod
    def cntlrCmdLineUtilityRun(
        cntlr: Cntlr,
        options: RuntimeOptions,
        *args: Any,
        **kwargs: Any
    ) -> None:
        cntlr.addToLog(f"Python {sys.version}", messageCode="info", level=logging.DEBUG)
        cntlr.addToLog("environment variables...", messageCode="info", level=logging.DEBUG)
        cntlr.addToLog(f"sys.path={sys.path}", messageCode="info", level=logging.DEBUG)
        cntlr.addToLog(f"LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH', '')}", messageCode="info", level=logging.DEBUG)
        cntlr.addToLog("options...")
        for name, value in sorted(vars(options).items()):
            if value is not None:
                cntlr.addToLog(f"{name}={value}", messageCode="info", level=logging.DEBUG)


__pluginInfo__ = {
    "name": "System Info",
    "version": "1.0",
    "description": "This plug-in displays system information such as system path for debugging frozen installation.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "CntlrCmdLine.Utility.Run": ShowInfoPlugin.cntlrCmdLineUtilityRun,
}
