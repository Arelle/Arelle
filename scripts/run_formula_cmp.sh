#!/usr/bin/env bash
set -euo pipefail

# Runs Arelle Formula ruleset and compares outputs against expected comments.
# Artifacts are written under /Users/hermf/temp to avoid /tmp cleanup.

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <ruleset-name-without-.xule> [input-factset-json]"
  echo "Example: $0 taxonomyFunctions"
  exit 2
fi

RULESET_NAME="$1"
INPUT_FACTSET="${2:-/Users/hermf/Documents/projects/XBRL.org/oim/specifications/oim-taxonomy/examples/aapl-10K-20250927-factset.json}"

BASE="/Users/hermf/Documents/projects/XBRL.org/oim/specifications/oim-taxonomy"
CMP="/Users/hermf/temp/cmpff.py"
OUT="/Users/hermf/temp/${RULESET_NAME}.out"
LOG="/Users/hermf/temp/${RULESET_NAME}.log"
RULESET="$BASE/Formula/base/${RULESET_NAME}.xule"

if [[ ! -f "$CMP" ]]; then
  echo "Comparator not found at $CMP"
  echo "Create it first (or ask Copilot to recreate /Users/hermf/temp/cmpff.py)."
  exit 3
fi

if [[ ! -f "$RULESET" ]]; then
  echo "Ruleset not found: $RULESET"
  exit 4
fi

python3 arelleCmdLine.py \
  --plugin 'XbrlModel|XbrlModel/Formula' \
  --formula-ruleset "$BASE/Formula/base/namespace.xule" \
  --formula-ruleset "$BASE/Formula/base/constants.xule" \
  --formula-ruleset "$RULESET" \
  --formula-output-file "$OUT" \
  --file "$INPUT_FACTSET" \
  --validate \
  >"$LOG" 2>&1

python3 "$CMP" "$RULESET" "$OUT"
