#!/usr/bin/env python3
"""aosp_metadata_scan.py — AOSP METADATA -> FOSSA manifests (no source egress).

Published copy (fossas/post_sales_scripts, aosp/tools/). Run tests/test_shapes.py (from tests/: python3 test_shapes.py) after any change to
the pin-shape rules.

Walks an AOSP checkout for per-project METADATA files (protobuf text format,
both the modern `identifier {}` and legacy `url {} + version` schemas), and
emits:

  fossa-deps.yml      tier-1 components as referenced-dependencies, type git.
                      License + CVE via FOSSA's git locators — VERIFY after
                      upload: every row of GET /api/revisions/<url-encoded
                      revision locator>/dependencies must be resolved: true.
  aosp-sbom.cdx.json  CycloneDX 1.5 covering ALL tiers: purls for github
                      upstreams, CPEs (from AOSP's own NVD security tags,
                      version-refreshed when safely derivable from the
                      pinned tag) for CVE watchlists on non-github forks,
                      vcs externalReferences for the rest. Tier-2/3 rows are
                      INVENTORY: CVE via CPE where present, no license data.
  coverage.md         per-component tier/CPE/license_type/note table, totals,
                      a first-party audit list, and the post-upload
                      verification step — so the gaps are explicit, not silent.

Tiers:
  1  github upstream + a pin whose shape can resolve (tag or commit SHA;
     bare numbers and date-style pins are demoted with a note)
     -> fossa-deps git dep (license + CVE; verify resolved post-upload)
  2  non-github upstream, demoted tier-1 pin, and/or CPE -> SBOM inventory
     (CVE via CPE where present; no license data)
  3  no upstream version (e.g. homepage-only METADATA) -> named SBOM
     inventory row, listed in coverage.md as needs-human

Stdlib only, no network, nothing uploaded: output carries names/versions/URLs.
Run anywhere, including airgapped checkouts.

Usage:
  python3 aosp_metadata_scan.py --root /path/to/aosp [--out-dir out]
                                [--project-name NAME] [--pilot N]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import uuid
from pathlib import Path

SKIP_DIRS = {".git", ".repo", "out", ".ccache", "testdata", "tests"}   # tests/testdata holds REAL METADATA fixtures

# --------------------------------------------------------------------------
# protobuf-text-lite parsing (only the fields we need; quote-aware)
# --------------------------------------------------------------------------


def _find_blocks(text: str, label: str) -> list[str]:
    """Return the brace-delimited bodies of every `label { ... }` block,
    scanning quote-aware so braces inside quoted strings don't count.
    Protobuf text allows both `label {` and `label: {` (AOSP's real sqlite
    METADATA uses the colon form for `security: {`) — match both."""
    bodies = []
    for m in re.finditer(r"\b" + re.escape(label) + r"\s*:?\s*\{", text):
        i = m.end()
        depth = 1
        in_str = False
        prev = ""
        start = i
        while i < len(text) and depth:
            c = text[i]
            if in_str:
                if c == '"' and prev != "\\":
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
            prev = c
            i += 1
        if depth == 0:
            bodies.append(text[start : i - 1])
    return bodies


def _scalar(text: str, key: str) -> str | None:
    """First `key: "value"` or bare `key: value` at any depth of `text`."""
    m = re.search(r"\b" + re.escape(key) + r'\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        return m.group(1)
    m = re.search(r"\b" + re.escape(key) + r"\s*:\s*([A-Za-z0-9_.\-]+)", text)
    return m.group(1) if m else None


def _top_level_scalar(body: str, key: str) -> str | None:
    """`key: "value"` in `body` but NOT inside a nested { } block."""
    depth = 0
    in_str = False
    prev = ""
    stripped = []
    for c in body:
        if in_str:
            stripped.append(c)
            if c == '"' and prev != "\\":
                in_str = False
        else:
            if c == '"':
                in_str = True
                stripped.append(c)
            elif c == "{":
                depth += 1
                stripped.append("\x00")  # mask nested content
            elif c == "}":
                depth -= 1
                stripped.append("\x00")
            else:
                stripped.append(c if depth == 0 else "\x00")
        prev = c
    return _scalar("".join(stripped), key)


def parse_metadata(text: str, fallback_name: str) -> dict:
    """Extract {name, git_url, version, cpe, homepage} from one METADATA file."""
    out = {"name": _scalar(text, "name") or fallback_name, "git_url": None,
           "version": None, "cpe": None, "homepage": None, "license_type": None}
    tp_blocks = _find_blocks(text, "third_party")
    if not tp_blocks:
        out["first_party"] = True
        return out
    tp = tp_blocks[0]
    out["license_type"] = _top_level_scalar(tp, "license_type")

    # Modern schema: identifier { type: "Git" value: "..." version: "..." }
    for ident in _find_blocks(tp, "identifier"):
        itype = (_scalar(ident, "type") or "").lower()
        if itype == "git" and not out["git_url"]:
            out["git_url"] = _scalar(ident, "value")
            out["version"] = _scalar(ident, "version") or out["version"]
        elif itype == "cpe" and not out["cpe"]:
            out["cpe"] = _scalar(ident, "value")

    # Legacy schema: url { type: GIT value: "..." } + sibling version: "..."
    for url in _find_blocks(tp, "url"):
        utype = (_scalar(url, "type") or "").upper()
        if utype == "GIT" and not out["git_url"]:
            out["git_url"] = _scalar(url, "value")
        elif utype == "HOMEPAGE" and not out["homepage"]:
            out["homepage"] = _scalar(url, "value")
    if not out["version"]:
        out["version"] = _top_level_scalar(tp, "version")

    # security { tag: "NVD-CPE2.3:cpe:/a:vendor:product:version" }
    for sec in _find_blocks(tp, "security"):
        tag = _scalar(sec, "tag")
        if tag and "cpe:" in tag.lower() and not out["cpe"]:
            out["cpe"] = tag.split(":", 1)[1] if tag.upper().startswith("NVD-CPE2.3:") else tag

    if not out["homepage"]:
        out["homepage"] = _top_level_scalar(tp, "homepage")
    return out


# --------------------------------------------------------------------------
# classification + emission
# --------------------------------------------------------------------------

GITHUB_RE = re.compile(r"^(?:https?://|git://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", re.I)
VERSION_NUM_RE = re.compile(r"(\d+(?:[._]\d+)+)")


def github_coords(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    m = GITHUB_RE.match(url.strip())
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def numeric_version(tag: str | None) -> str | None:
    """curl-8_12_1 -> 8.12.1, v1.6.44 -> 1.6.44, 2.13.2 -> 2.13.2; None if no
    confident dotted/underscored numeric core exists (e.g. '76' stays None)."""
    if not tag:
        return None
    m = VERSION_NUM_RE.search(tag)
    return m.group(1).replace("_", ".") if m else None


def cpe23(cpe: str, version_override: str | None) -> str:
    """Normalize a 2.2-style `cpe:/a:vendor:product:version` (or an existing
    2.3 string) to CPE 2.3, optionally overriding the version with the
    currently pinned one (AOSP's NVD tags are often stale)."""
    parts = None
    if cpe.startswith("cpe:2.3:"):
        parts = cpe.split(":")
        # ['cpe','2.3',part,vendor,product,version,...]
        head, vendor, product = parts[2], parts[3], parts[4]
        version = parts[5] if len(parts) > 5 else "*"
    elif cpe.startswith("cpe:/"):
        body = cpe[len("cpe:/"):]
        segs = body.split(":")
        head = segs[0]
        vendor = segs[1] if len(segs) > 1 else "*"
        product = segs[2] if len(segs) > 2 else "*"
        version = segs[3] if len(segs) > 3 else "*"
    else:
        return cpe
    if version_override:
        version = version_override
    return f"cpe:2.3:{head}:{vendor}:{product}:{version}:*:*:*:*:*:*:*"


HEX_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)


