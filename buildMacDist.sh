#!/bin/sh

# remove old build
/bin/rm -rf build
/bin/rm -rf dist

# set the build date in version.py
python3.3 buildVersion.py

# Regenerate messages catalog (doc/messagesCatalog.xml)
python3.3 generateMessagesCatalog.py

# create new app
# python3.3 setup.py py2app
python3.3 setup.py bdist_mac

# fix up tkinter library to not use built-in one
cp /Library/Frameworks/Python.framework/Versions/3.3/lib/python3.3/lib-tkinter/library/_tkinter.so build/Arelle.app/Contents/MacOS

# copy scripts to get packaged with app in distribution directory
/bin/rm -rf dist
mkdir dist
cp -R build/Arelle.app dist
cp arelle/scripts-macOS/* dist

/bin/rm -rf dist_pkg

mkdir dist_pkg
/developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --root dist --id org.arelle.Arelle --title 'Arelle Open Source XBRL Platform' --out dist_pkg/arelle.pkg --no-recommend --verbose --version 2011041601
#/developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --doc arelle.pmdoc --out dist_pkg/arelle.pkg --verbose

# create the .dmg file
/bin/rm -rf dist_dmg
mkdir dist_dmg
#hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist_pkg dist_dmg/arelle.dmg
hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist dist_dmg/arelle.dmg

# rename the .dmg file with the exact same version date as Version.py
sh -x buildRenameDmg.sh

# delete the built application so that the package can be installed to test it
#/bin/rm -rf dist




