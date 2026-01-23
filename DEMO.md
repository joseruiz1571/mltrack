# MLTrack Demo Scripts

Step-by-step commands for recording terminal demos with asciinema.

## Recording Setup

```bash
# Install asciinema
brew install asciinema

# Start recording
asciinema rec demo.cast

# When done, press Ctrl+D to stop
# Upload: asciinema upload demo.cast
# Or convert to GIF: agg demo.cast demo.gif
```

---

## Demo 1: Quick Start (2-3 minutes)

**Purpose**: Show the tool working from zero to useful in under 3 minutes.

```bash
# Clear any existing data and start fresh
mltrack sample-data --count 20 --clear

# View the dashboard
mltrack dashboard

# Press q to exit dashboard, then run compliance check
mltrack validate --all

# Show a specific model
mltrack show fraud-detector

# List all critical risk models
mltrack list --risk critical
```

---

## Demo 2: Full Model Lifecycle (3-4 minutes)

**Purpose**: Demonstrate adding, managing, and eventually retiring a model.

```bash
# Start with a clean slate
mltrack sample-data --count 5 --clear

# Add a new model (use flags for demo clarity)
mltrack add \
  --name "customer-churn-predictor" \
  --vendor "In-house" \
  --risk-tier high \
  --use-case "Predicts customer churn likelihood for retention campaigns" \
  --business-owner "Marketing Analytics Team" \
  --technical-owner "ML Platform" \
  --deployment-date 2025-01-15 \
  --environment prod \
  --data-classification confidential

# View the model we just created
mltrack show customer-churn-predictor

# List all models - should see our new one
mltrack list

# Check compliance - new model should pass
mltrack validate --model-id customer-churn-predictor

# Record a review
mltrack reviewed customer-churn-predictor --date today --notes "Initial deployment review completed. Model approved for production use."

# Show updated model with review info
mltrack show customer-churn-predictor

# Later: deprecate the model
mltrack update customer-churn-predictor --status deprecated -y

# Eventually: decommission it
mltrack delete customer-churn-predictor --soft --yes

# Verify it's decommissioned
mltrack show customer-churn-predictor
```

---

## Demo 3: Compliance Workflow (2-3 minutes)

**Purpose**: Show how compliance teams would use the tool for audits.

```bash
# Generate sample data with some overdue models
mltrack sample-data --count 15 --clear --overdue-percent 30

# Run compliance validation
mltrack validate --all

# Check just critical models
mltrack validate --risk critical

# Generate compliance report
mltrack report compliance

# Export for auditors
mltrack report compliance -f json -o compliance-report.json

# Show the JSON file
cat compliance-report.json | head -50

# Generate risk report
mltrack report risk
```

---

## Demo 4: Dashboard Features (2 minutes)

**Purpose**: Showcase the interactive dashboard capabilities.

```bash
# Generate diverse sample data
mltrack sample-data --count 25 --clear

# View full dashboard
mltrack dashboard

# (Press q to exit)

# Filter by risk tier
mltrack dashboard --risk critical

# Filter by vendor
mltrack dashboard --vendor Anthropic

# Filter by environment
mltrack dashboard --environment prod

# Combine filters
mltrack dashboard --risk high --environment prod
```

---

## Demo 5: Import/Export Workflow (2-3 minutes)

**Purpose**: Show bulk data operations for enterprise use.

```bash
# Start fresh
mltrack sample-data --count 5 --clear

# Export current inventory
mltrack export inventory-backup.json

# Show the JSON structure
cat inventory-backup.json | head -30

# Export as CSV
mltrack export inventory-backup.csv

# Show CSV
cat inventory-backup.csv

# Export only high-risk models
mltrack export high-risk-models.json --risk high

# Create a template for data entry
mltrack export template.csv --template

# Show template (headers only)
cat template.csv

# Clean up demo files
rm -f inventory-backup.json inventory-backup.csv high-risk-models.json template.csv
```

---

## Demo 6: Filtering and Search (1-2 minutes)

**Purpose**: Show the filtering capabilities for large inventories.

```bash
# Generate larger dataset
mltrack sample-data --count 30 --clear

# List all models
mltrack list

# Filter by risk
mltrack list --risk critical
mltrack list --risk high

# Filter by vendor
mltrack list --vendor Anthropic
mltrack list --vendor OpenAI

# Filter by environment
mltrack list --environment prod

# Combine filters
mltrack list --risk high --environment prod

# Pagination for large results
mltrack list --limit 10
mltrack list --limit 10 --offset 10

# Verbose output with all fields
mltrack list --verbose

# JSON output for scripting
mltrack list --json | head -20
```

---

## Demo 7: Review Management (2 minutes)

**Purpose**: Show the review scheduling and tracking features.

```bash
# Generate data with overdue reviews
mltrack sample-data --count 10 --clear --overdue-percent 50

# Check which models need reviews
mltrack validate --all

# Pick an overdue model and record its review
mltrack reviewed fraud-detector --date today --notes "Quarterly model validation completed. Performance metrics within acceptable range."

# Verify the review was recorded
mltrack show fraud-detector

# Check compliance again - should have one fewer failure
mltrack validate --all
```

---

## Tips for Recording

### Before Recording

1. Clear your terminal: `clear`
2. Resize terminal to a good width (100-120 chars)
3. Use a clean shell prompt
4. Have commands ready to copy/paste

### During Recording

1. Type at a readable pace (or use pre-typed commands)
2. Pause briefly after each command to show output
3. Add comments as you go: `# Now let's check compliance...`
4. Keep demos focused - one concept per recording

### After Recording

```bash
# Play back locally
asciinema play demo.cast

# Upload to asciinema.org
asciinema upload demo.cast

# Convert to GIF (requires agg)
# Install: cargo install agg
agg demo.cast demo.gif

# Or use svg-term for SVG output
# npm install -g svg-term-cli
svg-term --in demo.cast --out demo.svg
```

---

## Suggested Demo Set for Portfolio

| Demo | Duration | Purpose |
|------|----------|---------|
| Quick Start | 2 min | First impression, shows tool working |
| Model Lifecycle | 3 min | Deep dive into core functionality |
| Compliance Workflow | 2 min | Shows regulatory/audit use case |
| Dashboard | 1 min | Visual appeal, monitoring capability |

Total: ~8 minutes of demo content, can be trimmed to highlights for README.