def suspicious_version(tag: str) -> str | None:
    """Pin shapes observed not to resolve as git tags or not to match CVE data
    (observed on app.fossa.com, 2026-11-04, fossa-cli 3.20.4; re-check when FOSSA's
    matcher changes): a bare number with no
    separators is usually not a real tag (ICU pins `76`; the real tag is
    `release-76-1`), and any numeric segment > 9999 (date-style tags like
    `20240116` or `edk2-stable202311`) is rejected as a version by FOSSA's
    vuln matcher. Commit SHAs are fine — but an ALL-DIGIT string is never
    treated as a SHA, or the hex guard would swallow 8-digit dates
    (`20240116` is a valid hex string) and make the date rule unreachable.
    Shape table: `76`→bare number, `20240116`→date-style, `1234567`→date-style
    (single segment > 9999), `v20240116`→date-style, `deadbeef`→None (SHA),
    `v1.6.44`→None, `3.7`→None. Returns the reason, or None if resolvable."""
    if HEX_SHA_RE.match(tag) and not tag.isdigit():
        return None
    if any(int(seg) > 9999 for seg in re.findall(r"\d+", tag)):
        return "date-style segment > 9999 did not match CVE version data (observed 2026-11-04)"
    if re.fullmatch(r"\d+", tag):
        return "bare number is unlikely to be a real git tag"
    return None


