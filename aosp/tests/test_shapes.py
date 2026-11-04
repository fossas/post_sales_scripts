#!/usr/bin/env python3
"""Scenario table for aosp_metadata_scan — run directly from this directory: python3 test_shapes.py

Also runs the generator over testdata/aosp-root (19 real AOSP METADATA files) and asserts the tier split.
Keep this directory OUT of any tree you scan: the fixtures are real METADATA files and would be read as components.

Each case here is a reviewer-caught or corpus-observed shape; if one of these
asserts fires, a silent-coverage bug came back."""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import aosp_metadata_scan as m

# --- suspicious_version: the guard-order table (an all-digit date must not pass the SHA test) ---------------------
CASES = {
    "76": "bare",            # ICU's real pin; the real tag is release-76-1
    "20240116": "date",      # 8-digit date IS valid hex — must not pass as SHA
    "1234567": "date",       # all-digit 7-char; single segment > 9999
    "v20240116": "date",
    "edk2-stable202311": "date",
    "deadbeef": None,        # genuine short hex SHA
    "7d77fb7fd66d8a5640618ad32c71fdeb7d3e02df": None,  # full SHA (corpus zlib)
    "v1.6.44": None,
    "curl-8_12_1": None,
    "R_2_5_0": None,
    "3.7": None,
    "libcap-2.69": None,
}
for tag, expect in CASES.items():
    got = m.suspicious_version(tag)
    if expect is None:
        assert got is None, f"{tag!r}: expected resolvable, got {got!r}"
    elif expect == "bare":
        assert got and "bare number" in got, f"{tag!r}: expected bare-number, got {got!r}"
    elif expect == "date":
        assert got and "date-style" in got, f"{tag!r}: expected date-style, got {got!r}"

# --- _find_blocks: both protobuf text block forms (brace and colon forms, incl. sqlite's) ------------
for form in ("security {", "security: {", "security  :  {"):
    text = form + ' tag: "NVD-CPE2.3:cpe:/a:x:y:1" }'
    assert m._find_blocks(text, "security"), f"block form not parsed: {form!r}"
assert m._find_blocks('third_party: { url: { type: GIT value: "u" } }', "third_party")

# --- parse_metadata: colon-form CPE recovery (real sqlite shape) -----------
sqlite_like = 'name: "SQLite"\nthird_party: {\n  security: {\n    tag: "NVD-CPE2.3:cpe:/a:sqlite:sqlite"\n  }\n  version: "3.42.0"\n}\n'
parsed = m.parse_metadata(sqlite_like, "sqlite")
assert parsed["cpe"] == "cpe:/a:sqlite:sqlite", parsed
assert parsed["version"] == "3.42.0", parsed
assert not parsed.get("first_party"), "colon-form third_party misread as first-party"

# --- CPE version refresh (stale AOSP security tags refreshed from the pinned tag) ----------------------
assert m.cpe23("cpe:/a:haxx:curl:7.87.0", m.numeric_version("curl-8_12_1")) == \
    "cpe:2.3:a:haxx:curl:8.12.1:*:*:*:*:*:*:*"

# --- pilot cohort: both lanes slice the same components -------------
entries = m.classify([
    {"name": n, "git_url": f"https://github.com/o/{n}", "version": "v1.0.0",
     "cpe": None, "homepage": None, "license_type": None, "path": f"external/{n}/METADATA"}
    for n in ("a", "b", "c")
] + [
    {"name": "z-cpe", "git_url": None, "version": "1.2", "cpe": "cpe:/a:z:z:1.2",
     "homepage": None, "license_type": None, "path": "external/z/METADATA"},
])
cohort = m.pilot_cohort(entries, 2)
assert [e["name"] for e in cohort] == ["a", "b"], cohort
import json
bom = json.loads(m.emit_cyclonedx(entries, "p", "1", pilot=2))
assert sorted(c["name"] for c in bom["components"]) == ["a", "b"], bom["components"]
deps_yaml = m.emit_fossa_deps(entries, 2)
assert deps_yaml.count("type: git") == 2 and "github.com/o/a" in deps_yaml and "github.com/o/b" in deps_yaml

# --- the real-file corpus: the generator over testdata/aosp-root must reproduce the recorded tier split ---
_here = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as _out:
    _res = subprocess.run([sys.executable, os.path.join(_here, "..", "tools", "aosp_metadata_scan.py"),
                           "--root", os.path.join(_here, "testdata", "aosp-root"), "--out-dir", _out],
                          capture_output=True, text=True)
    assert _res.returncode == 0, _res.stderr
    _line = next(l for l in _res.stdout.splitlines() if l.startswith("parsed="))
    assert _line.startswith("parsed=19 tier1=8 tier2=9 tier3=2"), _line

# --- cpe23 keeps trailing fields; bom-refs stay unique after path sanitization ---
assert m.cpe23("cpe:2.3:a:vendor:product:1.0:beta:*:*:*:*:*:*", "2.0") == "cpe:2.3:a:vendor:product:2.0:beta:*:*:*:*:*:*", m.cpe23("cpe:2.3:a:vendor:product:1.0:beta:*:*:*:*:*:*", "2.0")
assert m.cpe23("cpe:/a:vendor:product:1.0:sp1:pro:en", None) == "cpe:2.3:a:vendor:product:1.0:sp1:pro:en:*:*:*:*"
assert m.cpe23("cpe:/a:vendor:product", None) == "cpe:2.3:a:vendor:product:*:*:*:*:*:*:*:*"
_u = m._ref_factory()
assert [_u("pkg-external-foo-bar"), _u("pkg-external-foo-bar"), _u("pkg-x")] == ["pkg-external-foo-bar", "pkg-external-foo-bar-2", "pkg-x"]

print("all shape scenarios pass; corpus: " + _line)
