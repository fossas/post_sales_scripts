#   Prerequisites:
#   - Black Duck API token (user access token from Black Duck > My Access Tokens)
#   - Black Duck URL
#   - FOSSA API token
#   - FOSSA CLI installed
#
#   Usage:
#   - Set the environment variables:
#     - export BLACKDUCK_URL="https://yourblackduckdomain.blackducksoftware.com"
#     - export BLACKDUCK_TOKEN="<black duck API token>"
#     - export FOSSA_API_KEY="<fossa api key>"
#
#   - Run the script:
#     - python3 bd_to_fossa.py             # full run (resumes from the CSV if present)
#     - python3 bd_to_fossa.py --dry-run   # enumerate only; no reports created, nothing uploaded
#     - python3 bd_to_fossa.py --sbom-type SPDX_23
#     - python3 bd_to_fossa.py --help
#
#   Resumability:
#     Every (project, version) row is written to the CSV as it finishes. On the next run,
#     rows with status "success" are skipped; everything else is retried. Delete the CSV
#     (or pass --fresh) to start over.
#
#   Verified against:
#   - blackducksoftware/hub-rest-api-python  examples/client/generate_sbom.py  (official)
#   - philips-software/blackduck-report-action get-blackduck-report.sh        (maintained, 2025+)

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# CLI
# ============================================================

parser = argparse.ArgumentParser(description="Migrate Black Duck project versions to FOSSA via SBOM export/import.")
parser.add_argument("--dry-run", action="store_true",
                    help="Enumerate projects/versions and apply filters, but do not create reports or upload to FOSSA.")
parser.add_argument("--fresh", action="store_true",
                    help="Ignore any existing results CSV and start from scratch.")
parser.add_argument("--no-reuse", action="store_true",
                    help="Always generate a new SBOM report even if a completed one already exists.")
parser.add_argument("--sbom-type", default="CYCLONEDX_16",
                    choices=["SPDX_22", "SPDX_23", "SPDX_30", "CYCLONEDX_13", "CYCLONEDX_14", "CYCLONEDX_15", "CYCLONEDX_16"])
parser.add_argument("--fossa-prefix", default="blackduck/",
                    help="Prefix for the FOSSA project ID (default: 'blackduck/').")
parser.add_argument("--page-limit", type=int, default=100,
                    help="Black Duck page size (server cap is 1000).")
parser.add_argument("--csv", default="./fossa_sbom_migration_results.csv")
parser.add_argument("--sbom-dir", default="./sboms")
parser.add_argument("--log-dir", default="./fossa_logs",
                    help="Where to write per-version FOSSA CLI stdout/stderr.")
args = parser.parse_args()

# ============================================================
# Environment Variables (must be set before running)
# ============================================================

BLACKDUCK_URL = os.environ["BLACKDUCK_URL"].rstrip("/")
BLACKDUCK_TOKEN = os.environ["BLACKDUCK_TOKEN"]   # API token, NOT a bearer token

SBOM_OUTPUT_DIR = args.sbom_dir
CSV_OUTPUT_FILE = args.csv
FOSSA_LOG_DIR = args.log_dir
PAGE_LIMIT = min(args.page_limit, 1000)
SBOM_TYPE = args.sbom_type
FOSSA_PREFIX = args.fossa_prefix
DRY_RUN = args.dry_run
REUSE_EXISTING_REPORTS = not args.no_reuse
SBOM_POLL_SECONDS = 5
SBOM_POLL_TIMEOUT = 15 * 60     # give up on a single report after 15 min
FOSSA_CLI_TIMEOUT = 30 * 60     # give up on a single `fossa sbom analyze` after 30 min

# sbomType -> "specification" string. Newer Black Duck releases accept/expect
# `specification` on POST /sbom-reports; older ones ignore it and use sbomType.
SBOM_SPECIFICATION = {
    "SPDX_22": "SPDX-2.2",
    "SPDX_23": "SPDX-2.3",
    "SPDX_30": "SPDX-3.0",
    "CYCLONEDX_13": "CycloneDX-1.3",
    "CYCLONEDX_14": "CycloneDX-1.4",
    "CYCLONEDX_15": "CycloneDX-1.5",
    "CYCLONEDX_16": "CycloneDX-1.6",
}
SBOM_FILE_EXT = ".cdx.json" if SBOM_TYPE.startswith("CYCLONEDX") else ".spdx.json"

