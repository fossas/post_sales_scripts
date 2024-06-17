import pandas as pd

# Load the CSV file
data = pd.read_csv('./CHMOpenSource.csv')

# Define the output YAML file path
output_yaml_path = './fossa-deps.yml'

# Create the YAML content
yaml_content = "remote-dependencies:\n"

# Function to append 'zipball/master' to URLs if they don't end with '.zip'
def adjust_url(url):
    if not url.endswith('.zip'):
        return url.rstrip('/') + '/zipball/master'
    return url

for _, row in data.iterrows():
    # Adjust URL if necessary
    adjusted_url = adjust_url(row['Source Link'])
    yaml_content += f"  - name: \"{row['Project / Source Module']}\"\n"
    yaml_content += f"    version: \"{row['Version']}\"\n"
    yaml_content += f"    url: \"{adjusted_url}\"\n"


# Write to the YAML file
with open(output_yaml_path, 'w') as file:
    file.write(yaml_content)

output_yaml_path
