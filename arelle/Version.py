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


def getGitHash() -> str | None:
    return tryRunCommand('git', 'rev-parse', 'HEAD')

def getDefaultVersion() -> str:
    return '0.0.0'


def getVersion() -> str:
    for version_fetcher in [getBuildVersion, getGitHash, getDefaultVersion]:
        fetched_version = version_fetcher()
        if fetched_version is not None:
            return fetched_version
    raise ValueError('Version not set')


__version__ = getVersion()
version = __version__
authorLabel = 'Workiva, Inc.'
copyrightLabel = '(c) Copyright 2011-present Workiva, Inc., All rights reserved.'
