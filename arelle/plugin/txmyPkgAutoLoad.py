"""

Auto load taxonomy package for entry points in XBRL Taxonomy Registry (via STANDARD_PACKAGES_URL).

See COPYRIGHT.md for copyright information.

When this plugin is loaded, the XBRL Taxonomy Registry is used to check if any external taxonomy
url is listed as an entry point and if so, if the corresponding package has not yet been loaded,
loads the taxonomy package before resolving the URL to the redirected contents in the package.

Eliminates the need to manually specify taxonomy packages in GUI or command line for registered 
taxonomy packages.

The validate feature adds Validate Packages to the GUI under the help menu top section, and 
--validateTaxonomyPackages to the command line.

If any specified taxonomy packages are loaded (from GUI or --packages) they are checked with
all of the registered taxonomy packages to check for entry point conflicts and rewrite overlaps.

To validate locally-loaded taxonomy package(s) against registered packages (useful when developing
and testing a new not-yet-registered package):
   with GUI specify the locally-loaded packages by Help->Manage Packages and then run Help->Validate Packages
   with command line specify the locally-loaded packages by --packages and also --validateTaxonomyPackages

"""

import json, logging, threading
from collections import defaultdict
from typing import TYPE_CHECKING

from arelle.Cntlr import Cntlr
from arelle import PackageManager
from arelle.DialogPackageManager import STANDARD_PACKAGES_URL
from arelle.Version import authorLabel, copyrightLabel

if TYPE_CHECKING:
    from arelle.typing import TypeGetText
    _: TypeGetText  # Handle gettext

entryPointsPackageUrl = None

def taxonomyPackageAutoLoad(cntlr: Cntlr, packagesConfig: dict, url: str):
    global entryPointsPackageUrl
    if packagesConfig is not None and url is not None and url.startswith("http"):
        if entryPointsPackageUrl is None: # load standard taxonomy packages entry points
            entryPointsPackageUrl = {}
            with open(cntlr.webCache.getfilename(STANDARD_PACKAGES_URL, reload=True), 'r', errors='replace') as fh:
                regPkgs = json.load(fh)
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
                PackageManager.addPackage(cntlr, entryPointsPackageUrl[url])
                PackageManager.rebuildRemappings(cntlr)

def validatePackages(cntlr):
    with open(cntlr.webCache.getfilename(STANDARD_PACKAGES_URL, reload=True), 'r', errors='replace') as fh:
        regPkgs = json.load(fh)
    entryPointPkgs = defaultdict(set)
    cntlr.showStatus(_("Loading XBRL Taxonomy Registry"))
    for pkgTxmy in regPkgs.get("taxonomies", []):
        _url = pkgTxmy.get("Links",{}).get("AuthoritativeURL")
        if _url.endswith(".zip"):
            # Ignore taxonomies that lack a direct download link.
            # Although future valid taxonomy download links from the registry might not have a ".zip" extension,
            # as of October 27th, 2024, all links that without a zip file extension have been invalid.
            for _ep in pkgTxmy.get("EntryPoints") or ():
                for _doc in _ep.get("EntryPointDocuments") or ():
                    entryPointPkgs[_doc].add(_url)
            # loading will confirm any overlapping redirects
            cntlr.showStatus(_("Checking taxonomy package {}").format(_url))
            PackageManager.addPackage(cntlr, _url)
    for _packageInfo in PackageManager.packagesConfig["packages"]:
        _url = _packageInfo.get("URL")
        ident = _packageInfo.get("identifier")
        if ident.startswith("http:"):
            cntlr.addToLog(_("Package identifier should use https as the scheme."),
                           messageCode="xbrlTxmyPractGuide.3.1.1",
                           file=_url,
                           level=logging.WARNING)
        version = _packageInfo.get("version")
        if version:
            for name in _packageInfo.get("name").split(", "):
                if version in name:
                    cntlr.addToLog(_("Package name contains version: name %(name)s, version %(version)s"),
                                   messageArgs={"name": name, "version": version},
                                   messageCode="xbrlTxmyPractGuide.3.1.2",
                                   file=_url,
                                   level=logging.WARNING)
    for _doc, _urls in sorted(entryPointPkgs.items()):
        if len(_urls) > 1:
            cntlr.addToLog(_("Registered packages contain same entry point: %(entryPoint)s, packages %(packages)s"),
                           messageArgs={"entryPoint": _doc, "packages": ", ".join(sorted(_urls))},
                           messageCode="arelle.packageEntryPointsConflict",
                           file=_urls,
                           level=logging.WARNING)
    cntlr.showStatus(_("Checking for package remapping overlaps"))
    # provide warning messages of overlapping redirects among all the standard packages and previously loaded packages
    PackageManager.rebuildRemappings(cntlr)
    cntlr.showStatus(_("Done validating taxonomy packages"), 15000)
                
def validatePackagesMenuExtender(cntlr, menu, *args, **kwargs):
    menu.add_command(label=_("Validate packages"),
                     underline=0,
                     command=lambda: threading.Thread(target=validatePackages, args=(cntlr,), daemon=True).start()
                     )
def validatePackagesOptionExtender(parser, *args, **kwargs):
    parser.add_option("--validateTaxonomyPackages",
                      action="store_true",
                      dest="validateTaxonomyPackages",
                      help=_("Validate any cmd line loaded packages against XBRL Taxonomy Registry packages (including entry point conflicts and overlapping redirects)."))

def validatePackagesCommandLineRun(cntlr, options, *args, **kwargs):
    if options.validateTaxonomyPackages:
        validatePackages(cntlr)

__pluginInfo__ = {
    "name": "Taxonomy Package Auto Load",
    "version": "1.0",
    "description": "This plug-in auto loads taxonomy packages from XBRL registry.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    # classes of mount points (required)
    "TaxonomyPackage.AutoLoad": taxonomyPackageAutoLoad,
    "CntlrCmdLine.Options": validatePackagesOptionExtender,
    "CntlrCmdLine.Utility.Run": validatePackagesCommandLineRun,
    "CntlrWinMain.Menu.Help.Upper": validatePackagesMenuExtender
}
