# CSQ1 OCPQ Query Definitions and Reproduction Notes

This file documents the OCPQ definitions and raw inputs used to reproduce CSQ1 in the current thesis version.

## 1. CSQ1 research question

**CSQ1 – Baseline performance**

> How long does a submitted Requirement that reaches accounting-voucher posting take to do so, and how is this elapsed time distributed across process stages in terms of contribution and variability?

The elapsed-time analysis is conditional on the 25 Requirements that reach `Post Accounting Voucher`. The seven non-posted Requirements are reported separately in the thesis rather than treated as missing duration observations.

Current thesis mapping:

- **Figure 4.2** – OCPQ path and throughput-time distribution from Requirement submission to accounting-voucher posting.
- **Table 4.9** – Stage-level decomposition of simulated submission-to-posting elapsed time.
- **Figure 4.3** – Distribution of the four stage durations for the 25 posted Requirements.

---

## 2. Overall CSQ1 path

The OCPQ Path Schema relates `Submit Requirement` and `Post Accounting Voucher` through the same `Requirement` object.

The preserved `Open as Query` representation contains:

```text
o1 = Requirement
e1 = Submit Requirement
e2 = Post Accounting Voucher
```

with qualified E2O relations:

```text
e1 -> o1   qualifier: submitted requirement
e2 -> o1   qualifier: source requirement
```

and a forward event-to-event temporal relation from `e1` to `e2`.

Expected Path Schema checkpoints for the preserved baseline run:

```text
Support      = 25
Coverage     = 0.781
Selectivity  = 1.000
Reach        = 1.000
Exclusivity  = 1.000

Minimum throughput  ≈ 16 days 7 hours
Median throughput   ≈ 18 days 7 hours
Mean throughput     ≈ 19 days 23 hours
Maximum throughput  ≈ 38 days
```

Preserved path files:

```text
csq1_path_query.json
csq1_path_connections.csv
csq1_path_schema_overview.png
csq1_path_throughput_results.png
```

`csq1_path_connections.csv` is the raw OCPQ connection export. It contains the selected source/target event identifiers and timestamps for the 25 path connections.

---

## 3. Milestone query for stage decomposition

The preserved machine-readable query is:

```text
csq1_milestone_query.json
```

### Object variable

```text
o1: Requirement
```

### Event variables

```text
e1: Submit Requirement
e2: Obtain Quotations
e3: Create Purchase Order
e4: Verify Accounting Prerequisites
e5: Post Accounting Voucher
```

All five event variables are related to the same `Requirement` object.

### Temporal constraint

```text
e1.time() <= e2.time() &&
e2.time() <= e3.time() &&
e3.time() <= e4.time() &&
e4.time() <= e5.time()
```

### OCPQ duration labels

The preserved query computes the following duration labels directly from event timestamps:

```text
e2e_duration =
    e5.time() - e1.time()

requirement_stage =
    e2.time() - e1.time()

sourcing_order_stage =
    e3.time() - e2.time()

fulfilment_prereq_stage =
    e4.time() - e3.time()

accounting_posting_stage =
    e5.time() - e4.time()
```

These correspond to:

```text
S1  = requirement_stage
S2  = sourcing_order_stage
S3  = fulfilment_prereq_stage
S4  = accounting_posting_stage
E2E = e2e_duration
```

The raw OCPQ Situation Table should be preserved unchanged as:

```text
csq1_milestone_situation_table.csv
```

Expected number of satisfied bindings:

```text
25
```

One row represents one posted Requirement lifecycle.

Expected core columns:

```text
o1
e1
e2
e3
e4
e5
e2e_duration
requirement_stage
sourcing_order_stage
fulfilment_prereq_stage
accounting_posting_stage
Satisfied
```

Additional OCPQ-exported columns, such as Requirement attributes, may be present and are left unchanged.

The duration values are exported by OCPQ in ISO-8601-like form, for example:

```text
PT1620S
PT2862300S
```

The analysis script converts these durations to elapsed seconds and then to **calendar elapsed days**:

```text
calendar_days = elapsed_seconds / 86400
```

