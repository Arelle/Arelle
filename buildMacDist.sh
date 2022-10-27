#!/bin/sh

# Rebuild messages.pot internationalization file
python pygettext.py -v -o arelle/locale/messages.pot arelle/*.pyw arelle/*.py
# Regenerate messages catalog (doc/messagesCatalog.xml)
python generateMessagesCatalog.py
cp -p arelleGUI.pyw arelleGUI.py
# Build app
python distro.py bdist_mac
