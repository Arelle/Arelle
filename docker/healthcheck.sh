#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

curl --fail http://localhost:8080 || exit 1

exit 0
