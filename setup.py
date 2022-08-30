"""
Created on Jan 30, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.

  pip3.9 or python3.9 -m pip (followed by install below)
    >> windows only may need install wheel
  install lxml pg8000 pymysql pyodbc
    >> windows only install cx_Oracle
  install numpy matplotlib
  install rdflib
  install isodate regex aniso8601 graphviz holidays openpyxl Pillow
  #  install pycrypto  << end user installed only if using any plugin/security module
  install cx_freeze cherrypy cheroot tornado
  pip install --no-cache --use-pep517 pycountry

  may need to reinstall pycountry to get pep517 format
  install pycountry: pip uninstall -y pycountry ; pip install --no-cache --use-pep517 pycountry

to install pycrypto on windows (by end-users using plugin/security modules) see:
  https://www.dariawan.com/tutorials/python/python-3-install-pycrypto-windows/

"""
import datetime
import os
import sys

VERSION_FILE = 'version.txt'


def get_version():
    """
    Retrieving version string from git tag using GitHub Actions environment variables.
    Returns 0.0.0 if no tag included.
    """
    github_ref_type = os.getenv('GITHUB_REF_TYPE')
    github_ref_name = os.getenv('GITHUB_REF_NAME')
    return github_ref_name if github_ref_type == 'tag' else '0.0.0'


options = {}
cx_freeze_executables = []


if sys.platform in ('darwin', 'linux'):
    from setuptools import find_packages
    try:
        from cx_Freeze import setup, Executable
        cx_freeze_executables = [
            Executable(script="arelleGUI.py", target_name="arelleGUI"),
            Executable(script="arelleCmdLine.py")
        ]
    except:
        from setuptools import setup
        cx_freeze_executables = []

    packages = find_packages(
        '.',  # note that new setuptools finds plugin and lib unwanted stuff
        exclude=['*.plugin.*', '*.lib.*']
    )

    data_files = []
    include_files = [
        ('arelle/config', 'config'),
        ('arelle/doc', 'doc'),
        ('arelle/images', 'images'),
        ('arelle/locale', 'locale'),
        ('arelle/examples', 'examples'),
        ('arelle/examples/plugin', 'examples/plugin'),
        (
            'arelle/examples/plugin/locale/fr/LC_MESSAGES',
            'examples/plugin/locale/fr/LC_MESSAGES'
        ),
        ('arelle/plugin', 'plugin')
    ]
    if sys.platform == 'darwin':
        include_files.append(('arelle/scripts-macOS', 'scripts'))
        include_files.append(('libs/macos/Tktable2.11', 'Tktable2.11'))
    else:
        include_files.append(('arelle/scripts-unix', 'scripts'))
        if os.path.exists("/etc/redhat-release"):
            # extra libraries needed for red hat
            include_files.append(('/usr/lib64/libexslt.so.0', 'libexslt.so'))
            include_files.append(('/usr/lib64/libxml2.so', 'libxml2.so'))
            # for some reason redhat needs libxml2.so.2 as well
            include_files.append(('/usr/lib64/libxml2.so.2', 'libxml2.so.2'))
            include_files.append(('/usr/lib64/libxslt.so.1', 'libxslt.so'))
            include_files.append(('/lib64/libz.so.1', 'libz.so.1')) # not standard in RHEL6
            include_files.append(('/usr/lib64/liblzma.so.5', 'liblzma.so.5')) # not standard in RHEL6
            include_files.append(('/usr/local/lib/tcl8.6', 'tcl8.6'))
            include_files.append(('/usr/local/lib/tk8.6', 'tk8.6'))

    if os.path.exists(VERSION_FILE):
        include_files.append((VERSION_FILE, VERSION_FILE))

    include_libs = [
        'lxml', 'lxml.etree', 'lxml._elementpath', 'lxml.html',
        'pg8000', 'pymysql', 'sqlite3', 'numpy',
        'numpy.core._methods', 'numpy.lib.format',
        # note cx_Oracle isn't here because it is version and machine specific,
        # ubuntu not likely working
        # more rdflib plugin modules may need to be added later
        'rdflib',
        'rdflib.extras',
        'rdflib.tools',
        'rdflib.plugins',
        'rdflib.plugins.memory',
        'rdflib.plugins.parsers',
        'rdflib.plugins.serializers',
        'rdflib.plugins.serializers.rdfxml',
        'rdflib.plugins.serializers.turtle',
        'rdflib.plugins.serializers.xmlwriter',
        'rdflib.plugins.sparql',
        'rdflib.plugins.stores',
        'isodate', 'regex', 'gzip', 'zlib', 'aniso8601', 'graphviz', 'holidays',
        'openpyxl', 'PIL',  # to install PIL it's named Pillow
        'pycountry' # to install pycountry: pip uninstall -y pycountry ; pip install --no-cache --use-pep517 pycountry
        # only installed by end-users when using security plugins: 'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES' # install pycrypto not another crypto module
        # 'google_api_python_client', 'oauth2client', 'six', 'httplib2', 'uritemplate', 'pyasn1', 'rsa', 'pyasn1_modules' # google-api-python-client
    ]

    exclude_libs = []

    if os.path.exists("arelle/plugin/EdgarRenderer"):
        include_libs += [
            'cherrypy',  # 'cherrypy.wsgiserver.wsgiserver3',
            'dateutil', 'pytz',  # pytz installed by dateutil
            'dateutil.relativedelta',

            'tornado',
            'pyparsing',
            'matplotlib', 'matplotlib.pyplot'
        ]

    options = dict(
        build_exe={
            "include_files": include_files,
            #
            # rdflib & isodate egg files: rename .zip cpy lib & egg-info
            # subdirectories to site-packages directory
            #
            "includes": include_libs,
            "excludes": exclude_libs,
            "packages": packages,
        }
    )
    options["bdist_mac"] = {
        "iconfile": 'arelle/images/arelle.icns',
        "bundle_name": 'Arelle',
    }


