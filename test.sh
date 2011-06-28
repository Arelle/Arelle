#!/usr/bin/env bash

if [ -d ".virtualenv" ]; then
   echo "**> virtualenv exists"
else
   echo "**> creating virtualenv"
   virtualenv-3.2 .virtualenv
fi

source .virtualenv/bin/activate

pip install -r requirements.txt

python setup.py test
