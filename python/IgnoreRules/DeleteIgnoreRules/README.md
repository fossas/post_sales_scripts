
# Ignore Rules Deletion Script

This script deletes ignore rules from the FOSSA API using issue IDs provided in a CSV file. 

## **** PLEASE USE CAUTION as this is a BULK DELETE script.

## Requirements

- Python 3.x
- `requests` library

## Installation

1. Clone the repository or download the script.
2. Ensure you have Python 3 installed on your system.
3. Install the `requests` library if you haven't already:

```sh
pip install requests
```

## Usage

Run the script with the following command:

```sh
python delete_ignore_rules.py <path_to_csv_file> <your_api_token>
```

- `<path_to_csv_file>`: Path to the CSV file containing the ignore rules.
- `<your_api_token>`: Your FOSSA API token.

## Example

```sh
python delete_ignore_rules.py IgnoreRules_vulnerability.csv your_actual_api_token_here
```

## Output

The script will generate a `DeleteResults.csv` file containing the results of the delete operations, with the following columns:
- `IssueId`
- `StatusCode`
- `ResponseText`

## CSV Format

The input CSV file should have the following format:

```
Id,Exception Title,Package Version,Created By,Note,Dependency Project Locator,Ignore Scope
<issue_id_1>,<exception_title_1>,<package_version_1>,<created_by_1>,<note_1>,<dependency_project_locator_1>,<ignore_scope_1>
<issue_id_2>,<exception_title_2>,<package_version_2>,<created_by_2>,<note_2>,<dependency_project_locator_2>,<ignore_scope_2>
...
```

Only the `Id` field is used by the script for the DELETE operations.

## Notes

- Make sure to replace the placeholder values with your actual data.
- Ensure your API token is kept secure and not shared publicly.

## License

This project is licensed under the MIT License.
