# CSQ2 OCPQ Query Definitions and Reproduction Notes

This file documents the OCPQ feature queries and the downstream analysis used to reproduce CSQ2 in the current thesis version.

## 1. CSQ2 analytical objective

CSQ2 compares lifecycle characteristics of the 25 posted Requirements already defined by CSQ1.

The analysis does **not** define a new population. Instead, it:

1. loads the 25-row `csq1_case_level.csv`;
2. recomputes the 75th percentile (P75) of end-to-end elapsed time using linear interpolation;
3. classifies each Requirement as:
   - `upper-tail` if `E2E_days >= P75`;
   - `remaining` otherwise;
4. identifies four lifecycle characteristics using OCPQ query outputs;
5. left-joins those positive occurrence results back to the complete 25-Requirement cohort;
6. reproduces thesis Tables 4.10 and 4.11.

The current thesis reports:

```text
P75 ≈ 19.30 calendar days

Upper-tail n = 7
Remaining  n = 18
```

Expected upper-tail Requirement IDs:

```text
R-5
R-6
R-9
R-10
R-23
R-25
R-27
```

---

## 2. Shared CSQ1 input

CSQ2 uses the generated CSQ1 intermediate file:

```text
csq1_case_level.csv
```

Required columns:

```text
requirement_id
S3_days
E2E_days
```

`E2E_days` is used to recompute P75 and the upper-tail classification.

`S3_days` is used for the acceptance-rework depth comparison in Table 4.11.

The P75 threshold must be recalculated from the 25 full-precision E2E values. Do not hard-code the rounded thesis value `19.30` as the classification threshold.

---

## 3. Requirement-modification query

Preserved files:

```text
csq2_requirement_modification_query.json
csq2_requirement_modification_situation_table.csv
```

The preserved query contains:

```text
o1 = Requirement
e1 = Modify Requirement

e1 <-> o1
```

The raw OCPQ query identifies positive modification occurrences in the full Run-1 OCEL.

The query result is **not** forced to contain the full 25-row CSQ1 population. The Python analysis counts occurrences per Requirement and left-joins the result to the 25 posted Requirements. Requirements without a matched occurrence receive count `0`.

Expected raw positive Requirements from the preserved query:

```text
R-11
R-25
```

Expected result after joining to the CSQ1 cohort:

```text
Upper-tail with >=1 modification: 1/7
Remaining with >=1 modification:  1/18
```

---

## 4. Acceptance-rework query

Preserved files:

```text
csq2_acceptance_rework_query.json
csq2_acceptance_rework_situation_table.csv
```

The preserved query operationalises an acceptance-rework occurrence as:

```text
o1 = Requirement
e1 = Perform Business And Technical Acceptance

e1 <-> o1

e1.attr('decision') == 'ACCEPTANCE_REWORK'
```

This is intentionally the preserved operationalisation used for CSQ2.

In the simulation model, an acceptance decision with value `ACCEPTANCE_REWORK` triggers the corresponding rectify-and-redeliver loop. Therefore, the query counts the acceptance decisions that trigger those rework cycles while retaining direct Requirement-level traceability.

The raw Run-1 query contains eight positive occurrences:

```text
R-5   x1
R-18  x1
R-23  x2
R-25  x3
R-27  x1
```

`R-18` is not part of the 25 posted Requirements used by CSQ1 and is therefore removed only when the positive occurrence result is joined to the CSQ1 cohort.

Expected posted-cohort result:

```text
R-5   x1
R-23  x2
R-25  x3
R-27  x1

4 Requirements with >=1 acceptance rework
7 total acceptance-rework occurrences
```

All four are expected to be in the upper-tail group.

---

## 5. Contract-review query

Preserved files:

```text
csq2_contract_review_query.json
csq2_contract_review_situation_table.csv
```

The preserved query contains:

```text
o1 = Requirement
e1 = Review Contract

e1 <-> o1
```

The raw Run-1 query identifies positive occurrences in the full log. Requirements outside the 25-row CSQ1 cohort are removed only during the cohort join.

Expected raw positive Requirements:

```text
R-1
R-3
R-4
R-5
R-7
R-6
R-10
```

Expected posted-cohort positives:

```text
R-1
R-3
R-5
R-6
R-10
```

Expected group result:

```text
Upper-tail passed through Contract Review: 3/7
Remaining passed through Contract Review:  2/18
```

---

## 6. Voucher-rework mapping

CSQ2 reuses the voucher-rework evidence already preserved for CSQ3:

```text
csq3_voucher_rework_situation_table.csv
```

The CSQ3 voucher-rework query identifies:

