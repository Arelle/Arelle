#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

PYTHON=python3.1

# create version with date and a shell file to name output with the date
${PYTHON} buildVersion.py

BUILT64=exe.solaris-2.10-sun4v-3.1

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
${PYTHON} setup.py build
cp arelle/scripts-unix/* build/${BUILT64}

cd build/${BUILT64}

# for now there's no tkinter on solaris sun4 (intended for server only)
# rm arelleGUI

tar -cf ../../dist/${BUILT64}.tar .
gzip ../../dist/${BUILT64}.tar
cd ../..

/bin/sh buildRenameSol10Sun4.sh
# rm -R build2