They are not converted by dividing by an eight-hour working day.

---

## 4. Stage definitions and internal consistency

The four consecutive stages are:

```text
S1: Submit Requirement -> Obtain Quotations
S2: Obtain Quotations -> Create Purchase Order
S3: Create Purchase Order -> Verify Accounting Prerequisites
S4: Verify Accounting Prerequisites -> Post Accounting Voucher
```

For every posted Requirement, the analysis must verify:

```text
S1 + S2 + S3 + S4 = E2E
```

The script also checks:

```text
row count = 25
25 unique Requirement IDs
all rows are Satisfied = TRUE, if the column is present
all required duration values are present
all durations are non-negative
```

If `csq1_path_connections.csv` is supplied, the script additionally joins the milestone query to the Path Schema result by:

```text
e1 = source_id
e5 = target_id
```

and verifies that:

```text
target_time - source_time = e2e_duration
```

for all 25 Requirements.

---

## 5. Stage contribution

For stage `j`, the aggregate elapsed-time share is:

```text
Share_j =
    sum_i(T_ij)
    ----------------- × 100
    sum_i(T_i,E2E)
```

Because the same 25 Requirements are used for all stages, this is also equal to the ratio of the corresponding unrounded mean stage duration to the unrounded mean E2E duration.

Shares are calculated from full-precision row-level durations rather than from the rounded values printed in the thesis.

---

## 6. Current-thesis checkpoints

The current thesis reports the following values for Table 4.9:

| Stage | N | Mean | Median | Q1 | Q3 | Min | Max | Share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 25 | 10.23 | 11.02 | 9.02 | 11.02 | 9.02 | 11.08 | 51.22% |
| S2 | 25 | 0.45 | 0.17 | 0.17 | 0.98 | 0.17 | 1.98 | 2.24% |
| S3 | 25 | 9.27 | 7.09 | 7.09 | 7.82 | 7.09 | 29.00 | 46.43% |
| S4 | 25 | 0.02 | 0.02 | 0.02 | 0.02 | 0.02 | 0.05 | 0.11% |
| E2E | 25 | 19.97 | 18.30 | 17.05 | 19.30 | 16.30 | 38.31 | 100.00% |

Additional checkpoint:

```text
S1 share + S3 share = 97.65%
```

The current thesis uses **Figure 4.3** for the boxplot of the four stage-duration distributions. The plot is generated from all 25 row-level observations for each of S1–S4 and retains outliers.

---

## 7. Run the analysis

If the CSQ1 files are in the same folder, run:

```powershell
python csq1_analysis.py "csq1_milestone_situation_table.csv" --path-connections-csv "csq1_path_connections.csv" --out-dir .
```

If the Path Schema connection CSV is temporarily unavailable, the stage analysis can still be run with:

```powershell
python csq1_analysis.py "csq1_milestone_situation_table.csv" --out-dir .
```

For the formal baseline reproduction, the first command is preferred because it also performs the independent path-to-milestone E2E cross-check.

---

## 8. Generated outputs

The script creates:

```text
intermediate/
    csq1_case_level.csv
    csq1_path_milestone_crosscheck.csv   # when path connection CSV is supplied

results/
    csq1_run_summary.txt

    tables/
        table_4_9.csv
        csq1_summary_numeric.csv

    figures/
        csq1_stage_duration_distribution.pdf
        csq1_stage_duration_distribution.png
```

`table_4_9.csv` and the figure are generated outputs and should not be manually edited.

---

## 9. Reproducible evidence chain

Overall path:

```text
Run-1 OCEL
→ OCPQ Path Schema
→ csq1_path_query.json
→ csq1_path_connections.csv
→ Figure 4.2 visual evidence
```

Stage decomposition:

```text
Run-1 OCEL
→ csq1_milestone_query.json
→ csq1_milestone_situation_table.csv
→ csq1_analysis.py
→ csq1_case_level.csv
→ Table 4.9 + Figure 4.3
```

The analytical results describe behaviour produced by the preserved stochastic baseline simulation run. They are not estimates of real organisational performance.
