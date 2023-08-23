#!/bin/bash

org_name="insert-gh-org-name-here"
token="call-gh-pat-here"
page=1

while true; do
  repos=$(curl -s -H "Authorization: Bearer $token" "https://api.github.com/orgs/$org_name/repos?per_page=100&page=$page&type=private" | jq -r '.[].name')
  echo "Private repositories identified: \n $repos"

  # Create debug directory
  TIMESTAMP=$(date +"%m-%d-%Y")
  DEBUG_DIR=debug-files-$TIMESTAMP
  mkdir $DEBUG_DIR

  for repo in $repos; do
    echo "Cloning and analyzing private repo: $repo"

    git clone "https://github.com/$org_name/$repo.git" "$repo"
    if [ $? -eq 0 ]; then
      echo "Clone of $repo successful"
    else
      echo "Clone of $repo failed"
      exit 1
    fi

    # Run FOSSA Analysis
    fossa analyze $repo --fossa-api-key $FOSSA_API_KEY --debug
    # Probably need to refactor this if you need to use any flags

    # Check the exit code of the fossa analyze command
    if [ $? -ne 0 ]; then
      echo "FOSSA analysis failed"
      # Rename and move the debug and telemetry files
      mv fossa.debug.json.gz "failed-$repo-fossa.debug.json.gz"
      mv "failed-$repo-fossa.debug.json.gz" $DEBUG_DIR
      mv fossa.telemetry.json "failed-$repo-fossa.telemetry.json"
      mv "failed-$repo-fossa.telemetry.json" $DEBUG_DIR
    else
      echo "FOSSA analysis succeeded for $repo"
      mv fossa.debug.json.gz "success-$repo-fossa.debug.json.gz"
      mv "success-$repo-fossa.debug.json.gz" $DEBUG_DIR
      mv fossa.telemetry.json "success-$repo-fossa.telemetry.json"
      mv "success-$repo-fossa.telemetry.json" $DEBUG_DIR
    fi

    # Remove repository
    rm -rf $repo
  done

  # Check if there are more pages
  link_header=$(curl -I -s -H "Authorization: Bearer $token" "https://api.github.com/orgs/$org_name/repos?per_page=100&page=$page&type=private" | grep -i link)
  if [[ $link_header =~ .*rel=\"next\".* ]]; then
    ((page++))
  else
    break
  fi
done

echo "FOSSA Bulk Analysis Complete. See Debug directory for any failed analysis runs."
