"""
See COPYRIGHT.md for copyright information.
"""
import os
import platform
import site
import sys
from importlib.metadata import entry_points

import regex as re
from cx_Freeze import Executable, setup
from setuptools import find_packages

LINUX_PLATFORM = "linux"
MACOS_PLATFORM = "darwin"
WINDOWS_PLATFORM = "win32"

cliExecutable = Executable(script="arelleCmdLine.py")
packages = find_packages()
includeFiles = [
    (os.path.normcase("arelle/archive"), "archive"),
    (os.path.normcase("arelle/config"), "config"),
    (os.path.normcase("arelle/doc"), "doc"),
    (os.path.normcase("arelle/examples"), "examples"),
    (os.path.normcase("arelle/images"), "images"),
    (os.path.normcase("arelle/locale"), "locale"),
    (os.path.normcase("arelle/plugin"), "plugin"),
]

# Pip-installed plugins cannot be discovered in frozen builds because
# the `ast` library can't parse `__pluginInfo__` from compiled .pyc files
# Instead, pip-intalled plugins can be copied directly into the plugins folder

# Built list of absolute paths to available pip packages
packageDirectories = []
sitePackagesDirectories = site.getsitepackages()
for sitePackagesDirectory in sitePackagesDirectories:
    if not sitePackagesDirectory.endswith('site-packages'):
        continue
    packageDirectories.extend([os.path.join(sitePackagesDirectory, x) for x in os.listdir(sitePackagesDirectory)])

entryPoints = list(entry_points(group='arelle.plugin'))
for entryPoint in entryPoints:
    pluginUrl = entryPoint.load()()
    pluginDirectory = None
    for packageDirectory in packageDirectories:
        if pluginUrl.startswith(packageDirectory):
            pluginDirectory = packageDirectory
            break
    assert pluginDirectory, f"Corresponding package could not be found for plugin path: {pluginUrl}"
    includeFiles.append((pluginDirectory, os.path.join('plugin', os.path.basename(pluginDirectory))))

includeLibs = [
    "dateutil",
    "dateutil.relativedelta",
    "graphviz",
    "gzip",
    "isodate",
    "jaconv",
    "lxml._elementpath",
    "lxml.etree",
    "lxml.html",
    "lxml",
    "numpy._core._methods",
    "numpy.lib.format",
    "numpy",
    "openpyxl",
    "pg8000",
    "PIL",
    "pymysql",
    "pyparsing",
    "rdflib",
    "regex",
    "sqlite3",
    "tinycss2",
    "tornado",
    "zlib",
]
options = {
    "build_exe": {
        "include_files": includeFiles,
        "includes": includeLibs,
        "packages": packages,
    }
}

if os.path.exists("arelle/plugin/EDGAR") or os.path.exists("arelle/plugin/xule"):
    includeLibs.append("aniso8601")

if os.path.exists("arelle/plugin/EDGAR"):
    includeLibs.append("holidays")
    includeLibs.append("holidays.countries")
    includeLibs.append("holidays.financial")
    includeLibs.append("matplotlib")
    includeLibs.append("matplotlib.pyplot")
    includeLibs.append("pytz")

if sys.platform == LINUX_PLATFORM:
    guiExecutable = Executable(
        script="arelleGUI.py",
        base="gui",
        target_name="arelleGUI",
    )
    includeLibs.append("Crypto")
    includeLibs.append("Crypto.Cipher")
    includeLibs.append("Crypto.Cipher.AES")
    includeFiles.append(("arelle/scripts-unix", "scripts"))
elif sys.platform == MACOS_PLATFORM:
    guiExecutable = Executable(
        script="arelleGUI.py",
        base="gui",
        target_name="arelleGUI",
    )
    includeFiles.append(("arelle/scripts-macOS", "scripts"))
    options["bdist_mac"] = {
        "iconfile": "arelle/images/arelle.icns",
        "bundle_name": "Arelle",
    }
    if codesignIdentity := os.environ.get('CODESIGN_IDENTITY'):
        options["bdist_mac"].update({
            "codesign_identity": codesignIdentity,
            "codesign_deep": True,
            "codesign_timestamp": True,
            "codesign_verify": True,
            "codesign_options": "runtime",
        })
        if platform.machine() == 'x86_64' and sys.version_info >= (3, 14):
            # Required for running x86_64 Python 3.14 builds on Apple Silicon via Rosetta.
            options["bdist_mac"]["codesign_entitlements"] = "arelle/config/rosettaEntitlements.plist"
    if scmTagVersion := os.environ.get('SETUPTOOLS_SCM_PRETEND_VERSION'):
        semverRegex = r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
        if re.fullmatch(semverRegex, scmTagVersion):
            # Tagged release. Dev versions are ignored.
            options['bdist_mac']['plist_items'] = [
                ('CFBundleVersion', scmTagVersion),
                ('CFBundleShortVersionString', scmTagVersion),
            ]
elif sys.platform == WINDOWS_PLATFORM:
    guiExecutable = Executable(
        script="arelleGUI.pyw",
        base="gui",
        icon="arelle\\images\\arelle16x16and32x32.ico",
    )
    includeFiles.append(("arelle\\scripts-windows", "scripts"))
    if "arelle.webserver" in packages:
        includeFiles.append(("QuickBooks.qwc", "QuickBooks.qwc"))
    # note cx_Oracle isn't included for unix builds because it is version and machine specific.
    includeLibs.append("cx_Oracle")
    includeLibs.append("pyodbc")
    includeLibs.append("requests")
    includeLibs.append("requests_negotiate_sspi")
    options["build_exe"]["include_msvcr"] = True
else:
    raise ValueError(
        f"Frozen builds are supported on Windows, Linux, and macOS. Platform {sys.platform} is not supported."
    )

setup(
    executables=[guiExecutable, cliExecutable],
    options=options,
    setup_requires=["setuptools_scm>=9.2,<10"],
    use_scm_version={
        "tag_regex": r"^(?:[\w-]+-?)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$",
        "write_to": os.path.normcase("arelle/_version.py"),
    },
)