elif sys.platform == 'win32':
    from setuptools import find_packages
    from cx_Freeze import setup, Executable
    # FIXME: this should use the entry_points mechanism
    packages = find_packages('.')
    print("packages={}".format(packages))
    data_files = None
    win32_include_files = [
        ('arelle\\config', 'config'),
        ('arelle\\doc', 'doc'),
        ('arelle\\images', 'images'),
        ('arelle\\locale', 'locale'),
        ('arelle\\examples', 'examples'),
        ('arelle\\examples\\plugin', 'examples/plugin'),
        (
            'arelle\\examples\\plugin\\locale\\fr\\LC_MESSAGES',
            'examples/plugin/locale/fr/LC_MESSAGES'
        ),
        ('arelle\\plugin', 'plugin'),
        ('arelle\\scripts-windows', 'scripts')
    ]
    if 'arelle.webserver' in packages:
        win32_include_files.append('QuickBooks.qwc')

    if os.path.exists(VERSION_FILE):
        win32_include_files.append(VERSION_FILE)

    include_libs = [
        'lxml', 'lxml.etree', 'lxml._elementpath', 'lxml.html',
        'pg8000', 'pymysql', 'cx_Oracle', 'pyodbc', 'sqlite3', 'numpy',
        'numpy.core._methods', 'numpy.lib.format',  # additional modules of numpy
        # more rdflib plugin modules may need to be added later
        'rdflib',
        'rdflib.extras',
        'rdflib.tools',
        'rdflib.plugins',
        'rdflib.plugins.memory',
        'rdflib.plugins.parsers',
        'rdflib.plugins.serializers',
        'rdflib.plugins.serializers.rdfxml',
        'rdflib.plugins.serializers.turtle',
        'rdflib.plugins.serializers.xmlwriter',
        'rdflib.plugins.sparql',
        'rdflib.plugins.stores',
        'isodate', 'regex', 'gzip', 'zlib', 'aniso8601', 'graphviz', 'holidays',
        'openpyxl', 'PIL', 'pycountry',
        # only installed by end-users when using security plugins: 'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES',
        'requests', 'requests_negotiate_sspi'
    ]
    # uncomment the next line if cx_Freezing with EdgarRenderer
    # note that openpyxl must be 2.1.4 at this time
    # removed tornado
    if os.path.exists("arelle/plugin/EdgarRenderer"):
        include_libs += [
            'cherrypy',  # 'cherrypy.wsgiserver.wsgiserver3',
            'dateutil', 'dateutil.relativedelta',
            "six", "pyparsing", "matplotlib", "matplotlib.pyplot"
        ]

    options = dict(
        build_exe={
            "include_files": win32_include_files,
            "include_msvcr": True,  # include MSVCR100
            # "icon": 'arelle\\images\\arelle16x16and32x32.ico',
            "packages": packages,
            #
            # rdflib & isodate egg files: rename .zip cpy lib & egg-info
            # subdirectories to site-packages directory
            #
            "includes": include_libs
        }
    )

    # windows uses arelleGUI.exe to launch in GUI mode, arelleCmdLine.exe in command line mode
    cx_freeze_executables = [
        Executable(
            script="arelleGUI.pyw",
            base="Win32GUI",
            icon='arelle\\images\\arelle16x16and32x32.ico',
        ),
        Executable(
            script="arelleCmdLine.py",
        )
    ]
else:
    from setuptools import os, setup, find_packages
    packages = find_packages(
        '.', # note that new setuptools finds plugin and lib unwanted stuff
        exclude=['*.plugin.*', '*.lib.*']
    )
    data_files = [(
        'config',
        ['arelle/config/' + f for f in os.listdir('arelle/config')]
    )]
    cx_freeze_executables = []

timestamp = datetime.datetime.utcnow()
setup(
    version=get_version(),
    include_package_data=True,
    packages=packages,
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'arelle=arelle.CntlrCmdLine:main',
        ],
        'gui_scripts': [
            'arelle-gui=arelle.CntlrWinMain:main',
        ],
    },
    options=options,
    executables=cx_freeze_executables,
)
