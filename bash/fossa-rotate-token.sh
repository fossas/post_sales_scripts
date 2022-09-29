#!/bin/bash

# Script for rotating token

set -o errexit
set -o noglob
set -o nounset
set -o pipefail

if [ $# -eq 0 ]; then
	echo "usage: USER_ID=..."
	exit 1
fi

# Rather than put in proper logging, let's just use bash's debugging...
set -o xtrace

# SET OLD TOKEN VALUE
OLD_TOKEN_VALUE=$FOSSA_API_KEY

# SET USER_ID
USER_ID=$1

# SET NEW NAME OF TOKEN - It has to be a new name
NOW=$(date +"%m-%d-%y")
NEW_TOKEN_NAME=newy-company-service-token-${NOW}

# CREATE NEW TOKEN
curl --request POST "https://app.fossa.com/api/user/$USER_ID/api_token" \
	--header "Accept: application/json" \
	--header "Authorization: token $OLD_TOKEN_VALUE" \
	--form "name=$NEW_TOKEN_NAME" \
	--form "pushOnly="false"" \
	--compressed

# FIND NEW TOKEN
NEW_TOKEN_VALUE=$(curl "https://app.fossa.com/api/users/$USER_ID" \
	--header "authorization: token ${OLD_TOKEN_VALUE}" \
  --header "accept: */*" | jq -r --arg NEW_TOKEN_NAME "$NEW_TOKEN_NAME" '.tokens[] | select(.name==$NEW_TOKEN_NAME).token')

# SET NEW VALUE
export FOSSA_API_KEY=$NEW_TOKEN_VALUE

# DELETE OLD TOKEN
curl --request DELETE "https://app.fossa.com/api/user/$USER_ID/api_token" \
	--header "Accept: application/json" \
	--header "Authorization: token $NEW_TOKEN_VALUE" \
	--form "token=$OLD_TOKEN_VALUE" \
	--compressed

echo OK
