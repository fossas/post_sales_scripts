import re
import yaml

# List to store extracted data
referenced_dependencies = []

# Regular expression to match different formats of referenceLocator
locator_pattern = re.compile(r'"referenceLocator": "pkg:([a-zA-Z-]+)/?([^@"]+)?@?([^,"]+)?"')

# cat <BD-SBPM-SPDX>.json | jq | grep referenceLocator > referenceLocatorFile.txt
# Open the input text file in read mode

with open('referenceLocatorFile.txt', 'r') as file:
    # Iterate through each line in the file
    for line in file:
        # Find all matching referenceLocator patterns in the line
        matches = re.findall(locator_pattern, line)
        for match in matches:
            # Extract name, version, and type from the match
            dep_type = match[0]
            name = match[1] if match[1] else ""
            version = match[2] if match[2] else ""

            if dep_type == 'golang':
               dep_type='go'
              
            if (dep_type != 'generic' and dep_type != 'deb') :
               # Add double quotes around version
               version = f"{version}"
               ver = '"{}"'.format(version)
               # Add extracted data to the list
               referenced_dependencies.append({
                  'name':name,
                  'version':ver,
                  'type':dep_type
               })

# Write the extracted data to a YAML file
with open('fossa-deps.yaml', 'w') as yaml_file:
    yaml.dump({'referenced-dependencies': referenced_dependencies}, yaml_file)

print("Data has been written to fossa-deps.yaml.")