# ------------------------------------------------------------
# Optional filters  (all OFF by default — uncomment to enable)
#
# Each filter is a function (project, version) -> True to KEEP.
# Add any you want to FILTERS below.
# ------------------------------------------------------------
# SKIP_PHASES = {"ARCHIVED", "DEPRECATED"}
# def filter_phase(project, version):
#     return version.get("phase") not in SKIP_PHASES
#
# PROJECT_ALLOWLIST = {"my-project", "another-project"}
# def filter_project_allowlist(project, version):
#     return project.get("name") in PROJECT_ALLOWLIST
#
# PROJECT_NAME_REGEX = re.compile(r"^(payments|platform)-")
# def filter_project_regex(project, version):
#     return bool(PROJECT_NAME_REGEX.search(project.get("name", "")))
#
# MAX_VERSIONS_PER_PROJECT = 3   # keep only the N most recently created versions
# # (applied separately in main() — see the commented block there)

FILTERS = [
    # filter_phase,
    # filter_project_allowlist,
    # filter_project_regex,
]

# ------------------------------------------------------------
# Media types
#
# Black Duck versions every endpoint family with a custom media type and
# returns 406 if the Accept value isn't supported by *your* server release.
# The project-detail version has moved from -4 -> -5 -> -7 across releases,
# so rather than hardcode one, we try a list in order and fall back on 406.
# "application/json" asks for the newest external version and is what Black
# Duck's own Python client uses by default for GETs.
# ------------------------------------------------------------
PROJECT_ACCEPT_TYPES = [
    "application/json",
    "application/vnd.blackducksoftware.project-detail-7+json",
    "application/vnd.blackducksoftware.project-detail-5+json",
    "application/vnd.blackducksoftware.project-detail-4+json",
]
REPORT_ACCEPT_TYPES = [
    "application/vnd.blackducksoftware.report-4+json",
    "application/json",
]
REPORT_CONTENT_TYPE = "application/vnd.blackducksoftware.report-4+json"
ZIP_ACCEPT_TYPES = ["application/zip", "application/octet-stream", "*/*"]

os.makedirs(SBOM_OUTPUT_DIR, exist_ok=True)
os.makedirs(FOSSA_LOG_DIR, exist_ok=True)

# ============================================================
# Results CSV (also the resume checkpoint + metadata store)
# ============================================================

CSV_FIELDS = [
    # identity
    "project", "revision", "fossa_project", "status", "error",
    # what happened
    "sbom_path", "report_url", "report_reused", "fossa_url", "fossa_log",
    # SBOM validation
    "sbom_format", "sbom_spec_version", "component_count",
    # Black Duck metadata — for re-hydrating FOSSA via API later
    "bd_project_href", "bd_version_href",
    "bd_project_description", "bd_project_tier", "bd_project_owner",
    "bd_version_phase", "bd_version_distribution", "bd_version_nickname",
    "bd_version_released_on", "bd_version_created_at", "bd_version_license",
    "migrated_at",
]

# key: (project, revision) -> row dict
results: Dict[Tuple[str, str], Dict] = {}


def load_previous_results() -> None:
    if args.fresh or not os.path.exists(CSV_OUTPUT_FILE):
        return
    with open(CSV_OUTPUT_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # tolerate CSVs written by older versions of this script
            row = {k: row.get(k, "") for k in CSV_FIELDS}
            results[(row["project"], row["revision"])] = row
    done = sum(1 for r in results.values() if r["status"] == "success")
    print(f"Resuming: {len(results)} rows in {CSV_OUTPUT_FILE}, {done} already successful (will be skipped)")


def write_csv() -> None:
    tmp = CSV_OUTPUT_FILE + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in results.values():
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    os.replace(tmp, CSV_OUTPUT_FILE)   # atomic: never leaves a half-written CSV


def base_row(project: Dict, version: Dict) -> Dict:
    """Pre-populate a row with Black Duck metadata so it's captured even if the migration fails."""
    lic = version.get("license") or {}
    return {
        "project": project.get("name", ""),
        "revision": version.get("versionName", ""),
        "fossa_project": fossa_project_id(project.get("name", "")),
        "status": "",
        "error": "",
        "sbom_path": "",
        "report_url": "",
        "report_reused": "",
        "fossa_url": "",
        "fossa_log": "",
        "sbom_format": "",
        "sbom_spec_version": "",
        "component_count": "",
        "bd_project_href": project.get("_meta", {}).get("href", ""),
        "bd_version_href": version.get("_meta", {}).get("href", ""),
        "bd_project_description": project.get("description", "") or "",
        "bd_project_tier": project.get("projectTier", "") or "",
        "bd_project_owner": project.get("projectOwner", "") or "",
        "bd_version_phase": version.get("phase", "") or "",
        "bd_version_distribution": version.get("distribution", "") or "",
        "bd_version_nickname": version.get("nickname", "") or "",
        "bd_version_released_on": version.get("releasedOn", "") or "",
        "bd_version_created_at": version.get("createdAt", "") or "",
        "bd_version_license": lic.get("licenseDisplay", "") or "",
        "migrated_at": "",
    }

# ============================================================
# HTTP session with retries (429 / 5xx) — GET only.
# A retried POST to /sbom-reports could create duplicate reports.
# ============================================================

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )),
)

