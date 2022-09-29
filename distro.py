"""
See COPYRIGHT.md for copyright information.
"""
import os
import sys

from cx_Freeze import Executable, setup
from setuptools import find_packages

LINUX_PLATFORM = "linux"
MACOS_PLATFORM = "darwin"
WINDOWS_PLATFORM = "win32"

cliExecutable = Executable(script="arelleCmdLine.py")
packages = find_packages()
includeFiles = [
    (os.path.normcase("arelle/config"), "config"),
    (os.path.normcase("arelle/doc"), "doc"),
    (os.path.normcase("arelle/images"), "images"),
    (os.path.normcase("arelle/locale"), "locale"),
    (os.path.normcase("arelle/examples"), "examples"),
    (os.path.normcase("arelle/examples/plugin"), os.path.normcase("examples/plugin")),
    (
        os.path.normcase("arelle/examples/plugin/locale/fr/LC_MESSAGES"),
        os.path.normcase("examples/plugin/locale/fr/LC_MESSAGES"),
    ),
    (os.path.normcase("arelle/plugin"), "plugin"),
]
includeLibs = [
    "aniso8601",
    "graphviz",
    "gzip",
    "holidays",
    "isodate",
    "lxml._elementpath",
    "lxml.etree",
    "lxml.html",
    "lxml",
    "numpy.core._methods",
    "numpy.lib.format",
    "numpy",
    "openpyxl",
    "pg8000",
    "PIL",
    "pycountry",
    "pymysql",
    "rdflib.extras",
    "rdflib.plugins.memory",
    "rdflib.plugins.parsers",
    "rdflib.plugins.serializers.rdfxml",
    "rdflib.plugins.serializers.turtle",
    "rdflib.plugins.serializers.xmlwriter",
    "rdflib.plugins.serializers",
    "rdflib.plugins.sparql",
    "rdflib.plugins.stores",
    "rdflib.plugins",
    "rdflib.tools",
    "rdflib",
    "regex",
    "sqlite3",
    "zlib",
]
options = {
    "build_exe": {
        "include_files": includeFiles,
        "includes": includeLibs,
        "packages": packages,
    }
}

if os.path.exists("arelle/plugin/EdgarRenderer"):
    includeLibs.append("cherrypy")
    includeLibs.append("dateutil")
    includeLibs.append("dateutil.relativedelta")
    includeLibs.append("matplotlib")
    includeLibs.append("matplotlib.pyplot")
    includeLibs.append("pyparsing")
    includeLibs.append("pytz")
    includeLibs.append("six")
    includeLibs.append("tornado")

if sys.platform == LINUX_PLATFORM:
    guiExecutable = Executable(script="arelleGUI.py", target_name="arelleGUI")
    includeFiles.append(("arelle/scripts-unix", "scripts"))
    if os.path.exists("/etc/redhat-release"):
        includeFiles.append(("/usr/lib64/libexslt.so.0", "libexslt.so"))
        includeFiles.append(("/usr/lib64/libxml2.so", "libxml2.so"))
        includeFiles.append(("/usr/lib64/libxml2.so.2", "libxml2.so.2"))
        includeFiles.append(("/usr/lib64/libxslt.so.1", "libxslt.so"))
        includeFiles.append(("/lib64/libz.so.1", "libz.so.1"))
        includeFiles.append(("/usr/lib64/liblzma.so.5", "liblzma.so.5"))
        includeFiles.append(("/usr/local/lib/tcl8.6", "tcl8.6"))
        includeFiles.append(("/usr/local/lib/tk8.6", "tk8.6"))
elif sys.platform == MACOS_PLATFORM:
    guiExecutable = Executable(script="arelleGUI.py", target_name="arelleGUI")
    includeFiles.append(("arelle/scripts-macOS", "scripts"))
    includeFiles.append(("libs/macos/Tktable2.11", "Tktable2.11"))
    options["bdist_mac"] = {
        "iconfile": "arelle/images/arelle.icns",
        "bundle_name": "Arelle",
    }
elif sys.platform == WINDOWS_PLATFORM:
    guiExecutable = Executable(
        script="arelleGUI.pyw",
        base="Win32GUI",
        icon="arelle\\images\\arelle16x16and32x32.ico",
    )
    includeFiles.append(("arelle\\scripts-windows", "scripts"))
    if "arelle.webserver" in packages:
        includeFiles.append("QuickBooks.qwc")
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
    setup_requires=["setuptools_scm~=7.0"],
    use_scm_version={
        "tag_regex": r"^(?:[\w-]+-?)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$",
        "write_to": os.path.normcase("arelle/_version.py"),
    },
)
