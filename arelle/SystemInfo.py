"""
Created on Sep 24, 2022

@author: Mark V Systems Limited
(c) Copyright 2022 Mark V Systems Limited, All rights reserved.
"""
from __future__ import annotations

import os
import platform
import sys
from typing import Any

from arelle.Version import __version__


def get_system_info() -> dict[str, Any]:
    """Return info about the system."""
    info_object = {
        "arch": platform.machine(),
        "docker": False,
        "os_name": platform.system(),
        "version_arelle": __version__,
        "version_os": platform.release(),
        "version_python": platform.python_version(),
        "virtualenv": getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or hasattr(sys, "real_prefix"),
    }

    if platform.system() == "Darwin":
        info_object["os_version"] = platform.mac_ver()[0]
    elif platform.system() == "Linux":
        info_object["docker"] = os.path.isfile("/.dockerenv")

    return info_object
