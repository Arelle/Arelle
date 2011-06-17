'''
Created on Jan 30, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
import sys

setup_requires = []
options = {}
scripts = []

if sys.platform == 'darwin':
    from setuptools import os, setup, find_packages
    
    setup_requires.append('py2app')
    # Cross-platform applications generally expect sys.argv to
    # be used for opening files.
    options['py2app'] =  dict(app=['arelle/CntlrWinMain.py'],
                              iconfile='arelle/images/arelle.icns',
                              plist=dict(CFBundleIconFile='arelle.icns',
                                         NSHumanReadableCopyright='(c) 2010-2011 Mark V Systems Limited'))
    packages = find_packages('.')
    dataFiles = [
	'--iconfile',
	('images',['arelle/images/' + f for f in os.listdir('arelle/images')]),
	('config',['arelle/config/' + f for f in os.listdir('arelle/config')]),
      ]
    cx_FreezeExecutables = None
elif sys.platform == 'win32':
    from setuptools import find_packages
    from cx_Freeze import setup, Executable 
    # py2exe is not ported to Python 3 yet
    # setup_requires.append('py2exe')
    # FIXME: this should use the entry_points mechanism
    scripts.extend(
        ['scripts/runEFMTests.bat',
         'scripts/runUS-GFMTests.bat',
         'scripts/runUTRTests.bat',
         'scripts/runVersioningConsumptionTests.bat',
         'scripts/runXDTTests.bat',
        ])
    packages = find_packages('.')
    dataFiles = None
    options = dict( build_exe =  {
        "include_files": [('arelle\\config','config'),
                          ('arelle\\images','images')],
        "icon": 'arelle\\images\\arelle16x16and32x32.ico',
        "packages": packages,
        } )
   
    cx_FreezeExecutables = [
        Executable(
                script="arelle.pyw",
                base="Win32GUI",
                )                            
        ]
else:
    from setuptools import os, setup, find_packages
    packages = find_packages('.')
    dataFiles = [        
	('config',['arelle/config/' + f for f in os.listdir('arelle/config')]),
      ]
    cx_FreezeExecutables = None

setup(name='Arelle',
      version='0.9.0',
      description='An open source XBRL platform',
      long_description=open('README.txt').read(),
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
          'Programming Language :: Python :: 3.1',
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
