"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import math
import os
import platform
import sys
from typing import Any

from arelle.Version import __version__


def get_system_info() -> dict[str, Any]:
    """Return info about the system."""
    info_object = {
        "arelle_version": __version__,
        "arch": platform.machine(),
        "args": sys.argv,
        "cgi": False,
        "filesystem": True,
        "gae": False,
        "docker": False,
        "os_name": platform.system(),
        "os_version": platform.release(),
        "python_branch": platform.python_branch(),
        "python_compiler": platform.python_compiler(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_virtualenv": getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or hasattr(sys, "real_prefix"),
        "system_word_size": int(round(math.log(sys.maxsize, 2)) + 1),
        "webserver": False,
    }

    if platform.system() == "Darwin":
        info_object["os_version"] = platform.mac_ver()[0]
    elif platform.system() == "Linux":
        info_object["docker"] = os.path.isfile("/.dockerenv")

    return info_object
