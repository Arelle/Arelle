#!/bin/sh

# a little more robust script
set -o nounset
set -o errexit

# remove old build
/bin/rm -rf build
/bin/rm -rf dist

# set the build date in version.py
python3.2 buildVersion.py > arelle/Version.py

# prepare icons
pushd arelle/images
unzip -u arelle.icns.zip
popd

# create new app
python3.2 setup.py py2app

# add the icon file to resources
cp -R arelle/images/arelle.icns dist/Arelle.app/Contents/Resources

# add icon and config files to resources
cp -R arelle/images dist/Arelle.app/Contents/Resources
cp -R arelle/config dist/Arelle.app/Contents/Resources

/bin/rm -rf dist_pkg
mkdir dist_pkg
/developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --root dist --id org.arelle.Arelle --title 'Arelle Open Source XBRL Platform' --out dist_pkg/arelle.pkg --no-recommend --verbose --version 2011041601
#/developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --doc arelle.pmdoc --out dist_pkg/arelle.pkg --verbose

# create the .dmg file
/bin/rm -rf dist_dmg
mkdir dist_dmg
#hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist_pkg dist_dmg/arelle.dmg
hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist dist_dmg/arelle.dmg

# delete the built application so that the package can be installed to test it
#/bin/rm -rf dist




