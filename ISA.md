---
task: "mltrack README maintenance and Loom script"
project: mltrack
effort: E3
effort_source: classifier
phase: execute
progress: 0/32
mode: interactive
started: 2026-06-28T00:00:00Z
updated: 2026-06-28T00:00:00Z
---

## Problem

The mltrack README drifted from the code during the 2026-06-14 overnight card export/validate work. The badge was updated (641 tests) but body text in two places still says 566. The test categories table is missing the Governance Cards row and has wrong counts in several categories. The project structure section omits card_command.py, schemas/, services/, mlflow_adapter.py, discover_command.py, error_helpers.py, model_commands.py, and core/registry.py. The roadmap lists "Model Cards" under "On the Horizon" despite card export/validate being shipped. There is no Loom walkthrough, which leaves a hiring manager with no fast path to understanding the design decisions.

## Vision

A hiring manager who lands on the repo sees a README that matches the actual code exactly — test counts, file structure, roadmap status all true. They find a Loom link early, watch a 5-minute walkthrough that makes them believe the candidate has a coherent theory of governance (not just a tool), and leave knowing where mltrack fits in the broader 4-layer portfolio.

## Out of Scope

No code changes. No new features. No CI pipeline changes. No restructuring of the README beyond the specific stale sections identified. The Loom recording itself is Jose's task; this session delivers the script and the README placeholder.

## Principles

- Every number in the README must match the actual codebase — no aspirational counts.
- The Loom script is a thesis defense, not a product demo. Each command is evidence for a claim.
- The README serves two readers: hiring manager (top third) and practitioner evaluating it for adoption (rest).

## Constraints

- Python codebase — no changes to any .py file.
- Tests must still pass 641/641 after all README edits.
- git diff must show only README.md changes plus the new ISA.md and Loom script file.
- Loom script word count must support < 5 minutes at normal speaking pace (~700 words max).

## Goal

Fix all README staleness from the card export/validate work. Add a Loom embed placeholder near the top. Write a <5-minute hiring manager Loom script that argues "governance is a data problem" using mltrack as evidence. Verify 641 tests still pass.

## Criteria

- [ ] ISC-1: README line containing "566 tests covering all functionality" is replaced with "641 tests" — verified by Grep finding "641" at that location
- [ ] ISC-2: README project structure block "(566 tests)" is replaced with "(641 tests)" — verified by Grep
- [ ] ISC-3: Test categories table contains a "Governance Cards" row — verified by Grep for "Governance Cards"
- [ ] ISC-4: Test category rows sum to 641 — verified by manual arithmetic check
- [ ] ISC-5: Project structure cli/ block shows card_command.py — verified by Grep
- [ ] ISC-6: Project structure shows schemas/ directory — verified by Grep
- [ ] ISC-7: Project structure shows services/ directory — verified by Grep
- [ ] ISC-8: Project structure adapters/ block shows mlflow_adapter.py — verified by Grep
- [ ] ISC-9: Project structure cli/ shows discover_command.py — verified by Grep
- [ ] ISC-10: Project structure cli/ shows check_command.py — verified by Grep
- [ ] ISC-11: Roadmap contains a "Done: Governance Model Cards" section — verified by Grep
- [ ] ISC-12: Roadmap "On the Horizon" section does NOT mention "Model Cards" as future work — verified by Grep on the On the Horizon section
- [ ] ISC-13: Roadmap "On the Horizon" still covers System Cards and Agent Cards — verified by Grep
- [ ] ISC-14: README contains a Loom section with a placeholder URL — verified by Grep for "loom" or "Loom"
- [ ] ISC-15: Loom section appears in the top third of the README (before line 50) — verified by line number check
- [ ] ISC-16: Loom script file exists at ~/Desktop/mltrack-loom-script.md — verified by Read tool
- [ ] ISC-17: Loom script word count ≤ 700 words — verified by wc -w
- [ ] ISC-18: Loom script contains the phrase "governance is a data problem" or equivalent thesis — verified by Grep
- [ ] ISC-19: Loom script references SHA-256 or tamper evidence — verified by Grep
- [ ] ISC-20: Loom script references "governance overlay" or equivalent (not a duplicate registry) — verified by Grep
- [ ] ISC-21: Loom script references card export and governance-card-stack connection — verified by Grep
- [ ] ISC-22: Loom script references the 4-layer portfolio or mlassure — verified by Grep
- [ ] ISC-23: Loom script includes at least 4 distinct mltrack commands — verified by counting "mltrack " occurrences
- [ ] ISC-24: Loom script addresses SR 11-7 or regulatory examiner perspective — verified by Grep
- [ ] ISC-25: 641 tests pass after all README edits — verified by pytest run
- [ ] ISC-26: git diff shows no .py file changes — verified by git diff --name-only
- [ ] ISC-27: README badge still shows "641%20passing" — verified by Grep
- [ ] ISC-28: Anti: any "566" remaining in README body text — verified by Grep (must return no matches)
- [ ] ISC-29: Anti: "Model Cards" listed as future work in On the Horizon — verified by Grep in that section (must return no matches in future-tense context)
- [ ] ISC-30: Anti: project structure lists a file that doesn't exist in the actual src/ tree — verified by cross-check
- [ ] ISC-31: Anti: Loom section contains a hard-coded Loom URL (must be placeholder) — verified by Grep
- [ ] ISC-32: README renders as syntactically valid markdown (all table headers balanced) — verified by checking each edited table