# ============================================================
# Black Duck Authentication
# ============================================================

_bearer_token: Optional[str] = None


def authenticate() -> str:
    """Exchange the Black Duck API token for a short-lived bearer token (~2h by default)."""
    global _bearer_token
    resp = _session.post(
        f"{BLACKDUCK_URL}/api/tokens/authenticate",
        headers={"Authorization": f"token {BLACKDUCK_TOKEN}"},
        timeout=60,
    )
    resp.raise_for_status()
    _bearer_token = resp.json()["bearerToken"]
    return _bearer_token


def _auth_header() -> Dict[str, str]:
    if _bearer_token is None:
        authenticate()
    return {"Authorization": f"Bearer {_bearer_token}"}


def bd_request(
    method: str,
    url: str,
    accept_types: List[str],
    content_type: Optional[str] = None,
    **kwargs,
) -> requests.Response:
    """
    Request with:
      - automatic re-auth on 401 (bearer token expired mid-run)
      - Accept-header fallback on 406 (server doesn't support that media type version)
    """
    last_406 = None
    for accept in accept_types:
        headers = {**_auth_header(), "Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type

        resp = _session.request(method, url, headers=headers, **kwargs)

        if resp.status_code == 401:
            authenticate()
            headers.update(_auth_header())
            resp = _session.request(method, url, headers=headers, **kwargs)

        if resp.status_code == 406:
            last_406 = resp
            continue  # try the next media type

        resp.raise_for_status()
        return resp

    last_406.raise_for_status()
    raise RuntimeError("unreachable")

# ============================================================
# Black Duck API Helpers
# ============================================================

def get_paginated(url: str, accept_types: List[str] = PROJECT_ACCEPT_TYPES) -> List[Dict]:
    """
    Walk a paginated collection using limit/offset.

    Stop conditions (whichever hits first):
      - we've collected totalCount items (when the server reports it)
      - a page comes back shorter than PAGE_LIMIT (official client's rule)
      - an empty page
    """
    items: List[Dict] = []
    offset = 0
    total: Optional[int] = None

    while True:
        resp = bd_request("GET", url, accept_types,
                          params={"limit": PAGE_LIMIT, "offset": offset}, timeout=60)
        data = resp.json()
        page = data.get("items", [])
        if total is None:
            total = data.get("totalCount")

        items.extend(page)

        if not page:
            break
        if total is not None and len(items) >= total:
            break
        if len(page) < PAGE_LIMIT:
            break

        offset += PAGE_LIMIT

    return items


def get_projects() -> List[Dict]:
    return get_paginated(f"{BLACKDUCK_URL}/api/projects")


def get_versions(project_href: str) -> List[Dict]:
    return get_paginated(f"{project_href}/versions")

# ============================================================
# SBOM Export
# ============================================================

def _absolutize(location: str) -> str:
    """Location is normally absolute; tolerate '/api/projects/...' or '/projects/...'."""
    if location.startswith("/"):
        if not location.startswith("/api/"):
            location = "/api" + location
        location = BLACKDUCK_URL + location
    return location


def find_existing_report(version_href: str) -> Optional[str]:
    """
    Look for an already-COMPLETED report of the right type on this version.
    Returns its URL, or None. Any error here just means "generate a new one".
    """
    try:
        reports = get_paginated(f"{version_href}/sbom-reports", REPORT_ACCEPT_TYPES)
    except requests.RequestException:
        # RequestException also covers RetryError, which the session raises
        # (instead of HTTPError) once 429/5xx retries are exhausted.
        return None

    wanted_spec = SBOM_SPECIFICATION.get(SBOM_TYPE, "")
    candidates = []
    for r in reports:
        if r.get("status") != "COMPLETED":
            continue
        if (r.get("reportFormat") or "JSON").upper() != "JSON":
            continue
        # Different BD releases expose the type under different keys.
        rtype = (r.get("sbomType") or r.get("specification") or r.get("reportType") or "")
        if rtype not in (SBOM_TYPE, wanted_spec):
            continue
        href = r.get("_meta", {}).get("href")
        if href:
            candidates.append((r.get("createdAt") or r.get("updatedAt") or "", href))

    if not candidates:
        return None
    candidates.sort(reverse=True)   # newest first
    return _absolutize(candidates[0][1])


def request_sbom(version_href: str) -> str:
    """POST {version}/sbom-reports -> report URL from the Location header."""
    body = {
        "reportFormat": "JSON",
        "reportType": "SBOM",
        "sbomType": SBOM_TYPE,
        "includeSubprojects": True,
    }
    spec = SBOM_SPECIFICATION.get(SBOM_TYPE)
    if spec:
        body["specification"] = spec

    resp = bd_request("POST", f"{version_href}/sbom-reports",
                      accept_types=["*/*"], content_type=REPORT_CONTENT_TYPE,
                      json=body, timeout=60)
    location = resp.headers.get("Location")
    if not location:
        raise RuntimeError(
            f"POST sbom-reports returned {resp.status_code} but no Location header. Body: {resp.text[:500]}"
        )
    return _absolutize(location)


def wait_for_sbom(report_url: str) -> Dict:
    """Poll the report until COMPLETED; return the report JSON."""
    deadline = time.time() + SBOM_POLL_TIMEOUT
    while True:
        data = bd_request("GET", report_url, REPORT_ACCEPT_TYPES, timeout=60).json()
        status = data.get("status")

        if status == "COMPLETED":
            return data
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"SBOM generation {status} for {report_url}. Response: {data}")
        if time.time() > deadline:
            raise TimeoutError(f"SBOM not ready after {SBOM_POLL_TIMEOUT}s (last status: {status}) for {report_url}")

        time.sleep(SBOM_POLL_SECONDS)


