"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from arelle.Version import __version__
from enum import Enum, auto
from typing import Any
import math
import os
import platform
import sys


class PlatformOS(Enum):
    LINUX = auto()
    MACOS = auto()
    WINDOWS = auto()

    @staticmethod
    def getPlatformOS() -> PlatformOS:
        """
        Using system.platform() raises a value error exception
        in windows testing envs and macOS with Python 3.8
        """
        if sys.platform == "darwin":
            return PlatformOS.MACOS
        if sys.platform.startswith("win"):
            return PlatformOS.WINDOWS
        # For legacy support purposes all other platforms are treated the same as Linux.
        return PlatformOS.LINUX


def isCGI() -> bool:
    return os.getenv("GATEWAY_INTERFACE", "").startswith("CGI/")


def isGAE() -> bool:
    serverSoftware = os.getenv("SERVER_SOFTWARE", "")
    return serverSoftware.startswith("Google App Engine/") or serverSoftware.startswith("Development/")


def hasFileSystem() -> bool:
    return not isGAE()


def hasWebServer() -> bool:
    try:
        from arelle import webserver
        return True
    except ImportError:
        return False


def getSystemWordSize() -> int:
    return int(round(math.log(sys.maxsize, 2)) + 1)


def hasVirtualEnv() -> bool:
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or hasattr(sys, "real_prefix")


def getSystemInfo() -> dict[str, Any]:
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
        "python_virtualenv": hasVirtualEnv(),
        "system_word_size": getSystemWordSize(),
        "webserver": hasWebServer(),
    }

    if PlatformOS.getPlatformOS() == PlatformOS.MACOS:
        info_object["os_version"] = platform.mac_ver()[0]
    elif PlatformOS.getPlatformOS() == PlatformOS.LINUX:
        info_object["docker"] = os.path.isfile("/.dockerenv")
    return info_object