def classify(entries: list[dict]) -> list[dict]:
    for e in entries:
        e.setdefault("note", "")
        if e.get("first_party"):
            e["tier"] = 0
            continue
        gh = github_coords(e["git_url"])
        if gh and e["version"]:
            reason = suspicious_version(e["version"])
            if reason:
                e["tier"] = 2
                e["note"] = f"demoted from tier 1: {reason}; map to a real upstream tag by hand"
            else:
                e["tier"] = 1
                e["gh"] = gh
        elif e["cpe"] or (e["git_url"] and e["version"]):
            e["tier"] = 2
        else:
            e["tier"] = 3
    return entries


def emit_fossa_deps(entries: list[dict], pilot: int | None) -> str:
    tier1 = [e for e in entries if e["tier"] == 1]
    if pilot:
        tier1 = tier1[:pilot]
    lines = [
        "# Generated by aosp_metadata_scan.py — AOSP METADATA -> referenced git deps.",
        "# Names are lowercase on purpose: git locators that differ only in case are distinct components",
        "# in FOSSA (observed 2026-11-04: DaveGamble/cJSON and davegamble/cjson came back as two rows).",
        "# Versions are the upstream tag or commit AOSP pins (external_updater keeps them current).",
        "",
        "referenced-dependencies:",
    ]
    for e in tier1:
        owner, repo = e["gh"]
        lines.append("- type: git")
        lines.append(f"  name: github.com/{owner}/{repo}")
        lines.append(f"  version: {json.dumps(e['version'])}")
    if skipped_paths:
        lines += ["", "METADATA files NOT scanned because a path segment is on the skip-list (move them, or edit SKIP_DIRS, if they are real components):", ""]
        lines += [f"- `{p}`" for p in sorted(skipped_paths)]
    lines.append("")
    return "\n".join(lines)


def pilot_cohort(entries: list[dict], pilot: int) -> list[dict]:
    """The pilot gate exists to prove git fetch + CVE population on a new
    instance, so both lanes slice the SAME cohort: the first N tier-1 entries
    in walk order (identical to the fossa-deps slice), topped up with
    CPE-bearing tier-2 entries (they exercise the CPE lane) if tier 1 runs
    short."""
    cohort = [e for e in entries if e["tier"] == 1][:pilot]
    if len(cohort) < pilot:
        cohort += [e for e in entries if e["tier"] == 2 and e["cpe"]][: pilot - len(cohort)]
    return cohort


def emit_cyclonedx(entries: list[dict], project_name: str, project_version: str,
                   pilot: int | None = None) -> str:
    pool = pilot_cohort(entries, pilot) if pilot else entries
    third_party = sorted((x for x in pool if x["tier"] in (1, 2, 3)), key=lambda x: x["name"])
    seen_names: dict[str, str] = {}
    components = []
    for e in third_party:
        if e["name"] in seen_names:
            print(f"warn: duplicate METADATA name {e['name']!r} "
                  f"({seen_names[e['name']]} and {e['path']}) — both kept, distinct bom-refs",
                  file=sys.stderr)
        seen_names.setdefault(e["name"], e["path"])
        comp = {
            # bom-ref from the file path, unique by construction (METADATA
            # names repeat across nested third_party trees).
            "bom-ref": "pkg-" + re.sub(r"[^A-Za-z0-9._-]", "-", e["path"].removesuffix("/METADATA")),
            "type": "library",
            "name": e["name"],
            "version": e["version"] or "unknown",
        }
        if e["tier"] == 1:
            owner, repo = e["gh"]
            comp["purl"] = f"pkg:github/{owner}/{repo}@{e['version']}"
        if e["cpe"]:
            comp["cpe"] = cpe23(e["cpe"], numeric_version(e["version"]))
        refs = []
        if e["git_url"]:
            refs.append({"type": "vcs", "url": e["git_url"]})
        elif e["homepage"]:
            refs.append({"type": "website", "url": e["homepage"]})
        if refs:
            comp["externalReferences"] = refs
        components.append(comp)
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [{"vendor": "FOSSA", "name": "aosp_metadata_scan", "version": "1.0.0"}],
            "component": {
                "bom-ref": f"aosp-{project_name}",
                "type": "operating-system",
                "name": project_name,
                "version": project_version,
            },
        },
        "components": components,
        "dependencies": [
            {"ref": f"aosp-{project_name}", "dependsOn": [c["bom-ref"] for c in components]}
        ],
    }
    return json.dumps(bom, indent=2) + "\n"