## Test Strategy

| isc | type | check | threshold | tool |
|-----|------|-------|-----------|------|
| ISC-1 | text probe | Grep README.md for "641 tests covering" | 1 match | Grep |
| ISC-2 | text probe | Grep README.md for "(641 tests)" in structure block | 1 match | Grep |
| ISC-3 | text probe | Grep README.md for "Governance Cards" in table | 1 match | Grep |
| ISC-4 | arithmetic | Sum table column 2 values | equals 641 | manual |
| ISC-5 through ISC-13 | text probe | Grep for each item | ≥1 match each | Grep |
| ISC-14 | text probe | Grep README.md for "loom" case-insensitive | ≥1 match | Grep |
| ISC-15 | line number | Find Loom section line number | < 50 | Grep -n |
| ISC-16 | file existence | Read ~/Desktop/mltrack-loom-script.md | no error | Read |
| ISC-17 | word count | wc -w ~/Desktop/mltrack-loom-script.md | ≤ 700 | Bash |
| ISC-18 through ISC-24 | text probe | Grep loom script for key phrases | ≥1 match each | Grep |
| ISC-25 | test run | pytest --tb=short -q | 641 passed | Bash |
| ISC-26 | git diff | git diff --name-only | no .py files | Bash |
| ISC-27 | text probe | Grep README badge for "641%20passing" | 1 match | Grep |
| ISC-28 | negative probe | Grep README body for "566" | 0 matches | Grep |
| ISC-29 | negative probe | Grep On the Horizon section for "Model Cards" as future | 0 matches | Grep |
| ISC-30 | cross-check | Compare listed files to actual src/ tree | all exist | Bash |
| ISC-31 | negative probe | Grep Loom section for real loom.com URL | 0 matches | Grep |
| ISC-32 | syntax check | Check table pipe counts | all balanced | manual |

## Features

| name | description | satisfies | depends_on | parallelizable |
|------|-------------|-----------|------------|----------------|
| fix-test-counts | Update "566" to "641" in two README body locations | ISC-1, ISC-2, ISC-28 | none | true |
| rewrite-test-table | Replace test categories table with accurate per-category counts summing to 641 | ISC-3, ISC-4 | fix-test-counts | false |
| rewrite-project-structure | Update project structure block to match actual src/ tree | ISC-5 through ISC-10, ISC-30 | none | true |
| update-roadmap | Add Done:Governance Model Cards section; update On the Horizon | ISC-11, ISC-12, ISC-13, ISC-29 | none | true |
| add-loom-section | Add Loom embed placeholder near top of README | ISC-14, ISC-15, ISC-31 | none | true |
| write-loom-script | Write <5-min thesis-defense walkthrough script for hiring managers | ISC-16 through ISC-24 | none | true |
| verify | Run tests, git diff, check all criteria | ISC-25 through ISC-32 | all above | false |

## Decisions

- 2026-06-28: ApertureOscillation revealed the Loom structure should be a thesis defense (claim → evidence → system connection), not a product demo. Every command illustrates a claim.
- 2026-06-28: Test table rewritten with category groupings that accurately reflect file-level counts. Old groupings were written before several test files were split/added.
- 2026-06-28: Delegation floor relaxed via show-your-math — README text edits and script writing are inherently single-author textual work; Forge would add overhead with no quality improvement on mechanical text substitutions.
- 2026-06-28: Loom script file written to ~/Desktop/mltrack-loom-script.md (not committed to repo). Jose records independently and pastes the URL into the README placeholder.
