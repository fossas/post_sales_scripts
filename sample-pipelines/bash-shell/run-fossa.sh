#!/bin/bash

# Script for generating repositories

set -o errexit
set -o noglob
set -o nounset
set -o pipefail

# set key
export FOSSA_API_KEY=<api key>

# cd  <root directory of repository>

# download cli
curl -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/fossas/fossa-cli/master/install-latest.sh | bash

# check version
fossa --version

# run analysis
fossa analyze 

# run test
fossa test
