# OCPQ analyses

The archived OCPQ queries and exports support reproduction of CSQ1–CSQ3 and the high-volume What-if analysis. OCPQ binds objects and events, applies event-selection and chronological constraints, and calculates elapsed-time labels. Python reads the exported CSV results, converts duration units, calculates descriptive statistics and generates the figures and tables.

## Contents

| Directory | Contents |
|---|---|
| [csq1_3_analysis](csq1_3_analysis/README.md) | Baseline CSQ1–CSQ3 queries, exports, scripts and results |
| [whatif_analysis](whatif_analysis/README.md) | Baseline/high-volume comparison and interval diagnostics |
| [ocpq_shared](ocpq_shared/) | Shared path and milestone queries and baseline milestone export |

The baseline and high-volume SQLite logs are maintained in the repository-root `data/` directory.

## Run

From the repository root, using Python 3.12:

```bash
python -m pip install -r analysis/ocpq/requirements.txt
python analysis/ocpq/csq1_3_analysis/scripts/run_analysis.py
python analysis/ocpq/whatif_analysis/scripts/reproduce.py
```

These commands produce six PDF figures and five CSV tables in the corresponding `results/` folders. Add `--latex` to either command to generate its LaTeX tables.

To repeat the query stage, load the corresponding SQLite log in OCPQ, import the saved JSON definitions, and export all result rows to the locations documented in each analysis guide. The baseline milestone export is shared by both analyses.