def _download_candidates(report_url: str, report_json: Dict) -> List[str]:
    """
    Order of preference:
      1. any _meta.links rel that looks like a download link (server-provided)
      2. {report}/download.zip  <- what the official example + Philips action use
      3. {report}/download      <- older/alternate form
    """
    base = report_url.rstrip("/")
    candidates: List[str] = []
    for link in report_json.get("_meta", {}).get("links", []):
        rel = (link.get("rel") or "").lower()
        if "download" in rel and link.get("href"):
            candidates.append(_absolutize(link["href"]))
    candidates.append(base + "/download.zip")
    candidates.append(base + "/download")
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def download_sbom(report_url: str, report_json: Dict, output_path: str) -> str:
    """
    Download the report (a .zip containing the SBOM .json) and extract the SBOM.
    Must request with a zip/binary Accept header, NOT the report-4+json type.
    """
    last_err: Optional[Exception] = None
    content: Optional[bytes] = None
    used_url = None

    for url in _download_candidates(report_url, report_json):
        try:
            resp = bd_request("GET", url, ZIP_ACCEPT_TYPES, timeout=300)
            content = resp.content
            used_url = url
            break
        except requests.HTTPError as e:
            last_err = e
            if e.response is not None and e.response.status_code in (404, 406, 415):
                continue
            raise

    if content is None:
        raise RuntimeError(f"All download URL forms failed for {report_url}: {last_err}")

    print(f"    Downloaded from: {used_url}")

    zip_path = output_path + ".zip"
    with open(zip_path, "wb") as f:
        f.write(content)

    if not zipfile.is_zipfile(zip_path):
        os.replace(zip_path, output_path)   # some instances return the JSON directly
        return output_path

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.endswith(".json")]
        if not members:
            raise RuntimeError(f"No JSON SBOM found in {zip_path}: {zf.namelist()}")
        members.sort()
        if len(members) > 1:
            print(f"    ⚠️  Zip contains {len(members)} JSON files {members}; using {members[0]!r}")
        with zf.open(members[0]) as src, open(output_path, "wb") as dst:
            dst.write(src.read())

    os.remove(zip_path)
    return output_path

