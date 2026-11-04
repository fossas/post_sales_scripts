#!/bin/bash

# verify-scan.sh — API readback for one FOSSA revision (receipts, not screenshots).
#
#   bash verify-scan.sh <org-id> <project-id> [revision] [branch]
#
# revision defaults to .fossa-out/LAST_REV in the current directory (written by fossa-scan.sh on success);
# branch (for the UI link only) defaults to main. Your organization id is the number in the FOSSA UI's
# project URLs (custom+<org-id>/<project-id>) and in GET /api/cli/organization.
# Needs FOSSA_API_KEY. Read-only: every call is a GET.

set -o errexit
set -o nounset
set -o pipefail

if [ $# -lt 2 ]; then
  echo "usage: bash verify-scan.sh <org-id> <project-id> [revision] [branch]" >&2
  exit 1
fi
ORG="$1"
PROJECT="$2"
REV="${3:-$(cat .fossa-out/LAST_REV 2>/dev/null || true)}"
BRANCH="${4:-main}"
: "${REV:?no revision given and no .fossa-out/LAST_REV in $PWD}"
: "${FOSSA_API_KEY:?set FOSSA_API_KEY}"
ENDPOINT="${FOSSA_ENDPOINT:-https://app.fossa.com}"

enc() { python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
LOC="custom+${ORG}/${PROJECT}\$${REV}"
ENC="$(enc "$LOC")"
RENC="$(enc "$REV")"
PENC="$(enc "custom+${ORG}/${PROJECT}")"
H="Authorization: Bearer ${FOSSA_API_KEY}"
api() { local body; body="$(curl -g -s -f -H "$H" "${ENDPOINT}$1")" || { echo "API call failed (HTTP error): $1" >&2; exit 1; }; printf '%s' "$body"; }
# every call below is captured first so that an HTTP failure stops the script before anything tries to parse an empty body

echo "revision locator: $LOC"
echo "UI: ${ENDPOINT}/projects/${PENC}/refs/branch/${BRANCH}/${REV}"
echo

echo "== build status (GET /api/cli/{REV}/latest_build)"
BODY="$(api "/api/cli/${ENC}/latest_build")"
printf '%s' "$BODY" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  ", (d.get("task") or {}).get("status"), "| error:", d.get("error"))'

echo "== issue scan (GET /api/cli/{REV}/issues)"
BODY="$(api "/api/cli/${ENC}/issues")"
printf '%s' "$BODY" | python3 -c '
import sys,json
from collections import Counter
d=json.load(sys.stdin); iss=d.get("issues") or []
print("   status:", d.get("status"))
print("   issues:", len(iss), dict(Counter(i.get("type") for i in iss)))'

echo "== dependencies (GET /api/revisions/{REV}/dependencies)"
BODY="$(api "/api/revisions/${ENC}/dependencies")"
printf '%s' "$BODY" | python3 -c '
import sys,json
from collections import Counter
rows=json.load(sys.stdin)
if isinstance(rows,dict): rows=rows.get("dependencies", rows.get("data", []))
print("   total rows:", len(rows))
def fetcher(r):
    loc=r.get("locator") or ""
    return loc.split("+")[0] if loc else ((r.get("loc") or {}).get("fetcher","?"))
print("   by fetcher:", dict(Counter(fetcher(r) for r in rows)))
unres=[r.get("locator") for r in rows if r.get("resolved") is False]
print("   unresolved:", len(unres), unres[:10])
lic=Counter()
for r in rows:
    for l in (r.get("licenses") or []): lic[l.get("licenseId") or l.get("name") or "?"]+=1
print("   top licenses:", lic.most_common(12))'

echo "== licensing issues (GET /api/v2/issues/statuses, project + revision scope)"
BODY="$(api "/api/v2/issues/statuses?category=licensing&scope[type]=project&scope[id]=${PENC}&scope[revision]=${RENC}")"
printf '%s' "$BODY" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print("   active:", d["issues"]["active"], "| ignored (auto-ignore and manual):", d["issues"]["ignored"])'

echo "== snippets by top-level path (GET /api/revisions/{REV}/snippets/paths?path=/)"
BODY="$(api "/api/revisions/${ENC}/snippets/paths?path=/")"
printf '%s' "$BODY" | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); ps=d.get("paths",[])
    print("   total:", sum(p.get("count",0) for p in ps), "|", ", ".join("%s %s" % (p.get("path"), p.get("count")) for p in ps) or "(none)")
except Exception as e: print("   (no snippet data on this revision)", e)'

echo "== snippet-kind records (GET /api/revisions/{REV}/snippets?path=/, paged)"
PAGES=""; pg=1; while [ "$pg" -le 400 ]; do PAGE="$(api "/api/revisions/${ENC}/snippets?path=/&pageSize=50&page=$pg")"; PAGES="${PAGES}${PAGE}
"; printf '%s' "$PAGE" | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d.get("results",[]); t=d.get("totalCount"); sys.exit(0 if r and (t is None or '"$pg"'*50 < t) else 1)' || break; pg=$((pg+1)); done
printf '%s' "$PAGES" | python3 -c '
import sys,json
from collections import Counter
rows=[]; total=None; msg=None
for raw in sys.stdin.read().split("\n"):
    if not raw.strip(): continue
    try: d=json.loads(raw)
    except Exception: continue
    if isinstance(d,dict) and "message" in d: msg=d["message"]; break
    page=d.get("results",[]) if isinstance(d,dict) else d
    total=d.get("totalCount") if isinstance(d,dict) else total
    if not page: break
    rows+=page
    if total is not None and len(rows)>=total: break
if msg: print("  ", msg); sys.exit()
print("   records:", len(rows), "| totalCount:", total, "| kinds:", dict(Counter(r.get("kind") for r in rows)),
      "" if total is None or len(rows) >= total else "| TRUNCATED: fewer rows than totalCount were returned")
for r in rows:
    if r.get("kind")=="snippet": print("     snippet:", r.get("package"), r.get("version"), "match", r.get("highestMatchPercentage"))'
