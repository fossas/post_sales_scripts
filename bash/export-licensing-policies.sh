#!/bin/bash

if [ $# -eq 0 ]; then
  echo "No api key in argument provided."
else
  response=$(curl -s -X GET 'https://app.fossa.com/api/policies' --header "Authorization: Bearer $1")

  if [ $? -eq 0 ]; then
    parsed_response=$(echo "$response" | jq --compact-output '.[] | select(.type == "LICENSING") | { policyId: .latestVersion.policyId, title: .title, createdAt: .latestVersion.createdAt, updatedAt: .updatedAt  }')

    echo "${parsed_response}" | while IFS= read -r line; do

      policyId=$(echo "${line}" | jq -r '.policyId')
      title=$(echo "${line}" | jq -r '.title' | sed 's/\///g')

      policy_response=$(curl -s -X GET "https://app.fossa.com/api/policies/${policyId}" --header "Authorization: Bearer $1")

      parsed_policy_response=$(echo "$policy_response" | jq '.rules | group_by(.type) | .[] | { type: .[0].type, licenseId: map(.licenseId) | sort }')
      echo "${parsed_policy_response}" > "policyId-${policyId}-policy-${title}.json"
    done
  else
    echo "Oh no. An error occurred while executing the policies GET request."
  fi
fi
