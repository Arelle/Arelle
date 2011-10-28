#!/bin/sh

# remove old build
/bin/rm -rf build
/bin/rm -rf dist

# set the build date in version.py
python3.2 buildVersion.py

# create new app
python3.2 setup.py build_exe

# add lxml _elementpath to lib
mkdir lxml
cp /usr/lib/python3/dist-packages/lxml/__pycache__/_elementpath.cpython-32.pyc lxml/_elementpath.pyc
zip -u build/exe.linux-i686-3.2/library.zip lxml lxml/_elementpath.pyc
/bin/rm -rf lxml

# stuff taken from the MacOS installer, possibly needed also for Linux
# 
# # add the icon file to resources
# cp -R arelle/images/arelle.icns dist/Arelle.app/Contents/Resources
# 
# # add icon and config files to resources
# cp -R arelle/images dist/Arelle.app/Contents/Resources
# cp -R arelle/config dist/Arelle.app/Contents/Resources
# cp -R arelle/examples dist/Arelle.app/Contents/Resources
# cp -R arelle/locale dist/Arelle.app/Contents/Resources
# 
# # add tcl and tk 8.6 versions
# cp -R /library/frameworks/tcl.framework/versions dist/Arelle.app/Contents/Frameworks/Tcl.framework
# cp -R /library/frameworks/tk.framework/versions dist/Arelle.app/Contents/Frameworks/Tk.framework
# rm -R dist/Arelle.app/Contents/Frameworks/Tcl.framework/Versions/8.5
# rm -R dist/Arelle.app/Contents/Frameworks/Tk.framework/Versions/8.5
#
# /bin/rm -rf dist_pkg
# 
# mkdir dist_pkg
# /developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --root dist --id org.arelle.Arelle --title 'Arelle Open Source XBRL Platform' --out dist_pkg/arelle.pkg --no-recommend --verbose --version 2011041601
# #/developer/applications/utilities/packagemaker.app/contents/macos/packagemaker --doc arelle.pmdoc --out dist_pkg/arelle.pkg --verbose
# 
# # create the .dmg file
# /bin/rm -rf dist_dmg
# mkdir dist_dmg
# #hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist_pkg dist_dmg/arelle.dmg
# hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist dist_dmg/arelle.dmg
# 
# # rename the .dmg file with the exact same version date as Version.py
# sh -x buildRenameDmg.sh
# 
# # delete the built application so that the package can be installed to test it
# #/bin/rm -rf dist
