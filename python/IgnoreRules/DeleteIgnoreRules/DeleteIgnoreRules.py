import csv
import requests
import argparse

# Set up command line argument parsing
parser = argparse.ArgumentParser(description="Delete Ignore Rules from CSV")
parser.add_argument('csv_file', type=str, help='Path to the CSV file containing the Ignore Rules; ALL rules in the CSV will be deleted.')
parser.add_argument('token', type=str, help='The FOSSA API key')

args = parser.parse_args()

# Function to delete issue
def delete_issue(issue_id, token):
    url = f'https://app.fossa.com/api/v2/issues/exceptions/{issue_id}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    response = requests.delete(url, headers=headers)
    return response.status_code, response.text

# Read the CSV file and iterate through each row
delete_results = []

with open(args.csv_file, mode='r') as file:
    csv_reader = csv.DictReader(file)
    for row in csv_reader:
        issue_id = row['Id']
        status_code, response_text = delete_issue(issue_id, args.token)
        delete_results.append((issue_id, status_code, response_text))

# Save the results to a new CSV file
output_file = 'DeleteResults.csv'

with open(output_file, mode='w', newline='') as file:
    csv_writer = csv.writer(file)
    csv_writer.writerow(['IssueId', 'StatusCode', 'ResponseText'])
    csv_writer.writerows(delete_results)

print(f"Deletion results saved to {output_file}")
