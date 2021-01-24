#!/bin/sh

# DO_CODESIGN is either false or true
DO_CODESIGN=false
IDENTAPP="Developer ID Application: Mark V Systems Limited (UUN8V38Y3D)"
IDENTPKG="Developer ID Installer: Mark V Systems Limited (UUN8V38Y3D)"
echo DO_CODESIGN=$DO_CODESIGN
echo IDENTAPP="$IDENTAPP"
echo IDENTPKG="$IDENTPKG"

# remove old build
/bin/rm -rf build/*.app build/lib build/exe.macos* build/*.dmg build/*.command
/bin/rm -rf dist_dmg/arelle-macOS*
/bin/rm -rf dist/arelle-macOS*
/bin/rm -rf dist_dmg/*.dmg

# set the build date in version.py
python3.9 buildVersion.py

# Regenerate messages catalog (doc/messagesCatalog.xml)
python3.9 generateMessagesCatalog.py

# create new app
python3.9 setup.py bdist_mac

# 3.9 patches
cp -r /Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages/pycountry-20.7.3-py3.9.egg-info build/Arelle.app/Contents/MacOS/lib
cp -r /Library/Frameworks/Python.framework/Versions/3.9/lib/tcl8.6 build/Arelle.app/Contents/MacOS
cp -r /Library/Frameworks/Python.framework/Versions/3.9/lib/tk8.6 build/Arelle.app/Contents/MacOS
rm -fr build/Arelle.app/Contents/MacOS/lib/arelle/plugin build/Arelle.app/Contents/MacOS/lib/arelle/config build/Arelle.app/Contents/MacOS/lib/arelle/images

# move python modules to Resources
if [ $DO_CODESIGN = true ]
then

for f in config doc examples images locale plugin scripts tcl8.6 tk8.6 Tktable2.11 ;
  do
    mv build/Arelle.app/Contents/MacOS/$f build/Arelle.app/Contents/Resources
  done

for f in `ls build/Arelle.app/Contents/MacOS/lib | grep -v "Python\|encodings\|codecs\|importlib\|matplotlib\|zlib\|library.zip\|so$"`
  do
    mv build/Arelle.app/Contents/MacOS/lib/$f build/Arelle.app/Contents/Resources/lib
  done

fi

# code signing
codesign --remove-signature build/Arelle.app/Contents/MacOS/lib/Python
for f in `find build/Arelle.app/Contents/MacOS \( -name '*.so' -o -name '*.dylib' \)`
  do
    codesign --remove-signature $f
  done

if [ $DO_CODESIGN = true ]
then

for f in `ls build/Arelle.app/Contents/MacOS/*dylib`
  do
    codesign -s "$IDENTAPP" $f
  done
for f in `ls build/Arelle.app/Contents/MacOS/lib/*so`
  do
    codesign -s "$IDENTAPP" $f
  done
for f in `find build/Arelle.app/Contents/Resources \( -name '*.so' -o -name '*.dylib' \)`
  do
    codesign --remove-signature $f
    codesign -s "$IDENTAPP" $f
  done
codesign -s "$IDENTAPP" build/Arelle.app/Contents/MacOS/lib/Python
codesign --options runtime --deep -s "$IDENTAPP" build/Arelle.app/Contents/MacOS/arelleCmdLine
codesign --options runtime --deep -s "$IDENTAPP" build/Arelle.app/Contents/MacOS/arelleGUI

fi

# remove .git subdirectories
find build/Arelle.app/Contents/Resources -name .git -exec rm -fR {} \;

# copy scripts to get packaged with app in distribution directory
mkdir dist
cp arelle/scripts-macOS/* build

mkdir dist_dmg

# simple way to create the .dmg file
#     hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist dist_dmg/arelle.dmg

if [ ! -e build/Applications ]
then 
    osascript -e 'tell application "Finder" to make alias file to POSIX file "/Applications" at POSIX file "/Users/arelle/hfdev/build"'
fi

#hdiutil create -fs HFS+ -fsargs "-c c=64,a=16,e=16"  -format UDZO dist_dmg/arelle.dmg -imagekey zlib-level=9 -srcfolder build/Arelle.app -volname Arelle -srcfolder build/Applications 

# rename the .dmg file with the exact same version date as Version.py
#sh -x buildRenameDmg.sh

#exit

# create .dmg with background image and positioned icons


# make an image dmg
# set up your app name, version number, and background image file name
DMG_BACKGROUND_IMG="arelle/images/dmg_background.png"

# figure out how big our DMG needs to be
#  assumes our contents are at least 1M!
SIZE=`du -sh build/Arelle.app | sed 's/\([0-9\.]*\)M\(.*\)/\1/'` 
# +1 is not enough, try +2 SIZE=`echo "${SIZE} + 1.0" | bc | awk '{print int($1+0.5)}'`
SIZE=`echo "${SIZE} + 20.0" | bc | awk '{print int($1+0.5)}'`

if [ $? -ne 0 ]; then
   echo "Error: Cannot compute size of staging dir"
   exit
fi

# create the temp DMG file
hdiutil create -srcfolder build/Arelle.app -volname Arelle -fs HFS+ \
      -fsargs "-c c=64,a=16,e=16" -format UDRW -size ${SIZE}M dist_dmg/arelle_tmp.dmg

echo "Created DMG: arelle_tmp.dmg"

# mount it and save the device
DEVICE=$(hdiutil attach -readwrite -noverify dist_dmg/arelle_tmp.dmg | \
         egrep '^/dev/' | sed 1q | awk '{print $1}')

sleep 2

# add a link to the Applications dir
echo "Add link to /Applications"
pushd /Volumes/Arelle
ln -s /Applications
popd

# add a background image
mkdir /Volumes/Arelle/.background
cp arelle/images/dmg_background.png /Volumes/Arelle/.background/

# tell the Finder to resize the window, set the background,
#  change the icon size, place the icons in the right position, etc.
echo '
   tell application "Finder"
     tell disk "Arelle"
           open
           set current view of container window to icon view
           set toolbar visible of container window to false
           set statusbar visible of container window to false
           set the bounds of container window to {400, 100, 920, 440}
           set viewOptions to the icon view options of container window
           set arrangement of viewOptions to not arranged
           set icon size of viewOptions to 72
           set background picture of viewOptions to file ".background:dmg_background.png"
           set position of item ".background" of container window to {999,999}
           set position of item ".DS_Store" of container window to {999,1099}
           set position of item ".Trashes" of container window to {999,1199}
           set position of item ".fseventsd" of container window to {999,1299}
           set position of item "Arelle.app" of container window to {150, 70}
           set position of item "startWebServer.command" of container window to {360, 70}
           set position of item "Applications" of container window to {260, 240}
           close
           open
           update without registering applications
           delay 2
     end tell
   end tell
' | osascript

sync

# unmount it
hdiutil detach "${DEVICE}"

# now make the final image a compressed disk image
echo "Creating compressed image"
hdiutil convert dist_dmg/arelle_tmp.dmg -format UDZO -imagekey zlib-level=9 -o dist_dmg/arelle.dmg
rm dist_dmg/arelle_tmp.dmg

# sign package
build/Arelle.app/Contents/

if [ $DO_CODESIGN = true ]
  then
    codesign -s "$IDENTAPP" dist_dmg/arelle.dmg
fi

# rename the .dmg file with the exact same version date as Version.py
sh -x buildRenameDmg.sh

