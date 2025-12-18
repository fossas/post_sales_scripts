#   Prerequisites:
#   - Black Duck API token
#   - Black Duck URL
#   - FOSSA API token
#   - FOSSA CLI installed

#   Usage:
#   - Set the environment variables:
#     - export BLACKDUCK_URL="http://yourblackduckdomain.blackducksoftware.com/"
#     - export BLACKDUCK_TOKEN="bd_pat_xxxxxxxxx"
#     - export FOSSA_API_KEY="fossa_xxxxxxxxx"
# 
#   - Run the script:
#     - python blackduck_to_fossa_sbom.py

import os
import time
import csv
import subprocess
import requests
from typing import List, Dict

# ============================================================
# Environment Variables (must be set before running)
# ============================================================
# export BLACKDUCK_URL=https://your-blackduck-instance
# export BLACKDUCK_TOKEN=xxxxx
# export FOSSA_API_KEY=xxxxx
# ============================================================

BLACKDUCK_URL = os.environ["BLACKDUCK_URL"].rstrip("/")
BLACKDUCK_TOKEN = os.environ["BLACKDUCK_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {BLACKDUCK_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

SBOM_OUTPUT_DIR = "./sboms"
CSV_OUTPUT_FILE = "./fossa_sbom_migration_results.csv"

os.makedirs(SBOM_OUTPUT_DIR, exist_ok=True)

results = []

# ============================================================
# Black Duck API Helpers
# ============================================================

def get_paginated(url: str) -> List[Dict]:
    items = []
    offset = 0
    limit = 100

    while True:
        resp = requests.get(
            f"{url}?limit={limit}&offset={offset}",
            headers=HEADERS,
            timeout=60,
        )
        resp.raise_for_status()

        page = resp.json().get("items", [])
        items.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return items


def get_projects() -> List[Dict]:
    return get_paginated(f"{BLACKDUCK_URL}/api/projects")


def get_versions(project_href: str) -> List[Dict]:
    return get_paginated(f"{project_href}/versions")

# ============================================================
# CycloneDX SBOM Export
# ============================================================

def request_cyclonedx_sbom(version_href: str) -> str:
    resp = requests.post(
        f"{version_href}/sbom-cyclonedx",
        headers=HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.headers["Location"]


def wait_for_sbom(task_url: str) -> str:
    while True:
        resp = requests.get(task_url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status == "COMPLETED":
            return data["sbomDownloadUrl"]
        elif status == "FAILED":
            raise RuntimeError(f"SBOM generation failed: {data}")

        time.sleep(3)


def download_sbom(download_url: str, output_path: str):
    resp = requests.get(download_url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)

# ============================================================
# FOSSA SBOM Ingestion
# ============================================================

def upload_to_fossa(sbom_path: str, project_name: str, revision: str):
    cmd = [
        "fossa",
        "sbom",
        "analyze",
        "--project",
        project_name,
        "--revision",
        revision,
        sbom_path,
    ]

    print("    ▶ Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

# ============================================================
# Main
# ============================================================

def main():
    projects = get_projects()
    print(f"Found {len(projects)} Black Duck projects")

    for project in projects:
        project_name = project["name"]
        project_href = project["_meta"]["href"]

        print(f"\n📦 Project: {project_name}")
        versions = get_versions(project_href)

        for version in versions:
            version_name = version["versionName"]
            version_href = version["_meta"]["href"]

            safe_filename = (
                f"{project_name}__{version_name}"
                .replace("/", "_")
                .replace(" ", "_")
            )

            sbom_path = os.path.join(
                SBOM_OUTPUT_DIR,
                f"{safe_filename}.cdx.json"
            )

            print(f"  └── Revision: {version_name}")

            try:
                task_url = request_cyclonedx_sbom(version_href)
                download_url = wait_for_sbom(task_url)
                download_sbom(download_url, sbom_path)

                upload_to_fossa(
                    sbom_path=sbom_path,
                    project_name=project_name,
                    revision=version_name,
                )

                results.append({
                    "project": project_name,
                    "revision": version_name,
                    "sbom_path": sbom_path,
                    "status": "success",
                })

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                results.append({
                    "project": project_name,
                    "revision": version_name,
                    "sbom_path": sbom_path,
                    "status": "failure",
                })

    write_csv()


def write_csv():
    with open(CSV_OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["project", "revision", "sbom_path", "status"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\n📄 Migration results written to {CSV_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
