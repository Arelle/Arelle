'''
Created on Jan 30, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import sys, os

setup_requires = []
options = {}
scripts = []

if sys.platform == 'darwin':
    from setuptools import setup, find_packages
    
    setup_requires.append('py2app')
    # Cross-platform applications generally expect sys.argv to
    # be used for opening files.
    
    plist = dict(CFBundleIconFile='arelle.icns', 
                 NSHumanReadableCopyright='(c) 2010-2011 Mark V Systems Limited') 

    # MacOS launches CntlrWinMain and uses "ARELLE_ARGS" to effect console (shell) mode
    options = dict(py2app=dict(app=['arelle/CntlrWinMain.py'], 
                               iconfile='arelle/images/arelle.icns', 
                               plist=plist, 
                               includes=['lxml', 'lxml.etree',  
                                         'lxml._elementpath', 'gzip', 'zlib'])) 

    packages = find_packages('.')
    dataFiles = [
    #XXX: this breaks build on Lion/Py3.2  --mike 
    #'--iconfile', 
	('images',['arelle/images/' + f for f in os.listdir('arelle/images')]),
    ('config',['arelle/config/' + f for f in os.listdir('arelle/config')]),
    ('examples',['arelle/examples/' + f for f in os.listdir('arelle/examples')]),
    ('examples/plugin',['arelle/examples/plugin/' + f for f in os.listdir('arelle/examples/plugin')]),
    ('examples/plugin/locale/fr/LC_MESSAGES',['arelle/examples/plugin/locale/fr/LC_MESSAGES/' + f for f in os.listdir('arelle/examples/plugin/locale/fr/LC_MESSAGES')]),
    ('scripts',['arelle/scripts/' + f for f in os.listdir('arelle/scripts-macOS')]),
      ]
    for dir, subDirs, files in os.walk('arelle/locale'):
        dir = dir.replace('\\','/')
        dataFiles.append((dir[7:],
                          [dir + "/" + f for f in files]))
    cx_FreezeExecutables = None
elif sys.platform == 'linux2': # works on ubuntu with hand-built cx_Freeze
    from setuptools import find_packages 
    from cx_Freeze import setup, Executable  
    packages = find_packages('.') 
    dataFiles = None 
    options = dict( build_exe =  { 
        "include_files": [('arelle/config','config'), 
                          ('arelle/images','images'), 
                          ('arelle/locale','locale'), 
                          ('arelle/examples','examples'), 
                          ('arelle/examples/plugin','examples/plugin'), 
                          ('arelle/examples/plugin/locale/fr/LC_MESSAGES','examples/plugin/locale/fr/LC_MESSAGES'), 
                          ('arelle/scripts-unix','scripts'),
                          ],
        "includes": ['lxml', 'lxml.etree', 'lxml._elementpath', 'zlib'], 
        "packages": packages, 
        } ) 
    
    cx_FreezeExecutables = [ 
        Executable( 
                script="arelleGUI.pyw", 
                ), 
        Executable( 
                script="arelleCmdLine.py", 
                )                             
        ] 
elif sys.platform == 'win32':
    from setuptools import find_packages
    from cx_Freeze import setup, Executable 
    # py2exe is not ported to Python 3 yet
    # setup_requires.append('py2exe')
    # FIXME: this should use the entry_points mechanism
    packages = find_packages('.')
    dataFiles = None
    win32includeFiles = [('arelle\\config','config'),
                         ('arelle\\images','images'),
                         ('arelle\\locale','locale'),
                         ('arelle\\examples','examples'),
                         ('arelle\\examples\\plugin','examples/plugin'),
                         ('arelle\\examples\\plugin\\locale\\fr\\LC_MESSAGES','examples/plugin/locale/fr/LC_MESSAGES'),
                         ('arelle\\scripts-windows','scripts')]
    if 'arelle.webserver' in packages:
        win32includeFiles.append('QuickBooks.qwc')
    options = dict( build_exe =  {
        "include_files": win32includeFiles,
        "icon": 'arelle\\images\\arelle16x16and32x32.ico',
        "packages": packages,
        } )
   
    # windows uses arelleGUI.exe to launch in GUI mode, arelleCmdLine.exe in command line mode
    cx_FreezeExecutables = [
        Executable(
                script="arelleGUI.pyw",
                base="Win32GUI",
                ),
        Executable(
                script="arelleCmdLine.py",
                )                            
        ]
else:  
    print("Your platform {0} isn't supported".format(sys.platform)) 
    sys.exit(1) 

setup(name='Arelle',
      version='0.9.0',
      description='An open source XBRL platform',
      long_description=open('README.md').read(),
      author='arelle.org',
      author_email='support@arelle.org',
      url='http://www.arelle.org',
      download_url='http://www.arelle.org/download',
      include_package_data = True,   # note: this uses MANIFEST.in
      packages=packages,
      data_files=dataFiles,
      platforms = ['OS Independent'],
      license = 'Apache-2',
      keywords = ['xbrl'],
      classifiers = [
          'Development Status :: 1 - Active',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache-2 License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Operating System :: OS Independent',
          'Topic :: XBRL Validation and Versioning',
          ],
      scripts=scripts,
      entry_points = {
          'console_scripts': [
              'arelle=arelle.CntlrCmdLine:main',
              'arelle-gui=arelle.CntlrWinMain:main',
          ]
      },
      setup_requires = setup_requires,
      options = options,
      executables = cx_FreezeExecutables,
     )