# ============================================================
# SBOM validation
# ============================================================

class EmptySBOM(Exception):
    pass


def validate_sbom(path: str) -> Dict[str, str]:
    """
    Parse the SBOM and return {sbom_format, sbom_spec_version, component_count}.
    Raises ValueError on malformed input, EmptySBOM if there are no components.
    """
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if "bomFormat" in doc:                       # CycloneDX
        fmt = doc.get("bomFormat", "")
        spec = str(doc.get("specVersion", ""))
        count = len(doc.get("components") or [])
        if fmt != "CycloneDX":
            raise ValueError(f"unexpected bomFormat {fmt!r}")
    elif "spdxVersion" in doc:                   # SPDX 2.x
        fmt = "SPDX"
        spec = doc.get("spdxVersion", "")
        count = len(doc.get("packages") or [])
    elif "@context" in doc and "@graph" in doc:  # SPDX 3.0
        fmt = "SPDX"
        spec = "SPDX-3.0"
        count = sum(1 for n in doc["@graph"] if str(n.get("type", "")).endswith("Package"))
    else:
        raise ValueError("file is neither CycloneDX nor SPDX JSON")

    info = {"sbom_format": fmt, "sbom_spec_version": spec, "component_count": str(count)}
    if count == 0:
        raise EmptySBOM("SBOM has 0 components")
    return info

# ============================================================
# FOSSA SBOM Ingestion
# ============================================================

_FOSSA_URL_RE = re.compile(r"https://app\.fossa\.com/\S+")


def fossa_project_id(project_name: str) -> str:
    """
    FOSSA project ID. Keep it deterministic and locator-safe:
    prefix + name with whitespace collapsed to '-'.
    """
    safe = re.sub(r"\s+", "-", project_name.strip())
    return f"{FOSSA_PREFIX}{safe}"


def upload_to_fossa(sbom_path: str, project_name: str, revision: str, log_path: str) -> Optional[str]:
    """
    Run `fossa sbom analyze`, tee stdout/stderr to log_path, and return the
    FOSSA project/report URL if the CLI printed one.
    """
    cmd = [
        "fossa", "sbom", "analyze",
        "--project", fossa_project_id(project_name),
        # TODO(Carlos): `fossa sbom analyze` has no --title flag (checked up to fossa-cli v3.20.0),
        # so this makes every upload fail. Can you clarify the intent? Should we drop it,
        # or set the title afterwards via the FOSSA API?
        "--title", project_name,          # human-readable name in the FOSSA UI
        "--revision", revision,
        sbom_path,
    ]
    print("    ▶ Running:", " ".join(cmd))

    def write_log(stdout: str, stderr: str) -> None:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"$ {' '.join(cmd)}\n\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=FOSSA_CLI_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        # Partial output on TimeoutExpired can be bytes even with text=True.
        def as_text(out) -> str:
            return out.decode("utf-8", "replace") if isinstance(out, bytes) else (out or "")
        write_log(as_text(e.stdout), as_text(e.stderr))
        raise RuntimeError(f"fossa timed out after {FOSSA_CLI_TIMEOUT}s") from e

    write_log(proc.stdout, proc.stderr)

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
        raise RuntimeError(f"fossa exited {proc.returncode}: " + " | ".join(tail))

    m = _FOSSA_URL_RE.search(proc.stdout + "\n" + proc.stderr)
    return m.group(0) if m else None

# ============================================================
# Main
# ============================================================

_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f\s]+')


def safe_filename(project_name: str, version_name: str) -> str:
    """
    Filesystem-safe (incl. Windows) stem for this project/version.
    Sanitizing is lossy ('a b' and 'a/b' both become 'a_b'), so a short hash of
    the raw names is appended to keep stems unique.
    """
    stem = _UNSAFE_FILENAME_RE.sub("_", f"{project_name}__{version_name}").strip("._")[:150]
    digest = hashlib.sha1(f"{project_name}\0{version_name}".encode("utf-8")).hexdigest()[:8]
    return f"{stem}__{digest}"


def keep(project: Dict, version: Dict) -> bool:
    return all(f(project, version) for f in FILTERS)


