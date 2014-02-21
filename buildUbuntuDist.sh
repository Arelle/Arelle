#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# create version with date and a shell file to name output with the date
python3.3 buildVersion.py

BUILT64=exe.linux-x86_64-3.3

if [ -d build/${BUILT64} ]
  then
    rm -fR build/${BUILT64}
fi
mkdir build/${BUILT64}

if [ ! -d dist ]
  then
    mkdir dist
fi

# run cx_Freeze setup
python3.3 setup.py build_exe
cp arelle/scripts-unix/* build/${BUILT64}

cd build/${BUILT64}
tar -czf ../../dist/${BUILT64}.tar.gz .
cd ../..

/bin/sh buildRenameLinux-x86_64.sh
# rm -R build2
