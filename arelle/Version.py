"""
This module represents the time stamp when Arelle was last built

See COPYRIGHT.md for copyright information.

"""
from __future__ import annotations

from arelle.PythonUtil import tryRunCommand


def getBuildVersion() -> str | None:
    try:
        import arelle._version
        return arelle._version.version
    except ModuleNotFoundError:
        return None


def getGitTag() -> str | None:
    return tryRunCommand("git", "describe", "--tags")

def getGitHash() -> str | None:
    return tryRunCommand("git", "rev-parse", "HEAD")

def getDefaultVersion() -> str:
    return "0.0.0"


def getVersion() -> str:
    for version_fetcher in [getBuildVersion, getGitTag, getGitHash, getDefaultVersion]:
        fetched_version = version_fetcher()
        if fetched_version is not None:
            return fetched_version
    raise ValueError("Version not set")


__version__: str
version: str
authorLabel = "Workiva, Inc."
copyrightLabel = "(c) Copyright 2011-present Workiva, Inc., All rights reserved."


def __getattr__(name: str) -> str:
    # Resolved on first use because finding the version may run git.
    if name in ("__version__", "version"):
        resolvedVersion = getVersion()
        globals().update(__version__=resolvedVersion, version=resolvedVersion)
        return resolvedVersion
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