def emit_coverage(entries: list[dict], root_display: str, skipped_paths: list[str] | None = None) -> str:
    counts = {t: sum(1 for e in entries if e["tier"] == t) for t in (0, 1, 2, 3)}
    lines = [
        "# AOSP METADATA coverage report",
        "",
        f"Scanned root: `{root_display}`",
        f"METADATA files parsed: {len(entries)}",
        f"METADATA files skipped by the directory skip-list ({', '.join(sorted(SKIP_DIRS))}): {len(skipped_paths or [])}",
        "",
        "Tier-1 verification step (run after the upload): "
        "`GET /api/revisions/<url-encoded revision locator>/dependencies` and assert every "
        "row's `resolved` is true — the revision-level `dependency_count` does NOT tell you "
        "whether a pin actually resolved.",
        "",
        "| Tier | Meaning | Count |",
        "| --- | --- | --- |",
        f"| 1 | github upstream + resolvable-shaped version -> fossa-deps git dep (license + CVE; verify `resolved` post-upload) | {counts[1]} |",
        f"| 2 | non-github upstream, demoted pin, and/or CPE -> SBOM inventory (CVE via CPE where present; **no license data**) | {counts[2]} |",
        f"| 3 | no upstream version -> SBOM inventory only, needs human | {counts[3]} |",
        f"| 0 | first-party METADATA (no third_party block), skipped — paths listed below for audit | {counts[0]} |",
        "",
        "| Component | Tier | Upstream | Version | CPE | AOSP license_type | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for e in sorted(entries, key=lambda x: (x["tier"], x["name"])):
        if e["tier"] == 0:
            continue
        cpe = cpe23(e["cpe"], numeric_version(e["version"])) if e["cpe"] else ""
        lines.append(
            f"| {e['name']} | {e['tier']} | {e.get('git_url') or e.get('homepage') or ''} "
            f"| {e.get('version') or ''} | {cpe} | {e.get('license_type') or ''} | {e.get('note') or ''} |"
        )
    first_party = [e for e in entries if e["tier"] == 0]
    if first_party:
        lines += ["", "First-party-classified METADATA (audit these — a parse miss lands here):", ""]
        lines += [f"- `{e['path']}`" for e in sorted(first_party, key=lambda x: x["path"])]
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path, help="AOSP checkout root")
    ap.add_argument("--out-dir", type=Path, default=Path("."), help="where to write outputs")
    ap.add_argument("--project-name", default="aosp", help="SBOM root component name")
    ap.add_argument("--project-version", default=_dt.date.today().isoformat(), help="SBOM root component version")
    ap.add_argument("--pilot", type=int, default=None, metavar="N",
                    help="pilot gate: emit only the first N components into BOTH "
                         "fossa-deps.yml (tier 1) and the CycloneDX")
    args = ap.parse_args()

    if args.pilot is not None and args.pilot < 1:
        print("error: --pilot must be >= 1", file=sys.stderr)
        return 2

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    entries = []
    skipped_paths: list[str] = []
    for path in sorted(root.rglob("METADATA")):
        # Skip-list applies to directories INSIDE the checkout only, never to
        # ancestors of the root (a checkout under /build/out/... must scan).
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            skipped_paths.append(str(path.relative_to(root)))
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"warn: unreadable {path}: {exc}", file=sys.stderr)
            continue
        entry = parse_metadata(text, fallback_name=path.parent.name)
        entry["path"] = str(path.relative_to(root))
        entries.append(entry)

    if not entries:
        print("error: no METADATA files found under root", file=sys.stderr)
        return 1

    classify(entries)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "fossa-deps.yml").write_text(emit_fossa_deps(entries, args.pilot))
    (args.out_dir / "aosp-sbom.cdx.json").write_text(
        emit_cyclonedx(entries, args.project_name, args.project_version, args.pilot)
    )
    # display the root as the user gave it; the absolute path is a local
    # detail that doesn't belong in a shareable artifact
    (args.out_dir / "coverage.md").write_text(emit_coverage(entries, str(args.root), skipped_paths))

    t = lambda n: sum(1 for e in entries if e["tier"] == n)  # noqa: E731
    print(f"parsed={len(entries)} tier1={t(1)} tier2={t(2)} tier3={t(3)} first_party={t(0)} skipped={len(skipped_paths)}")
    print(f"wrote: {args.out_dir / 'fossa-deps.yml'}, {args.out_dir / 'aosp-sbom.cdx.json'}, {args.out_dir / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