```text
o1 = Voucher
e1 = Modify Accounting Voucher
e2 = Post Accounting Voucher
```

with three positive voucher-rework lifecycles.

CSQ2 additionally preserves:

```text
csq2_requirement_voucher_mapping_query.json
csq2_requirement_voucher_mapping.csv
```

The mapping query contains:

```text
o1 = Requirement
o2 = Voucher
e1 = Post Accounting Voucher

e1 <-> o1
e1 <-> o2
```

The Python analysis maps a reworked Voucher back to its Requirement by joining both:

```text
rework.o1  = mapping.o2   # Voucher ID
rework.e2  = mapping.e1   # Post Accounting Voucher event ID
```

Expected mappings:

```text
V-O-14 -> R-16
V-O-21 -> R-24
V-O-22 -> R-25
```

Expected group result:

```text
Upper-tail with >=1 voucher rework: 1/7
Remaining with >=1 voucher rework:  2/18
```

---

## 7. Cohort-preserving join logic

The feature query exports contain only positive occurrences.

The complete analytical population remains the 25 posted Requirements from CSQ1.

The analysis therefore uses:

```text
CSQ1 25-row cohort
    LEFT JOIN requirement-modification counts
    LEFT JOIN acceptance-rework counts
    LEFT JOIN contract-review counts
    LEFT JOIN voucher-rework counts
```

Unmatched feature counts are replaced by zero.

This produces:

```text
csq2_requirement_features.csv
```

with exactly 25 rows.

Core columns:

```text
requirement_id
E2E_days
S3_days
group
requirement_modification_count
acceptance_rework_count
contract_review_count
voucher_rework_count
```

---

## 8. Table 4.10 checkpoints

Expected current-thesis results:

| Characteristic | Upper-tail (n=7) | Remaining (n=18) |
|---|---:|---:|
| Median E2E duration (calendar days) | 26.05 | 17.71 |
| >=1 Requirement modification | 1 (14.3%) | 1 (5.6%) |
| >=1 acceptance rework | 4 (57.1%) | 0 (0.0%) |
| Total acceptance-rework occurrences | 7 | 0 |
| Passed through Contract Review | 3 (42.9%) | 2 (11.1%) |
| >=1 voucher rework | 1 (14.3%) | 2 (11.1%) |

These are descriptive results for the preserved baseline simulation run; they are not inferential estimates of real-world process effects.

---

## 9. Table 4.11 checkpoints

The second comparison groups the same 25 posted Requirements by `acceptance_rework_count`.

Expected current-thesis result:

| Acceptance-rework cycles | N | Mean S3 (days) | Mean E2E (days) |
|---:|---:|---:|---:|
| 0 | 21 | 7.23 | 17.89 |
| 1 | 2 | 14.50 | 26.13 |
| 2 | 1 | 21.92 | 33.13 |
| 3 | 1 | 29.00 | 38.31 |

Expected deepest-rework case:

```text
R-25
acceptance_rework_count = 3
E2E ≈ 38.31 calendar days
```

---

## 10. Run the analysis

The analysis script is:

```text
csq2_analysis.py
```

If the relevant CSQ1, CSQ2, and CSQ3 files are all in the current directory, run:

```powershell
python csq2_analysis.py "csq1_case_level.csv" "csq2_requirement_modification_situation_table.csv" "csq2_acceptance_rework_situation_table.csv" "csq2_contract_review_situation_table.csv" "csq2_requirement_voucher_mapping.csv" "csq3_voucher_rework_situation_table.csv" --out-dir .
```

If the final repository uses separate `csq1/`, `csq2/`, and `csq3/` directories, update only the paths in the root README; the analysis logic does not change.

---

## 11. Generated outputs

The script creates:

```text
intermediate/
    csq2_requirement_features.csv
    csq2_voucher_rework_mapping_crosscheck.csv

results/
    csq2_run_summary.txt

    tables/
        table_4_10.csv
        table_4_11.csv
        csq2_summary_numeric.csv
```

No thesis figure is generated for CSQ2 in the current thesis version.

---

## 12. Reproducible evidence chain

```text
CSQ1 case-level durations
        +
three CSQ2 Requirement-level positive-occurrence OCPQ exports
        +
CSQ3 voucher-rework export
        +
CSQ2 Requirement-Voucher mapping export
        ↓
csq2_analysis.py
        ↓
25-row CSQ2 feature table
        ↓
Table 4.10 + Table 4.11
```

The raw OCPQ exports should remain unchanged. Generated intermediate and result files should be reproducible by rerunning the analysis script.
