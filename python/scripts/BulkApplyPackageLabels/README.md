# FOSSA Dependency Label Assignment Tool

This Python script automates the process of assigning labels to dependencies of a specific project revision in [FOSSA](https://fossa.com) using their public API.

## 🔧 What It Does

1. Fetches **all dependencies** of a given project revision using FOSSA's `/v2/revisions/:revision/dependencies` API.
2. Handles **pagination** to ensure all dependencies are retrieved (FOSSA returns max 50 per page).
3. Parses each dependency's `locator` to extract `packageId` and `packageVersion`.
4. Calls the `POST /api/package-label-assignments` API to assign a specific label to each dependency in the project.

## 🧪 Requirements

- Python 3.6+
- Internet access
- A valid FOSSA API token

## 📦 Installation

Clone the repository and install dependencies (if any).

## ▶️ Usage

```bash
python assign_labels_to_dependencies.py <API_TOKEN> <PROJECT_ID> <REVISION_HASH> <LABEL_ID>
```

### Example:

```bash
python assign_labels_to_dependencies.py sk_test_123 custom%2B40028%2FNewJavaReachability 64766b3fe... 100
```

### Parameters:

- `<API_TOKEN>`: Your FOSSA API token.
- `<PROJECT_ID>`: URL-encoded FOSSA project identifier. (e.g., `custom%2B40028%2FMyProject`)
- `<REVISION_HASH>`: The revision commit hash of the project.
- `<LABEL_ID>`: The ID of the label you want to apply.

## 💡 Notes

- The script uses the `project$revision` format when calling the dependencies API.
- For the label assignment, it only uses the decoded `project` portion (not the revision).
- This is especially helpful for bulk-tagging dependencies based on custom labels like "Dynamically Linked", "Reachability Exempt", etc.

## 🛠️ TODO

- Add retry logic for transient failures
- Support multi-threaded label assignments
- Export processed dependencies to a report file

---

Made with ❤️ to reduce manual work in compliance.