def preflight() -> None:
    """Fail fast on missing FOSSA prerequisites, before generating any Black Duck reports."""
    if DRY_RUN:
        return
    problems = []
    if shutil.which("fossa") is None:
        problems.append("`fossa` CLI not found on PATH")
    if not os.environ.get("FOSSA_API_KEY"):
        problems.append("FOSSA_API_KEY is not set")
    if problems:
        sys.exit("Preflight failed:\n  - " + "\n  - ".join(problems))


def main():
    load_previous_results()
    authenticate()

    projects = get_projects()
    print(f"Found {len(projects)} Black Duck projects" + ("  [DRY RUN]" if DRY_RUN else ""))

    counts = {"queued": 0, "skipped_done": 0, "filtered": 0}

    for project in projects:
        project_name = project["name"]
        project_href = project["_meta"]["href"]

        print(f"\n📦 Project: {project_name}")
        versions = get_versions(project_href)

        # --- optional: keep only the N most recent versions -------------------
        # versions.sort(key=lambda v: v.get("createdAt", ""), reverse=True)
        # versions = versions[:MAX_VERSIONS_PER_PROJECT]
        # ----------------------------------------------------------------------

        for version in versions:
            version_name = version["versionName"]
            version_href = version["_meta"]["href"]
            key = (project_name, version_name)

            if not keep(project, version):
                counts["filtered"] += 1
                print(f"  └── Revision: {version_name}  (filtered out)")
                continue

            prev = results.get(key)
            if prev and prev.get("status") == "success":
                counts["skipped_done"] += 1
                print(f"  └── Revision: {version_name}  (already migrated, skipping)")
                continue

            row = base_row(project, version)
            if prev:  # keep anything useful from the failed attempt
                row["report_url"] = prev.get("report_url", "")
            results[key] = row

            file_stem = safe_filename(project_name, version_name)
            sbom_path = os.path.join(SBOM_OUTPUT_DIR, file_stem + SBOM_FILE_EXT)
            log_path = os.path.join(FOSSA_LOG_DIR, file_stem + ".log")
            row["sbom_path"] = sbom_path

            print(f"  └── Revision: {version_name}")

            if DRY_RUN:
                existing = find_existing_report(version_href) if REUSE_EXISTING_REPORTS else None
                row["report_url"] = existing or ""
                row["report_reused"] = "yes" if existing else "no"
                row["status"] = "dry-run"
                counts["queued"] += 1
                print(f"      would migrate -> {row['fossa_project']}@{version_name}"
                      + (f"  (reusing existing report)" if existing else "  (would generate new report)"))
                write_csv()
                continue

            try:
                # 1. find or create the report
                report_url = find_existing_report(version_href) if REUSE_EXISTING_REPORTS else None
                if report_url:
                    row["report_reused"] = "yes"
                    print(f"    Reusing existing completed report")
                else:
                    row["report_reused"] = "no"
                    report_url = request_sbom(version_href)
                row["report_url"] = report_url

                # 2. wait + download
                report_json = wait_for_sbom(report_url)
                download_sbom(report_url, report_json, sbom_path)

                # 3. validate
                try:
                    row.update(validate_sbom(sbom_path))
                except EmptySBOM as e:
                    row.update({"component_count": "0", "status": "empty_sbom", "error": str(e)})
                    print(f"    ⚠️  {e} — not uploading")
                    write_csv()
                    continue

                # 4. upload
                row["fossa_url"] = upload_to_fossa(sbom_path, project_name, version_name, log_path) or ""
                row["fossa_log"] = log_path
                row["status"] = "success"
                row["migrated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                counts["queued"] += 1

            except Exception as e:
                print(f"    ❌ Failed for project {project_name} revision {version_name}")
                if row.get("report_url"):
                    print(f"    Report URL: {row['report_url']}")
                print(f"    Error: {e}")
                row["status"] = "failure"
                row["error"] = str(e)
                row["fossa_log"] = log_path if os.path.exists(log_path) else ""

            write_csv()   # after every revision so progress survives a Ctrl+C

    print("\nSummary:", ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    # Outside the try: exiting here must not trigger write_csv() and clobber an existing CSV.
    preflight()
    try:
        main()
    finally:
        write_csv()
        print(f"\n📄 Results written to {CSV_OUTPUT_FILE}")
