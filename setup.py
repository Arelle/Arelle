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
import sys
import os
import datetime
from distutils.command.build_py import build_py as _build_py


def get_version():
    """
    Retrieving version string from git tag using Github Actions environment variables.
    Returns 0.0.0 if no tag included.
    """
    github_ref_type = os.getenv('GITHUB_REF_TYPE')
    github_ref_name = os.getenv('GITHUB_REF_NAME')
    return github_ref_name if github_ref_type == 'tag' else '0.0.0'



options = {}
cxFreezeExecutables = []

def match_patterns(path, pattern_list=[]):
    from fnmatch import fnmatch
    for pattern in pattern_list:
        if fnmatch(path, pattern):
            return True
    return False



''' this section was for py2app which no longer works on Mavericks,
    switch below to cx_Freeze

if sys.platform == 'darwin':
    from setuptools import setup, find_packages
    
    setup_requires.append('py2app')
    # Cross-platform applications generally expect sys.argv to
    # be used for opening files.
    
    plist = dict(CFBundleIconFile='arelle.icns', 
                 NSHumanReadableCopyright='(c) 2010-2013 Mark V Systems Limited') 

    # MacOS launches CntlrWinMain and uses "ARELLE_ARGS" to effect console (shell) mode
    options = dict(py2app=dict(app=['arelle/CntlrWinMain.py'], 
                               iconfile='arelle/images/arelle.icns', 
                               plist=plist, 
                               #
                               # rdflib & isodate egg files: rename .zip cpy lib & egg-info subdirectories to site-packages directory
                               #
                               includes=['lxml', 'lxml.etree',  
                                         'lxml._elementpath', 'pg8000', 
                                         'rdflib', 'rdflib.extras', 'rdflib.tools', 
                                         # more rdflib plugin modules may need to be added later
                                         'rdflib.plugins', 'rdflib.plugins.memory', 
                                         'rdflib.plugins.parsers', 
                                         'rdflib.plugins.serializers', 'rdflib.plugins.serializers.rdfxml', 'rdflib.plugins.serializers.turtle', 'rdflib.plugins.serializers.xmlwriter', 
                                         'rdflib.plugins.sparql', 
                                         'rdflib.plugins.stores', 
                                         'isodate', 'regex', 'gzip', 'zlib'])) 

    packages = find_packages('.')
    dataFiles = [
    #XXX: this breaks build on Lion/Py3.2  --mike 
    #'--iconfile', 
    ('config',['arelle/config/' + f for f in os.listdir('arelle/config')]),
    ('doc',['arelle/doc/' + f for f in os.listdir('arelle/doc')]),
    ('examples',['arelle/examples/' + f for f in os.listdir('arelle/examples')]),
    ('images',['arelle/images/' + f for f in os.listdir('arelle/images')]),
    ('examples/plugin',['arelle/examples/plugin/' + f for f in os.listdir('arelle/examples/plugin')]),
    ('examples/plugin/locale/fr/LC_MESSAGES',['arelle/examples/plugin/locale/fr/LC_MESSAGES/' + f for f in os.listdir('arelle/examples/plugin/locale/fr/LC_MESSAGES')]),
    ('plugin',['arelle/plugin/' + f for f in os.listdir('arelle/plugin')]),
    ('scripts',['arelle/scripts/' + f for f in os.listdir('arelle/scripts-macOS')]),
      ]
    for dir, subDirs, files in os.walk('arelle/locale'):
        dir = dir.replace('\\','/')
        dataFiles.append((dir[7:],
                          [dir + "/" + f for f in files]))
    cx_FreezeExecutables = []
#End of py2app defunct section
'''

