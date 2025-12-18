"""
See COPYRIGHT.md for copyright information.
"""
from pathlib import Path

from arelle.Cntlr import Cntlr
from arelle.Version import authorLabel, copyrightLabel

PREFIX = str(Path("/c:/temp/conf/"))
REPLACE = str(Path("tests/resources/conformance_suites/lrr-conf-pwd-2005-06-21.zip/"))

def webCacheTransformUrl(cntlr: Cntlr, url: str | None, base: str | None = None) -> tuple[str | None, bool]:
    if url and url.startswith(PREFIX):
        return url.replace(PREFIX, REPLACE), False
    return url, False

__pluginInfo__ = {
    'name': 'LRR Conformance Suite URL Rewriter',
    'version': '1.0.0',
    'description': "Maps \"file:///c:/temp/conf/\" URLs to path within LRR conformance suite.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'WebCache.TransformURL': webCacheTransformUrl,
}
