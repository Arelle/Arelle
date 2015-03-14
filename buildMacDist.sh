#!/bin/sh

# remove old build
/bin/rm -rf build
/bin/rm -rf dist
/bin/rm -rf dist_dmg

# set the build date in version.py
python3.4 buildVersion.py

# Regenerate messages catalog (doc/messagesCatalog.xml)
python3.4 generateMessagesCatalog.py

# create new app
python3.4 setup.py bdist_mac

# fix up tkinter library to not use built-in one
cp /Library/Frameworks/Python.framework/Versions/3.3/lib/python3.3/lib-dynload/_tkinter.so build/Arelle.app/Contents/MacOS

# copy scripts to get packaged with app in distribution directory
mkdir dist
cp -R build/Arelle.app dist
cp arelle/scripts-macOS/* dist

mkdir dist_dmg

# simple way to create the .dmg file
#     hdiutil create -fs HFS+ -volname "ARELLE" -srcfolder dist dist_dmg/arelle.dmg

# create .dmg with background image and positioned icons

# make an image dmg
# set up your app name, version number, and background image file name
DMG_BACKGROUND_IMG="arelle/images/dmg_background.png"

# figure out how big our DMG needs to be
#  assumes our contents are at least 1M!
SIZE=`du -sh ./dist | sed 's/\([0-9\.]*\)M\(.*\)/\1/'` 
# +1 is not enough, try +2 SIZE=`echo "${SIZE} + 1.0" | bc | awk '{print int($1+0.5)}'`
SIZE=`echo "${SIZE} + 3.0" | bc | awk '{print int($1+0.5)}'`

if [ $? -ne 0 ]; then
   echo "Error: Cannot compute size of staging dir"
   exit
fi

# create the temp DMG file
hdiutil create -srcfolder ./dist -volname Arelle -fs HFS+ \
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

# rename the .dmg file with the exact same version date as Version.py
sh -x buildRenameDmg.sh





