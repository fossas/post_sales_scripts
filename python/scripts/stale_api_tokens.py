#!/usr/bin/env python3
"""List (and optionally delete) API tokens whose owner hasn't uploaded to FOSSA recently.

FOSSA keeps no per-token usage data: tokens have no last-used field, and audit logs
record the acting user, never the token. So "stale" here means: the token's OWNER has
no Project ADD_REVISION / ADD_PROJECT audit event in the last --days days, and the
token itself is older than --days. A user with several tokens can't be split further.
Note ADD_REVISION is also logged by UI rebuilds, so "active" = any upload/rebuild.

Org is implied by the token (both APIs are scoped to the caller's org). Use a token from
an org admin, or only that admin's own tokens are listed.

  FOSSA_API_KEY=... ./stale_api_tokens.py                      # dry run
  FOSSA_API_KEY=... ./stale_api_tokens.py --apply --confirm-org 1234
"""
import argparse, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone


def api(method, path, params=None):
    url = HOST + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        return json.loads(body) if body else None


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def active_user_ids(since):
    """actingUserId -> latest upload time, paging by id."""
    last, after = {}, None
    while True:
        params = {"topics": "Project", "actions": "ADD_REVISION,ADD_PROJECT",
                  "startDate": since.strftime("%Y-%m-%d"), "sortBy": "id", "sortDir": "ASC", "limit": 5000}
        if after:
            params["startingAfter"] = after
        rows = api("GET", "/api/audit_logs", params)
        for r in rows:
            uid, ts = r.get("actingUserId"), parse_ts(r["createdAt"])
            if uid and (uid not in last or ts > last[uid]):
                last[uid] = ts
        if len(rows) < 5000:
            return last
        after = rows[-1]["id"]


def main():
    global HOST, TOKEN
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("FOSSA_API_URL", "https://app.fossa.com"))
    p.add_argument("--days", type=int, default=30, help="inactivity window (default 30)")
    p.add_argument("--apply", action="store_true", help="actually delete the listed tokens")
    p.add_argument("--confirm-org", type=int, help="required with --apply; must match the token's org id")
    a = p.parse_args()
    HOST, TOKEN = a.host.rstrip("/"), os.environ.get("FOSSA_API_KEY")
    if not TOKEN:
        sys.exit("FOSSA_API_KEY not set")

    org = api("GET", "/api/cli/organization")
    org_id = org["organizationId"]
    print(f"org {org_id} on {HOST}", file=sys.stderr)
    if a.apply and a.confirm_org != org_id:
        sys.exit(f"--apply needs --confirm-org {org_id} (token's org); refusing")

    cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)
    active = active_user_ids(cutoff)
    tokens = api("GET", f"/api/organizations/{org_id}/api-tokens")

    stale = [t for t in tokens if t["userId"] not in active and parse_ts(t["createdAt"]) < cutoff]
    kept = len(tokens) - len(stale)
    print(f"{len(tokens)} tokens, {len(active)} users uploaded since {cutoff:%Y-%m-%d}; "
          f"{len(stale)} stale, {kept} kept", file=sys.stderr)

    print("tokenId\tcreatedAt\tpushOnly\tdisabled\tuserId\temail\tname")
    for t in sorted(stale, key=lambda t: (t.get("email") or "", t["createdAt"])):
        print(f"{t['id']}\t{t['createdAt'][:10]}\t{t.get('isPushOnly')}\t{t.get('isDisabled')}\t"
              f"{t['userId']}\t{t.get('email')}\t{t.get('name')}")

    if not a.apply:
        print("\ndry run: nothing deleted. Re-run with --apply --confirm-org "
              f"{org_id} to delete the {len(stale)} tokens above.", file=sys.stderr)
        return
    failed = 0
    for t in stale:
        try:  # no retry: a DELETE that timed out may have succeeded
            api("DELETE", f"/api/organizations/{org_id}/api-tokens/{t['id']}")
            print(f"deleted {t['id']}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"FAILED {t['id']}: {e}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
