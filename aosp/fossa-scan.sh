#!/bin/bash

# fossa-scan.sh — scan an AOSP / Android Automotive vendor tree with FOSSA in one run.
#
#   bash fossa-scan.sh --dry     regenerate fossa-deps.yml, analyze, upload nothing, print the units found
#   bash fossa-scan.sh           regenerate fossa-deps.yml, analyze with Vendetta + snippet scan, upload,
#                                then wait for the issue scan (fossa test)
#
# Run it from the root of the vendor tree (the directory holding .fossa.yml, fossa-deps.base.yml, tools/).
#
# Requirements
#   fossa-cli >= 3.20, python3 >= 3.10
#   FOSSA_API_KEY            for the full run (the dry run uploads nothing)
#   JAVA_HOME, ANDROID_HOME  the Gradle lane needs the app's build environment; without it fossa-cli
#                            exits 0 with zero Gradle dependencies (see README, "Lane notes")
# Optional
#   REV      revision name (default: <tree>-<git sha>-<timestamp>, unique per run)
#   BRANCH   branch name (default: the git branch, else main)
#   FOSSA_TEST_TIMEOUT  seconds fossa test waits for the issue scan (default 1200)

set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")"

TREE="$(basename "$PWD")"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
REV="${REV:-${TREE}-${GIT_SHA}-$(date +%Y%m%d-%H%M%S)}"
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"

if [ -z "${ANDROID_HOME:-}" ] || [ -z "${JAVA_HOME:-}" ]; then
  echo "warning: JAVA_HOME and/or ANDROID_HOME are not set; the Gradle lane will likely produce zero dependencies" >&2
fi

mkdir -p .fossa-out

# 0. Regenerate fossa-deps.yml from the tree (METADATA -> git references, prebuilt jars -> maven
#    coordinates; vendored/custom sections come from fossa-deps.base.yml). Offline, idempotent,
#    exits 2 instead of writing a file with a missing lane.
python3 -I tools/gen-fossa-deps.py

if [ "${1:-}" = "--dry" ]; then
  fossa analyze --output -r "$REV" -b "$BRANCH" > .fossa-out/analyze-dry.json
  python3 - <<'PY'
import json
d = json.load(open(".fossa-out/analyze-dry.json"))
for su in d["sourceUnits"]:
    deps = su["Build"]["Dependencies"]
    print("%-22s %-60s deps=%d" % (su["Type"], su.get("Name", ""), len(deps)))
PY
  exit 0
fi

: "${FOSSA_API_KEY:?set FOSSA_API_KEY for the full run}"
echo "revision: $REV (branch $BRANCH)"
echo "$REV" > .fossa-out/LAST_REV_PENDING            # in flight; promoted to LAST_REV only when analyze succeeds
fossa analyze \
  --x-vendetta \
  --snippet-scan \
  -r "$REV" -b "$BRANCH" \
  2>&1 | tee ".fossa-out/analyze-$REV.log"
mv .fossa-out/LAST_REV_PENDING .fossa-out/LAST_REV     # reached only if analyze exited 0

echo
echo "fossa test (policy gate; exits non-zero when policy issues exist):"
fossa test -r "$REV" --timeout "${FOSSA_TEST_TIMEOUT:-1200}" || true
