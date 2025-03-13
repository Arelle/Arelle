"""

Auto load taxonomy package for entry points in XBRL Taxonomy Registry (via STANDARD_PACKAGES_URL).

See COPYRIGHT.md for copyright information.
"""

import json

from arelle import PackageManager
from arelle.DialogPackageManager import STANDARD_PACKAGES_URL
from arelle.Version import authorLabel, copyrightLabel

entryPointsPackageUrl = None

def taxonomyPackageAutoLoad(_cntlr, packagesConfig, url):
    global entryPointsPackageUrl
    if packagesConfig is not None and url is not None and url.startswith("http"):
        if entryPointsPackageUrl is None: # load standard taxonomy packages
            entryPointsPackageUrl = {}
            with open(_cntlr.webCache.getfilename(STANDARD_PACKAGES_URL, reload=True), 'r', errors='replace') as fh:
                regPkgs = json.load(fh) # always reload
            for pkgTxmy in regPkgs.get("taxonomies", []):
                _url = pkgTxmy.get("Links",{}).get("AuthoritativeURL")
                if _url.endswith(".zip"):
                    # Ignore taxonomies that lack a direct download link.
                    # Although future valid taxonomy download links from the registry might not have a ".zip" extension,
                    # as of October 27th, 2024, all links that without a zip file extension have been invalid.
                    for _ep in pkgTxmy.get("EntryPoints") or ():
                        for _doc in _ep.get("EntryPointDocuments") or ():
                            entryPointsPackageUrl[_doc] = _url
        if url in entryPointsPackageUrl and not any(
            url.startswith(mapFrom) and not url.startswith(mapTo)
            for mapFrom, mapTo in packagesConfig.get('remappings', {}).items()):
                #print(f"loading package {url}")
                PackageManager.addPackage(_cntlr, entryPointsPackageUrl[url])

__pluginInfo__ = {
    "name": "Taxonomy Package Auto Load",
    "version": "1.0",
    "description": "This plug-in auto loads taxonomy packages from XBRL registry.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "TaxonomyPackage.AutoLoad": taxonomyPackageAutoLoad,
}
