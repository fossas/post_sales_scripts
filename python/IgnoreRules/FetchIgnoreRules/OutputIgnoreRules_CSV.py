import requests
import csv
import argparse

# Set up command line argument parsing
parser = argparse.ArgumentParser(description="Convert Ignore Rules into CSV")
parser.add_argument('category', type=str, help='Category can be "licensing" or "vulnerability"')
parser.add_argument('token', type=str, help='The FOSSA API key')

args = parser.parse_args()

# Main function
def main(token, category):
    url = 'https://app.fossa.com/api/v2/issues/exceptions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    params = {
        'filters[category]': category,
        'category': category
    }
    data = {}

    # Sending GET request
    response = requests.get(url, headers=headers, params=params, json=data)

    if response.status_code == 200:
        output_file_name = f'IgnoreRules_{category}.csv'
        print(f"Created {output_file_name} successfully.")
        json_response = response.json()
        
        # Open a CSV file to write the data
        with open(output_file_name, mode='w', newline='') as csv_file:
            fieldnames = ['Id', 'Exception Title', 'Package Version', 'Created By', 'Note', 'Dependency Project Locator', 'Ignore Scope']  # Add the necessary field names here
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()

            # Iterate through response to fetch ids and other required data
            for issue in json_response['exceptions']:
                issue_id = issue['id']
                exceptionTitle = issue.get('exceptionTitle', 'exceptionTitle') 
                note = issue.get('note', 'note') 
                dependencyProjectLocator = issue.get('dependencyProjectLocator', 'dependencyProjectLocator') 
                ignoreScope = issue.get('ignoreScope', 'default_value') 
                packageScope = issue.get('packageScope', 'default_value')  
                createdBy = issue.get('createdBy', 'default_value')  

                writer.writerow({
                    'Id': issue_id,
                    'Exception Title': exceptionTitle,
                    'Package Version': packageScope,
                    'Dependency Project Locator': dependencyProjectLocator,
                    'Ignore Scope': ignoreScope,
                    'Created By': createdBy,
                    'Note': note
                })
    else:
        print(f"Request failed with status code {response.status_code}.")

if __name__ == "__main__":
    main(args.token, args.category)
