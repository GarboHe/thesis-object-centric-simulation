# CSQ1–CSQ3

This analysis reproduces Figures 4.3–4.6 and Tables 4.9–4.12 from the archived baseline OCPQ exports. Its completed cohort consists of the 25 Requirements that reached accounting-voucher posting.

## Run

From the repository root:

```bash
python -m pip install -r analysis/OCPQ/requirements.txt
python analysis/OCPQ/csq1_3_analysis/scripts/run_analysis.py
```

Add `--latex` to generate LaTeX versions of the four tables. The generated LaTeX uses `booktabs`, `tabularx` and `array`.

## Queries and exports

Paths below are relative to `analysis/OCPQ/csq1_3_analysis/`. The baseline log is `../../../data/intangible_asset_ocel2.sqlite`.

| Query | OCPQ export | Rows |
|---|---|---:|
| `../ocpq_shared/queries/path.json` | `data/ocpq_exports/csq1_path_connections.csv` | 25 |
| `../ocpq_shared/queries/milestone.json` | `../ocpq_shared/baseline_milestone.csv` | 25 |
| `queries/csq2_requirement_modification_query.json` | `data/ocpq_exports/csq2_requirement_modification_situation_table.csv` | 2 |
| `queries/csq2_contract_review_query.json` | `data/ocpq_exports/csq2_contract_review_situation_table.csv` | 7 |
| `queries/csq2_acceptance_rework_query.json` | `data/ocpq_exports/csq2_acceptance_rework_situation_table.csv` | 8 |
| `queries/csq2_requirement_voucher_mapping_query.json` | `data/ocpq_exports/csq2_requirement_voucher_mapping.csv` | 25 |
| `queries/csq3_invoice_asset_query.json` | `data/ocpq_exports/csq3_invoice_asset_situation_table.csv` | 25 |
| `queries/csq3_voucher_rework_query.json` | `data/ocpq_exports/csq3_voucher_rework_situation_table.csv` | 3 |

To repeat the query stage, load the baseline SQLite log in OCPQ, import the query JSON, execute it, and export all result rows to the location above. Retain object IDs, event IDs, duration labels and `Satisfied` wherever it is present in the archived CSV. The three positive-feature exports cover the baseline log; the Python analysis joins them to the completed cohort by Requirement ID.

Each query contains one node. The JSON specifies its object/event variables, association filters, chronological constraints and output labels. Variable keys are zero-based in JSON and one-based in CSV column names. A null qualifier leaves the association unrestricted.

For the native path view, select *Submit Requirement* to *Post Accounting Voucher* through the same *Requirement*, with the `submitted requirement` and `source requirement` qualifiers. The archived path artwork and recorded OCPQ path statistics are in `assets/`.

## Thesis outputs

Output paths are relative to `results/`.

| Thesis item | Output | Input |
|---|---|---|
| Figure 4.3 | `figures/csq1_path_throughput.pdf` | Path connections, shared milestone export and path assets |
| Table 4.9 | `tables/csq1_stage_summary.csv` | Shared milestone export |
| Figure 4.4 | `figures/csq1_stage_duration_distribution.pdf` | Shared milestone export |
| Figure 4.5 | `figures/csq2_e2e_duration_distribution.pdf` | Shared milestone export |
| Table 4.10 | `tables/csq2_upper_tail_comparison.csv` | Milestones, CSQ2 feature/mapping exports and voucher rework |
| Table 4.11 | `tables/csq2_acceptance_rework_depth.csv` | Milestones and acceptance rework |
| Figure 4.6 | `figures/csq3_sync_delay_distribution.pdf` | Invoice–Asset export |
| Table 4.12 | `tables/csq3_timing_summary.csv` | Invoice–Asset, Requirement–Voucher mapping and voucher-rework exports |

## Definitions

**CSQ1.** OCPQ calculates the four successive intervals between *Submit Requirement*, *Obtain Quotations*, *Create Purchase Order*, *Verify Accounting Prerequisites* and *Post Accounting Voucher*, together with submission-to-posting duration. Python converts the exported duration labels using 86,400 seconds per calendar day. Stage share is `100 × sum(stage duration) / sum(end-to-end duration)`. Quartiles use linear interpolation; boxplots retain outliers and use 1.5-IQR whiskers.

The path histogram matches the 25 source/target event-ID pairs to the OCPQ milestone `e2e_duration` labels. It uses six equal-width bins between the observed minimum and maximum; the last bin includes its right endpoint. Heights are percentages of the completed cohort. Path support, coverage, selectivity, reach and exclusivity are the recorded OCPQ statistics. The scripts do not subtract the path-export timestamps.

**CSQ2.** The upper tail contains completed Requirements with end-to-end duration at or above the unrounded empirical P75. Positive-feature exports are counted by Requirement ID. Repeated acceptance events with `decision = ACCEPTANCE_REWORK` determine rework depth. “At least one” characteristics count each Requirement once. Voucher rework is connected to its Requirement through the exported Voucher ID and posting event ID.

**CSQ3.** The OCPQ query binds *Receive Invoice* to Invoice, *Put Asset Into Use* to Asset, and verification/posting events to both objects. Both prerequisite events must occur no later than verification, and verification no later than posting. OCPQ calculates readiness as the later prerequisite time, synchronisation delay as the absolute difference between prerequisite times, and the elapsed durations from readiness to verification and posting. Python uses these exported duration and ordering labels directly.

Calculations use unrounded values. Tables display durations and stage shares to two decimal places and group percentages to one decimal place. The script checks binding uniqueness, satisfaction flags, matching event-ID cohorts, stage additivity and voucher mappings before completing the results.

## Reported checkpoints

Mean end-to-end duration is 19.97 calendar days, with a median of 18.30. S1–S4 shares are 51.22%, 2.24%, 46.43% and 0.11%. P75 is 19.30 days, giving seven upper-tail Requirements: R-5, R-6, R-9, R-10, R-23, R-25 and R-27. Mean/median Invoice–Asset synchronisation delays are 9.14/7.00 days. Readiness-to-posting duration is 29 minutes for 22 Requirements and 79 minutes for the three with voucher rework.

## Figure presentation

The plotting settings are defined in the existing scripts. The four figures are 160 mm-wide vector PDFs with embedded fonts and main labels of at least 9 pt. Figure 4.3 retains the native OCPQ path artwork and redraws the histogram from matched exported duration labels. Captions are maintained in the thesis LaTeX project.
