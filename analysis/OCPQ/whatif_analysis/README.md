# High-volume What-if analysis

This analysis reproduces the baseline/high-volume comparison in Section 4.3.5: Table 4.14 and Figures 4.11–4.12.

## Run

From the repository root:

```bash
python -m pip install -r analysis/OCPQ/requirements.txt
python analysis/OCPQ/whatif_analysis/scripts/reproduce.py
```

Add `--latex` to generate the LaTeX comparison table.

| Thesis item | Output under `results/` |
|---|---|
| Table 4.14: overall scenario comparison | `overall_comparison.csv` |
| Figure 4.11: stage comparison | `stage_comparison.pdf` |
| Figure 4.12: diagnostic comparison | `interval_diagnostics.pdf` |

## Inputs

Paths below are relative to `analysis/OCPQ/whatif_analysis/`.

| Input | Contents |
|---|---|
| `../../../data/intangible_asset_ocel2.sqlite` | Baseline log for OCPQ |
| `../../../data/intangible_asset_whatif_ocel2.sqlite` | High-volume log for OCPQ |
| `../ocpq_shared/queries/path.json` | Shared submission-to-posting path query |
| `../ocpq_shared/queries/milestone.json` | Shared five-milestone query |
| `queries/diagnostic.json` | Diagnostic parent node and review/acceptance child nodes |
| `../ocpq_shared/baseline_milestone.csv` | Baseline milestone export, 25 posted Requirements |
| `data/ocpq/high_volume/milestone.csv` | High-volume milestone export, 2,155 posted Requirements |
| `data/ocpq/baseline/diagnostic.csv` | Baseline diagnostic export, 25 rows |
| `data/ocpq/high_volume/diagnostic.csv` | High-volume diagnostic export, 2,155 rows |
| `data/scenario_summary.csv` | Archived submitted counts, arrival spans and drain-down values reported in Table 4.14 |

Table 4.14 combines posted counts and duration summaries calculated from the OCPQ exports with log-level descriptors from `scenario_summary.csv`. The table's `source` column identifies the source of each measure.

## OCPQ query stage

Load each scenario's SQLite log in OCPQ and execute the shared milestone query and `queries/diagnostic.json`. Export all root-node bindings, including Requirement/event IDs, duration labels and `Satisfied`. Diagnostic exports also retain `nr` and `na`. Save the baseline milestone result in the shared location and the other exports at the paths above.

The milestone query binds five chronologically ordered events through the same Requirement. Its four successive stage labels sum to its end-to-end label.

The diagnostic query retains those milestones and adds quotation evaluation, contract-need checking and deliverable receipt. Child A binds *Review Requirement* through the same Requirement, at or after submission and before *Obtain Quotations*. The earliest and latest eligible reviews define the first and final review. Child B binds *Perform Business And Technical Acceptance* at or after *Receive Contract Deliverable* and no later than verification. The earliest eligible event defines the first acceptance attempt. Both child sets must be nonempty.

| Label | Diagnostic interval |
|---|---|
| `d1` | Submit Requirement to first eligible review |
| `d2` | Final eligible review to Obtain Quotations |
| `d3` | Obtain Quotations to Evaluate And Select Quotation |
| `d4` | Check Contract Need to Create Purchase Order |
| `d5` | Create Purchase Order to Receive Contract Deliverable |
| `d6` | Receive Contract Deliverable to first eligible acceptance |

The JSON contains the exact bindings, child-set constraints and CEL duration expressions. These intervals are selected diagnostic windows within completed lifecycles rather than a complete end-to-end decomposition.

## Statistics

Python reads the exported duration labels and converts seconds to calendar days using 86,400 seconds per day. Stage contribution is the sum of stage durations divided by the sum of end-to-end durations for the same cohort. Scenario ratios divide the unrounded high-volume mean by the unrounded baseline mean; absolute increases subtract those means. Display rounding occurs after calculation.

The script checks satisfied bindings, unique Requirement IDs, identical milestone/diagnostic cohorts, matching milestone event IDs and exact stage additivity. The six diagnostic ratios are 10.5, 33.7, 117.0, 93.5, 2.1 and 14.3 after rounding to one decimal place.

The archived OCEL logs and OCPQ exports reconstruct the reported analyses. The original simulation seeds were not retained, so a fresh simulation is not expected to regenerate identical logs. The baseline and scenario models are maintained in the repository-root `models/` directory.

## Figure presentation

The plotting settings are defined in the analysis script. Figures 4.11–4.12 are 160 mm-wide vector PDFs with embedded fonts and main labels of at least 9 pt; logarithmic-axis superscripts use smaller glyphs. The stage-comparison panels are arranged vertically. The diagnostic plot retains all six intervals and calculates scenario ratios from unrounded means.
