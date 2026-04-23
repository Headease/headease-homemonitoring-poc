#!/bin/bash
# Delete Organization and Endpoints for a given URA from the LRZa HAPI FHIR server.
# Usage: ./scripts/cleanup-lrza.sh <ura-number>
# Example: ./scripts/cleanup-lrza.sh 90000382

set -euo pipefail

URA=${1:?Usage: $0 <ura-number>}
BASE=https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir
CERT=certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn-chain.crt
KEY=certificates/headease_nvi_20260202_145627.key

CURL="curl -s --cert $CERT --key $KEY"

echo "Cleaning up LRZa resources for URA: $URA"
echo "================================================"

# Delete Endpoints
echo ""
echo "Searching for Endpoints..."
ENDPOINT_IDS=$($CURL "$BASE/Endpoint?_format=json" | python3 -c "
import sys, json
bundle = json.load(sys.stdin)
for entry in bundle.get('entry', []):
    r = entry.get('resource', {})
    org = r.get('managingOrganization', {}).get('identifier', {})
    if org.get('value') == '$URA':
        print(r['id'])
" 2>/dev/null)

if [ -z "$ENDPOINT_IDS" ]; then
    echo "  No Endpoints found for URA $URA"
else
    for id in $ENDPOINT_IDS; do
        echo "  Deleting Endpoint/$id..."
        $CURL -X DELETE "$BASE/Endpoint/$id" -o /dev/null -w "  HTTP %{http_code}\n"
    done
fi

# Delete Organizations
echo ""
echo "Searching for Organizations..."
ORG_IDS=$($CURL "$BASE/Organization?identifier=http://fhir.nl/fhir/NamingSystem/ura|$URA&_format=json" | python3 -c "
import sys, json
bundle = json.load(sys.stdin)
for entry in bundle.get('entry', []):
    print(entry['resource']['id'])
" 2>/dev/null)

if [ -z "$ORG_IDS" ]; then
    echo "  No Organizations found for URA $URA"
else
    for id in $ORG_IDS; do
        echo "  Deleting Organization/$id..."
        $CURL -X DELETE "$BASE/Organization/$id" -o /dev/null -w "  HTTP %{http_code}\n"
    done
fi

echo ""
echo "Done."
