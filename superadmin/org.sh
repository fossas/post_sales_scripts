#!/bin/bash

# Used by FOSSA administrators to switch between organizations. Requires
# superadmin privileges (FOSSA employees or on-premise customers only).

set -e
set -o pipefail

title=$1
endpoint="${2:-"https://app.fossa.com"}"

if [ -z "$FOSSA_API_KEY" ]; then
    echo "FOSSA_API_KEY not set" 1>&2
    exit 1
fi


# There's no API to get the caller's user ID, and it's not possible to extract a
# user ID from an API token. As a workaround, we get the list of users belonging
# to the current organization, and iterate through all of them. The current user
# is one that owns the same API token we're using.

users=$(curl --silent --fail --show-error --location "$endpoint"/api/users \
    --header "Authorization: Bearer $FOSSA_API_KEY")
user=$(jq --arg token "$FOSSA_API_KEY" '.[] | select(any(.tokens[]; .token == $token))' <<< $users)
userId=$(jq -r .id <<< $user)
echo "Current user: $(jq -r .email <<< $user) ($userId)" 1>&2
currentOrgTitle="$(jq -r .organization.title <<< $user)"
if [ "$currentOrgTitle" == "$title" ]; then
    echo "Already on organization \"$currentOrgTitle\", nothing to do" 1>&2
    exit 0
fi
echo "Current organization: \"$currentOrgTitle\" ($(jq -r .organization.id <<< $user))" 1>&2

if [ -z "$title" ]; then
    exit 0
fi

orgs=$(curl --silent --fail --show-error --location \
    --get --data-urlencode "title=$title" "$endpoint"/api/organizations \
    --header "Authorization: Bearer $FOSSA_API_KEY")
targetOrg=$(jq --arg t "$title" -r '.[] | select(.title == $t)'<<< "$orgs")

if [ -z "$targetOrg" ]; then
    echo "Organization \"$title\" not found." 1>&2
    exit 1
else
    targetOrgId=$(jq -r ".[0] | .id" <<< "$orgs")
    currentOrgId=$(jq -r .organization.id <<< $user)
    if [ $currentOrgId -eq $targetOrgId ]; then
        currentOrgTitle=$(jq -r .organization.title <<< $user)
        echo "Already on organization \"$currentOrgTitle\", nothing to do" 1>&2
        exit 0
    fi
    curl --silent --fail --show-error --location --request PUT "$endpoint/api/users/$userId" \
        --header "Authorization: Bearer $FOSSA_API_KEY" \
        --data "{\"organizationId\": $targetOrgId}" \
        --output /dev/null
    echo "Switched to organization \"$title\" ($targetOrgId)" 1>&2
fi
