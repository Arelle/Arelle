"""
See COPYRIGHT.md for copyright information.
"""
from typing import Any

from arelle import ViewFileRenderedLayout
from arelle.Version import authorLabel, copyrightLabel


def cntlrCmdLineXbrlRun(cntlr, options, modelXbrl, *args: Any, **kwargs: Any) -> None:
    ViewFileRenderedLayout.viewRenderedLayout(modelXbrl, None, diffToFile=True)


__pluginInfo__ = {
    'name': 'Testcase obtain expected calc 11 mode from variation/result@mode',
    'version': '0.9',
    'description': "This plug-in removes xxx.  ",
    'license': "Apache-2",
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Xbrl.Run': cntlrCmdLineXbrlRun
}
