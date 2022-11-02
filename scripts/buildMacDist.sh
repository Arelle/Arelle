#!/bin/sh

set -xeu

# setuptools_scm detects the current version based on the distance from latest
# git tag and if there are uncommitted changes. Capture version prior to
# localization build scripts which will create uncommitted changes.
VERSION=$(python -W ignore distro.py --version)
# Rebuild messages.pot internationalization file
python pygettext.py -v -o arelle/locale/messages.pot arelle/*.pyw arelle/*.py
# Regenerate messages catalog (doc/messagesCatalog.xml)
python generateMessagesCatalog.py
cp -p arelleGUI.pyw arelleGUI.py
# Build app
SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION} python distro.py bdist_mac
