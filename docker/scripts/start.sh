#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

python arelleCmdLine.py --about
python arelleCmdLine.py --webserver=0.0.0.0:8080
