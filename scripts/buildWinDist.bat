rem setuptools_scm detects the current version based on the distance from latest
rem git tag and if there are uncommitted changes. Capture version prior to
rem localization build scripts which will create uncommitted changes.
python -W ignore distro.py --version > versionTmpFile
set /p SETUPTOOLS_SCM_PRETEND_VERSION= < versionTmpFile
del versionTmpFile
rem Make directories
mkdir build,dist
rem Rebuild messages.pot internationalization file
python pygettext.py -v -o arelle\locale\messages.pot arelle\*.pyw arelle\*.py
rem Regenerate messages catalog (doc/messagesCatalog.xml)
python generateMessagesCatalog.py
rem Build exe
python distro.py build_exe
