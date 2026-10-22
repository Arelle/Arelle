"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from arelle import Version
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
        in windows testing envs
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


def contextMenuClick() -> str:
    """Return the event sequence for a right click in the GUI."""
    rightButton = 3
    if sys.platform == "darwin":
        try:
            from tkinter import TkVersion
        except ImportError:
            pass
        else:
            # Tk on macOS reported the right mouse button as button 2 before Tk 9
            if TkVersion < 9:
                rightButton = 2
    return f"<Button-{rightButton}>"


def getSystemWordSize() -> int:
    return int(round(math.log(sys.maxsize, 2)) + 1)


def hasVirtualEnv() -> bool:
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or hasattr(sys, "real_prefix")


def getSystemInfo() -> dict[str, Any]:
    """Return info about the system."""
    info_object = {
        "arelle_version": Version.__version__,
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
