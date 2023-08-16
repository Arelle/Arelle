"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from arelle.Version import __version__
from typing import Any
import math
import os
import platform
import sys


def isCGI() -> bool:
    return os.getenv("GATEWAY_INTERFACE", "").startswith("CGI/")


def isGAE() -> bool:
    serverSoftware = os.getenv("SERVER_SOFTWARE", "")
    return serverSoftware.startswith("Google App Engine/") or serverSoftware.startswith("Development/")


def hasFileSystem() -> bool:
    return not isGAE()


def getSystemWordSize() -> int:
    return int(round(math.log(sys.maxsize, 2)) + 1)


def getVirtualEnv() -> Any:
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or hasattr(sys, "real_prefix")


def get_system_info() -> dict[str, Any]:
    """Return info about the system."""
    info_object = {
        "arelle_version": __version__,
        "arch": platform.machine(),
        "args": sys.argv,
        "cgi": isCGI(),
        "filesystem": hasFileSystem(),
        "gae": isGAE(),
        "docker": False,
        "os_name": platform.system(),
        "os_version": platform.release(),
        "python_branch": platform.python_branch(),
        "python_compiler": platform.python_compiler(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_virtualenv": getVirtualEnv(),
        "system_word_size": getSystemWordSize(),
        "webserver": False,
    }

    if platform.system() == "Darwin":
        info_object["os_version"] = platform.mac_ver()[0]
    elif platform.system() == "Linux":
        info_object["docker"] = os.path.isfile("/.dockerenv")
    return info_object