# works on ubuntu with hand-built cx_Freeze
if sys.platform in ('darwin', 'linux2', 'linux', 'sunos5'):
    from setuptools import find_packages
    try:
        from cx_Freeze import setup, Executable  
        cx_FreezeExecutables = [ 
            Executable(script="arelleGUI.py", targetName="arelleGUI"),
            Executable(script="arelleCmdLine.py")
        ]
    except:
        from setuptools import setup
        cx_FreezeExecutables = []

    packages = find_packages(
        '.',  # note that new setuptools finds plugin and lib unwanted stuff
        exclude=['*.plugin.*', '*.lib.*']
    )

    dataFiles = []
    includeFiles = [
        ('arelle/config','config'),
        ('arelle/doc','doc'),
        ('arelle/images','images'),
        ('arelle/locale','locale'),
        ('arelle/examples','examples'),
        ('arelle/examples/plugin','examples/plugin'),
        (
            'arelle/examples/plugin/locale/fr/LC_MESSAGES',
            'examples/plugin/locale/fr/LC_MESSAGES'
        ),
        ('arelle/plugin','plugin')
    ]
    if sys.platform == 'darwin':
        includeFiles.append(('arelle/scripts-macOS','scripts'))
        # copy tck and tk built as described: https://www.tcl.tk/doc/howto/compile.html#mac
        # includeFiles.append(('/Library/Frameworks/Tcl.framework/Versions/8.6/Resources/Scripts','tcl8.6'))
        # includeFiles.append(('/Library/Frameworks/Tk.framework/Versions/8.6/Resources/Scripts','tk8.6'))
        # includeFiles.append(('/Library/Frameworks/Python.framework/Versions/3.5/lib/python3.5/tkinter','lib/tkinter'))
        # includeFiles.append(('/Library/Frameworks/Python.framework/Versions/3.5/lib/python3.5/lib-dynload/_tkinter.cpython-35m-darwin.so','lib/_tkinter.cpython-35m-darwin.so'))
        includeFiles.append(('../libs/macos/Tktable2.11','Tktable2.11'))
    else: 
        includeFiles.append(('arelle/scripts-unix','scripts'))
        if os.path.exists("/etc/redhat-release"):
            # extra libraries needed for red hat
            includeFiles.append(('/usr/lib64/libexslt.so.0', 'libexslt.so'))
            includeFiles.append(('/usr/lib64/libxml2.so', 'libxml2.so'))
            # for some reason redhat needs libxml2.so.2 as well
            includeFiles.append(('/usr/lib64/libxml2.so.2', 'libxml2.so.2'))
            includeFiles.append(('/usr/lib64/libxslt.so.1', 'libxslt.so'))
            includeFiles.append(('/lib64/libz.so.1', 'libz.so.1')) # not standard in RHEL6
            includeFiles.append(('/usr/lib64/liblzma.so.5', 'liblzma.so.5')) # not standard in RHEL6
            includeFiles.append(('/usr/local/lib/tcl8.6', 'tcl8.6')) 
            includeFiles.append(('/usr/local/lib/tk8.6', 'tk8.6')) 
                
    if os.path.exists("version.txt"):
        includeFiles.append(('version.txt', 'version.txt'))
        
    includeLibs = [
        'lxml', 'lxml.etree', 'lxml._elementpath', 'lxml.html',
        'pg8000', 'pymysql', 'sqlite3', 'numpy', 
        'numpy.core._methods', 'numpy.lib.format', # additional modules of numpy
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
        'openpyxl', 'PIL', # to install PIL it's named Pillow
        'pycountry' # to install pycountry: pip uninstall -y pycountry ; pip install --no-cache --use-pep517 pycountry
        # only installed by end-users when using security plugins: 'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES' # install pycrypto not another crypto module
        #'google_api_python_client', 'oauth2client', 'six', 'httplib2', 'uritemplate', 'pyasn1', 'rsa', 'pyasn1_modules' # google-api-python-client
    ]

    excludeLibs = []

    #if sys.platform == 'darwin':
    #    excludeLibs += ['tkinter'] # copied in as files
    
    # uncomment the next two files if cx_Freezing with EdgarRenderer
    # note that openpyxl must be 2.1.4 at this time
    if os.path.exists("arelle/plugin/EdgarRenderer"):
        includeLibs += [
            'cherrypy', # 'cherrypy.wsgiserver.wsgiserver3',
            'dateutil', 'pytz', # pytz installed by dateutil
            'dateutil.relativedelta',
            
            'tornado',
            'pyparsing',
            'matplotlib', 'matplotlib.pyplot'
        ]
        import matplotlib
        #dataFiles += matplotlib.get_py2exe_datafiles()

    if sys.platform != 'sunos5':
        try:
            import pyodbc # see if this is importable
            includeLibs.append('pyodbc')  # has C compiling errors on Sparc
        except ImportError:
            pass
    options = dict(
        build_exe={
            "include_files": includeFiles,
            #
            # rdflib & isodate egg files: rename .zip cpy lib & egg-info
            # subdirectories to site-packages directory
            #
            "includes": includeLibs,
            "excludes": excludeLibs,
            "packages": packages,
        }
    )
    if sys.platform == 'darwin':
        options["bdist_mac"] = {
            "iconfile": 'arelle/images/arelle.icns',
            "bundle_name": 'Arelle',
        }
        
    
