rem Make directories
mkdir build,dist
rem Rebuild messages.pot internationalization file
python pygettext.py -v -o arelle\locale\messages.pot arelle\*.pyw arelle\*.py
rem Regenerate messages catalog (doc/messagesCatalog.xml)
python generateMessagesCatalog.py
rem Build exe
python distro.py build_exe
