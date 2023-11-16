"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from arelle.Cntlr import Cntlr
from arelle.PluginUtils import PluginProcessPoolExecutor
from arelle.RuntimeOptions import RuntimeOptions
from arelle.Version import authorLabel, copyrightLabel
from arelle.utils.PluginHooks import PluginHooks


def sumPositiveNumbers(vals: tuple[int, ...]) -> int:
    if any(val < 1 for val in vals):
        raise ValueError("Verify exceptions are logged.")
    return sum(vals)


class MultiPlugin(PluginHooks):
    @staticmethod
    def cntlrInit(
        cntlr: Cntlr,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        jobs = (
            (0, 1),
            (2, 3, 4),
            (5, 6),
            (7, 8, 9),
        )
        with PluginProcessPoolExecutor(sys.modules[__name__]) as pool:
            jobFutures = [
                pool.submit(sumPositiveNumbers, job)
                for job in jobs
            ]
            val = 0
            for future in jobFutures:
                try:
                    val += future.result(1)
                except ValueError as e:
                    cntlr.addToLog(messageCode="multi:error", message=str(e), level=logging.ERROR)
            cntlr.addToLog(messageCode="multi:done", message=f"Computed val={val}")


__pluginInfo__ = {
    "name": "multi",
    "version": "0.0.1",
    "description": "multiprocessing example",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "Cntlr.Init": MultiPlugin.cntlrInit,
}
