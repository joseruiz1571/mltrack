#!/usr/bin/env bash
# Demo 5 — Export a model as a schema-valid Governance Model Card.
cd "$(dirname "$0")" && source ./lib.sh

banner "mltrack — export a model as a Governance Model Card"
run "mltrack sample-data --count 5 --clear"
say "Register the model we care about."
run "mltrack add --name fraud-detector --vendor In-house --risk-tier critical --use-case 'Real-time fraud detection for wire transfers' --business-owner 'Risk Management' --technical-owner 'ML Platform' --deployment-date 2026-02-01 --environment prod --data-classification confidential --version 2.3.0"
say "An inventory row IS governance data. Make that literal: export a Model Card."
run "mltrack card export fraud-detector -o fraud-detector.card.json"
say "A portable, structured governance artifact:"
run "jq '{card_type, name: .metadata.name, uuid: .metadata.uuid, lifecycle: .metadata.lifecycle_status, provider: .model.provider, risk: .classification.risk_tier}' fraud-detector.card.json"
say "Validate it against the Governance Card Stack schema — a CI-ready gate."
run "mltrack card validate fraud-detector.card.json"
say "Inventory becomes interoperable governance data. That is the bridge."
rm -f fraud-detector.card.json
sleep 1