elif sys.platform == 'win32':
    from setuptools import find_packages
    from cx_Freeze import setup, Executable 
    # py2exe is not ported to Python 3 yet
    # setup_requires.append('py2exe')
    # FIXME: this should use the entry_points mechanism
    packages = find_packages('.')
    print("packages={}".format(packages))
    dataFiles = None
    win32includeFiles = [
        ('arelle\\config','config'),
        ('arelle\\doc','doc'),
        ('arelle\\images','images'),
        ('arelle\\locale','locale'),
        ('arelle\\examples','examples'),
        ('arelle\\examples\\plugin','examples/plugin'),
        (
            'arelle\\examples\\plugin\\locale\\fr\\LC_MESSAGES',
            'examples/plugin/locale/fr/LC_MESSAGES'
        ),
        ('arelle\\plugin','plugin'),
        ('arelle\\scripts-windows','scripts')
    ]
    if 'arelle.webserver' in packages:
        win32includeFiles.append('QuickBooks.qwc')

    if os.path.exists("version.txt"):
        win32includeFiles.append('version.txt')
        
    includeLibs = [
        'lxml', 'lxml.etree', 'lxml._elementpath', 'lxml.html',
        'pg8000', 'pymysql', 'cx_Oracle', 'pyodbc', 'sqlite3', 'numpy',
        'numpy.core._methods', 'numpy.lib.format', # additional modules of numpy
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
        includeLibs += [
            'cherrypy', # 'cherrypy.wsgiserver.wsgiserver3', 
            'dateutil', 'dateutil.relativedelta',
            "six", "pyparsing", "matplotlib", "matplotlib.pyplot"
        ]
        import matplotlib
        
    options = dict(
        build_exe={
            "include_files": win32includeFiles,
            "include_msvcr": True,  # include MSVCR100
            # "icon": 'arelle\\images\\arelle16x16and32x32.ico',
            "packages": packages,
            #
            # rdflib & isodate egg files: rename .zip cpy lib & egg-info
            # subdirectories to site-packages directory
            #
            "includes": includeLibs
        }
    )
   
    # windows uses arelleGUI.exe to launch in GUI mode, arelleCmdLine.exe in command line mode
    cx_FreezeExecutables = [
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
    #print("Your platform {0} isn't supported".format(sys.platform)) 
    #sys.exit(1) 
    from setuptools import os, setup, find_packages
    packages = find_packages(
        '.', # note that new setuptools finds plugin and lib unwanted stuff
        exclude=['*.plugin.*', '*.lib.*']
    )
    dataFiles = [(
        'config',
        ['arelle/config/' + f for f in os.listdir('arelle/config')]
    )]
    cx_FreezeExecutables = []

timestamp = datetime.datetime.utcnow()
setup(
    name='Arelle-ac',
    version='0.0.2',#get_version(),
    description='An open source XBRL platform',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='arelle.org',
    author_email='support@arelle.org',
    url='http://www.arelle.org',
    download_url='http://www.arelle.org/pub',
    include_package_data=True,
    packages=packages,
    data_files=dataFiles,
    platforms=['OS Independent'],
    license='Apache-2',
    keywords=['xbrl'],
    classifiers=[ # valid classifiers here: https://pypi.org/classifiers/
        'Development Status :: 5 - Production/Stable', # 'Development Status :: 1 - Active
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License', # License :: OSI Approved :: Apache-2 License
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Operating System :: OS Independent',
        'Topic :: Text Processing :: Markup :: XML', # Topic :: XBRL Validation and Versioning
    ],
    entry_points={
        'console_scripts': [
            'arelle=arelle.CntlrCmdLine:main',
            'arelle-gui=arelle.CntlrWinMain:main',
        ]
    },
    setup_requires=['lxml'],
    # install_requires specifies a list of package dependencies that are
    # installed when 'python setup.py install' is run. On Linux/Mac systems
    # this also allows installation directly from the github repository
    # (using 'pip install -e git+git://github.com/rheimbuchArelle.git#egg=Arelle')
    # and the install_requires packages are auto-installed as well.
    install_requires=['lxml', 'isodate', 'openpyxl'],
    options=options,
    executables=cx_FreezeExecutables,
)
