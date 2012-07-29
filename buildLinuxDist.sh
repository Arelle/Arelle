#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# create version with date and a shell file to name output with the date
python3.2 buildVersion.py

BUILT64=exe.linux-x86_64-3.2

if [ -d build/${BUILT64} ]
  then
    rm -R build/${BUILT64}
fi
mkdir build/${BUILT64}

# run cx_Freeze setup
python3.2 setup.py build_exe
cp arelle/scripts-unix/* build/${BUILT64}

cd build/${BUILT64}
tar -c -gzip -f ../../dist/${BUILT64}.tar.gz .
cd ../..

/bin/sh buildRenameLinux-x86_64.sh
# rm -R build2
