# Delete CVS stuff in the current directory and below.
find . -name CVS -exec rm -rf {} \;
find . -name .cvsignore -exec rm -rf {} \;
find . -name .cache -exec rm -rf {} \;
find . -name .caches -exec rm -rf {} \;
