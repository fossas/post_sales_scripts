
# Get Ignore Rules and Convert to CSV

This Python script fetches ignore rules from the FOSSA API and converts them into a CSV file. The CSV format allows for easy filtering, sorting & searching of Licensing & Security Ignore Rules.

## Prerequisites

- Python 3.x
- `requests` library

You can install the required library using pip:
```bash
pip install requests
```

## Usage

To use this script, you need to provide the following command-line arguments:

1. `category`: The category can be "licensing" or "vulnerability".
2. `token`: The FOSSA API key.

### Command Line Arguments

- `category`: The category of the issues to fetch (e.g., "licensing" or "vulnerability").
- `token`: Your FOSSA API key.

### Example

```bash
python GetIgnoreRules_CSV.py licensing your_fossa_api_key
```

## Description

The script performs the following actions:

1. Sends a GET request to the FOSSA API to fetch exceptions (ignore rules) based on the specified category.
2. Writes the fetched data into a CSV file named `IgnoreRules.csv`.

### CSV Fields

The CSV file will contain the following fields:

- `Id`
- `Exception Title`
- `Package Version`
- `Created By`
- `Note`
- `Dependency Project Locator`
- `Ignore Scope`

### Code Explanation

- The script uses the `argparse` module to handle command-line arguments.
- The `requests` library is used to interact with the FOSSA API.
- The data is written to a CSV file using the `csv` module.

## Sample Output

Upon successful execution, the script will print:
```
Created IgnoreRules_licensing.csv successfully.
```

And the ` IgnoreRules_licensing.csv` file will be created in the same directory as the script. For vulnerability Ignore rules; the file will be named as  IgnoreRules_vulnerability.csv.

## Notes

- Ensure that you have the necessary permissions and network access to make requests to the FOSSA API.
- The script is set to use default values for some fields if they are not present in the API response. You can modify these default values as needed.
