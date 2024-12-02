#! /bin/bash

# Installer disk created by this script was succesfully tested on Virtualbox 6.1.4 r136177.

# First argument to the program should be the absolute path to the macOS installer app.
# Example: "/Applications/Install macOS Catalina.app"
APP_PATH=$1

# Installer name is used for the volume name and disk image names.
INSTALLER_NAME="macOSinstaller$(date +%d%m%Y)"

# Make an image to create the bootable media in /tmp.
# Make sure the size is enough for future images. 9000m is enough for Catalina 10.15.4.
# Next steps did not work with a dmg. So creating a sparsebundle is important.
hdiutil create -size 25g -type "SPARSEBUNDLE" -o "/tmp/$INSTALLER_NAME" -volname "$INSTALLER_NAME" -layout "SPUD" -fs "HFS+J"

# Mount the created disk.
hdiutil attach "/tmp/$INSTALLER_NAME.sparsebundle" -noverify -mountpoint "/Volumes/$INSTALLER_NAME"

# Create insaller media according to apple documentation.
# https://support.apple.com/en-us/HT201372
sudo "$APP_PATH/Contents/Resources/createinstallmedia" --volume "/Volumes/$INSTALLER_NAME" --nointeraction

# Unmount the created installer media volume.
# Media creation renames the volume. Therefore grep is used to find and unmount the volume.
hdiutil detach "/Volumes/$(ls "/Volumes" | grep "Install")"

# Convert the sparsebundle to an iso. You can not get extension directly to iso.
hdiutil convert "/tmp/$INSTALLER_NAME.sparsebundle" -format UDTO -o "$INSTALLER_NAME.cdr"
mv "$INSTALLER_NAME.cdr" "$INSTALLER_NAME.iso"
