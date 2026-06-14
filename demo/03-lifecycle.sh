#!/usr/bin/env bash
# Demo 3 — Full model lifecycle: register, review, retire (audit trail preserved).
cd "$(dirname "$0")" && source ./lib.sh

banner "mltrack — full model lifecycle"
run "mltrack sample-data --count 5 --clear"
say "Register a new model with full governance metadata."
run "mltrack add --name customer-churn-predictor --vendor In-house --risk-tier high --use-case 'Predicts churn likelihood for retention campaigns' --business-owner 'Marketing Analytics' --technical-owner 'ML Platform' --deployment-date 2026-01-15 --environment prod --data-classification confidential"
say "Record a completed model-risk review."
run "mltrack reviewed customer-churn-predictor --date today --notes 'Initial deployment review complete. Approved for production.'"
say "The next review date is auto-scheduled from the risk tier."
run "mltrack show customer-churn-predictor"
say "Later, deprecate it — the audit trail is preserved, not deleted."
run "mltrack update customer-churn-predictor --status deprecated -y"
sleep 1
