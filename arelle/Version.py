"""
This module represents the time stamp when Arelle was last built

@author: Workiva
(c) Copyright 2022 Workiva, All rights reserved.

"""
from __future__ import annotations

from datetime import datetime


def getBuildVersion() -> str | None:
    try:
        import arelle._version
        return arelle._version.version
    except ModuleNotFoundError:
        return None


def getGitHash() -> str | None:
    import subprocess
    p = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, encoding='utf-8')
    if not p.stderr:
        return p.stdout.strip()
    return None


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
copyrightLatestYear = datetime.now().year
