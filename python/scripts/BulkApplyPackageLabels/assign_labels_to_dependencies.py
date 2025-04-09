import requests
import urllib.parse
import json
import sys

# === Check & Parse Arguments ===
if len(sys.argv) != 5:
    print("Usage: python assign_labels_to_dependencies.py <API_TOKEN> <PROJECT_ID> <REVISION> <LABEL_ID>")
    print("Example: python script.py sk_test_123 custom%2B40028%2FNewJavaReachability 64766b3fe... 100")
    sys.exit(1)

API_TOKEN = sys.argv[1]
ENCODED_PROJECT = sys.argv[2]  # URL encoded
REVISION_HASH = sys.argv[3]
LABEL_ID = int(sys.argv[4])

# === Derived Values ===
REVISION_ID = f"{urllib.parse.unquote(ENCODED_PROJECT)}${REVISION_HASH}"
ENCODED_REVISION_ID = urllib.parse.quote_plus(REVISION_ID)
DECODED_PROJECT = urllib.parse.unquote(ENCODED_PROJECT)

# === CONFIG ===
BASE_URL = "https://app.fossa.com/api"
HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {API_TOKEN}",
    "content-type": "application/json"
}

COUNT_PER_PAGE = 50

# === DEBUG INFO ===
print("=== DEBUG: Configuration ===")
print(f"REVISION_ID (decoded): {REVISION_ID}")
print(f"ENCODED_REVISION_ID: {ENCODED_REVISION_ID}")
print(f"PROJECT_ID (decoded): {DECODED_PROJECT}")
print(f"LABEL_ID: {LABEL_ID}")
print("============================\n")

# === STEP 1: Fetch All Dependencies with Pagination ===
print(f"📦 Fetching dependencies for revision: {REVISION_ID}")
all_dependencies = []
page = 1

while True:
    url = f"{BASE_URL}/v2/revisions/{ENCODED_REVISION_ID}/dependencies?page={page}&count={COUNT_PER_PAGE}"
    print(f"🔄 Fetching page {page}...")
    response = requests.get(url, headers=HEADERS)
    print(f"GET Status Code: {response.status_code}")

    if response.status_code != 200:
        print("❌ Failed to fetch dependencies:")
        print(response.text)
        sys.exit(1)

    try:
        data = response.json()
        page_dependencies = data.get("dependencies", [])
    except Exception as e:
        print("❌ Failed to parse JSON response:")
        print(response.text)
        print("Error:", e)
        sys.exit(1)

    if not page_dependencies:
        print(f"✅ No more dependencies found after page {page}.")
        break

    print(f"✅ Retrieved {len(page_dependencies)} dependencies from page {page}")
    all_dependencies.extend(page_dependencies)
    page += 1

print(f"\n🔢 Total dependencies fetched: {len(all_dependencies)}\n")

# === STEP 2: Assign Label to Each Dependency ===
for index, dep in enumerate(all_dependencies):
    print(f"--- Processing Dependency {index + 1} ---")
    locator = dep.get("locator")
    print(f"Locator: {locator}")

    if not locator:
        print("⚠️ Skipping due to missing locator.")
        continue

    try:
        package_id, package_version = locator.split("$")
        print(f"Parsed packageId: {package_id}")
        print(f"Parsed packageVersion: {package_version}")
    except ValueError:
        print(f"❌ Invalid locator format (missing $): {locator}")
        continue

    payload = {
        "labelIds": [LABEL_ID],
        "scope": "project",
        "scopeId": DECODED_PROJECT,
        "packageId": package_id,
        "packageVersion": package_version
    }

    print("Payload to POST:")
    print(json.dumps(payload, indent=2))

    res = requests.post(f"{BASE_URL}/package-label-assignments", headers=HEADERS, data=json.dumps(payload))
    print(f"POST Status Code: {res.status_code}")
    
    if res.status_code in [200, 201]:
        print("✅ Label assigned successfully.\n")
    else:
        print(f"❌ Failed to assign label:")
        print(res.text)
        print("\n")

print("🎉 All dependencies processed.")
