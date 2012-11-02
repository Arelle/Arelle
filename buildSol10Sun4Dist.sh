#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# create version with date and a shell file to name output with the date
python3.2 buildVersion.py

# Regenerate messages catalog (doc/messagesCatalog.xml)
python3.2 generateMessagesCatalog.py

BUILT64=exe.solaris-2.10-sun4v-3.2

if [ -d build/${BUILT64} ]
  then
    rm -R build/${BUILT64}
fi
mkdir build/${BUILT64}

if [ ! -d dist ]
  then
    mkdir dist
fi

# run cx_Freeze setup
python3.2 setup.py build_exe
cp arelle/scripts-unix/* build/${BUILT64}

cd build/${BUILT64}

# for now there's no tkinter on solaris sun4 (intended for server only)
rm arelleGUI

tar -cf ../../dist/${BUILT64}.tar .
gzip ../../dist/${BUILT64}.tar
cd ../..

/bin/sh buildRenameSol10Sun4.sh
# rm -R build2
