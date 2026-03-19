#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

python arelleCmdLine.py --webserver=0.0.0.0:8080

## Optionally run with gunicorn with 2 workers, recycling workers after each request
## WARNING: Uncomment only one command at a time.
# gunicorn "arelle.CntlrCmdLine:wsgiApplication()" --workers 2 --timeout 180 --max-requests 1 --bind 0.0.0.0:8080
