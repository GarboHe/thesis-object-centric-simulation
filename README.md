# Design for Simulation in Object-Centric Process Management

**Supporting repository for a master's thesis on Object-Centric Process Simulation (OCPS).**

This repository contains the case-study models, simulation-generated object-centric event data, analysis scripts, results, and supporting research documentation for *Design for Simulation in Object-Centric Process Management*.

The research develops a catalogue of **55 normative OCPS design requirements** and demonstrates their application in a manufacturing case concerning the procurement and accounting of intangible assets. The case study implements a timed **Coloured Petri Net (CPN)**, generates **OCEL 2.0** event data, verifies activity–object participation, and analyses the simulated process using **OCPQ, PM4Py, and OCPA**.

> **Research scope:** The event data and numerical findings describe configured simulation runs. They are **not an operational event log or empirically calibrated measurements of the organisation**.

## Repository contents

```text
.
├── models/
│   ├── conceptual model v2.drawio
│   ├── intangible_asset_v14.cpn
│   └── intangible_asset_v15_whatif.cpn
├── data/
│   ├── raw_csv/
│   ├── csv_to_ocel2.py
│   ├── intangible_asset_ocel2.sqlite
│   ├── intangible_asset_ocel2_run1.jsonocel
│   └── ocpa_all_types.jsonocel
├── analysis/
│   ├── verification/
│   │   ├── ocpa_verification.py
│   │   └── output/
│   ├── OCPQ/
│   │   ├── OCPQ_README.md
│   │   ├── csq1/
│   │   ├── csq2/
│   │   └── csq3/
│   └── OCPA&pm4py/
│       ├── README.md
│       ├── script/
│       └── output/
└── docs/
    ├── OCPS_Business_Question_Selection_Record.xlsx
    ├── OCPS_Requirement_Traceability-final.xlsx
    ├── Simulation_Matrix.docx
    └── SLR/
```

### Models

- [Conceptual case model](models/conceptual%20model%20v2.drawio) — conceptual process representation.
- [Baseline CPN model (v14)](models/intangible_asset_v14.cpn) — executable procurement and accounting simulation.
- [High-volume what-if CPN model (v15)](models/intangible_asset_v15_whatif.cpn) — scenario variant for the second analysis iteration.

### Data and verification

- [Raw CPN-generated CSV tables](data/raw_csv/) — events, objects, qualified event-to-object links, object-to-object links, and type-specific tables.
- [CSV-to-OCEL 2.0 converter](data/csv_to_ocel2.py) — validates and converts those CSVs into OCEL 2.0 SQLite/JSON representations.
- [Baseline OCEL 2.0 JSON](data/intangible_asset_ocel2_run1.jsonocel) — canonical Run-1 input for the analysis.
- [Baseline OCEL 2.0 SQLite](data/intangible_asset_ocel2.sqlite) — relational representation of the simulated event data.
- [OCPA-compatible OCEL 1.0 view](data/ocpa_all_types.jsonocel) — a derived compatibility dataset, **not** a replacement for the OCEL 2.0 source.
- [Activity–object verification outputs](analysis/verification/output/) — event-to-object relation counts and cardinality matrices.

### Research documentation

- [Business-question selection record](docs/OCPS_Business_Question_Selection_Record.xlsx) — question selection, deferral, and subsequent treatment.
- [Requirement traceability workbook](docs/OCPS_Requirement_Traceability-final.xlsx) — requirement mapping and assessment evidence.
- [Case-specific Simulation Matrix](docs/Simulation_Matrix.docx) — activity–object specification and simulation design information.
- [Literature-review materials](docs/SLR/) — supporting systematic literature review records.

## Case-study questions

Four questions define the baseline analytical demonstration:

| ID | Focus | Main method | Reproduction materials |
| --- | --- | --- | --- |
| **CSQ1** | Submission-to-voucher-posting duration, stage contribution, and variability | OCPQ and descriptive statistics | [CSQ1](analysis/OCPQ/csq1/) |
| **CSQ2** | Rework and routing characteristics associated with unusually long completed lifecycles | OCPQ and within-run comparisons | [CSQ2](analysis/OCPQ/csq2/) |
| **CSQ3** | Invoice–Asset synchronisation and the delay from readiness to voucher posting | OCPQ and descriptive statistics | [CSQ3](analysis/OCPQ/csq3/) |
| **CSQ4** | Resource and Supplier participation and cross-object interaction frequency/breadth | PM4Py and OCPA | [CSQ4](analysis/OCPA%26pm4py/) |

CSQ1 and CSQ2 analyse Requirements that reach accounting-voucher posting; the completion-time findings do not treat non-posted Requirements as completed observations. CSQ3 retains Invoice and Asset as distinct related objects. CSQ4 distinguishes **event participation** from resource utilisation and **Supplier participation** from final Supplier selection.

A second, exploratory **high-volume what-if iteration** extends the CSQ1 performance analysis. The variant CPN model is preserved here, but the repository's documented downstream analysis package primarily covers the **baseline Run 1**; it does not yet provide an equivalent complete high-volume reproduction package.

## Baseline dataset and selected checkpoints

The preserved baseline represents a single configured simulation run. The thesis reports:

| Measure | Baseline result |
| --- | ---: |
| Generated/submitted Requirements | 32 |
| Requirements reaching voucher posting | 25 |
| Mean submission-to-posting elapsed time, among posted Requirements | 19.97 calendar days |
| Median submission-to-posting elapsed time, among posted Requirements | 18.30 calendar days |
| Share of elapsed time in stage S1 | 51.22% |
| Share of elapsed time in stage S3 | 46.43% |
| Upper-tail posted Requirements in CSQ2 | 7 |
| Upper-tail Requirements with acceptance rework | 4 of 7 |
| Median Invoice–Asset synchronisation delay in CSQ3 | 7.00 calendar days |

These are **descriptive results of the preserved simulated run**, not claims about actual organisational performance. More detailed numerical checkpoints and definitions are available in the [OCPQ reproduction guide](analysis/OCPQ/OCPQ_README.md).

## Reproduction guide

### 1. Obtain the repository

```bash
git clone https://github.com/GarboHe/thesis-object-centric-simulation.git
cd thesis-object-centric-simulation
```

The Python analysis uses packages such as **pandas, NumPy, Matplotlib, openpyxl, PM4Py, and OCPA**. OCPQ query re-execution additionally requires **OCPQ Desktop**. The CPN models are intended for **CPN Tools**. No single environment or dependency lockfile is provided; PM4Py and OCPA may require separate compatible environments.

### 2. Inspect or reconstruct the OCEL 2.0 data

The simplest route is to use the preserved [baseline JSONOCEL](data/intangible_asset_ocel2_run1.jsonocel) directly.

To rebuild OCEL 2.0 from the preserved CSV export:

```bash
python -m pip install pandas pm4py
python data/csv_to_ocel2.py --input-dir data/raw_csv
```

The converter validates the semicolon-delimited CSV tables and writes SQLite and JSONOCEL outputs **inside the specified input directory**. The versioned baseline files under [data/](data/) are already supplied and need not be overwritten.

A full fresh simulation would additionally require running the [CPN model](models/intangible_asset_v14.cpn) in CPN Tools and collecting its output CSV files. This is distinct from reproducing downstream analyses from the preserved baseline.

### 3. Verify activity–object participation

The [verification folder](analysis/verification/) contains the script, CSV matrices, workbook, and figures used to inspect event-to-object participation and per-activity cardinalities.

**Note:** The preserved verification script includes a machine-specific Windows input path. Adjust paths for your environment before rerunning it. The existing [verification outputs](analysis/verification/output/) can be inspected without running the script.

### 4. Reproduce CSQ1–CSQ3 (OCPQ)

Start with the [OCPQ reproduction guide](analysis/OCPQ/OCPQ_README.md). It documents the preserved OCPQ query JSON, raw Situation Table exports, Python scripts, expected results, and commands.

There are two levels of reproduction:

1. **Downstream analysis:** run the Python analysis scripts against the preserved OCPQ CSV exports.
2. **Query-level reproduction:** open the baseline OCEL in OCPQ Desktop, recreate the documented queries, export the Situation Tables, and then run the Python scripts.

The preserved baseline scripts perform thesis-specific checks. A successful formal run should report **Thesis checkpoint status: PASS**. CSQ2 includes frozen upstream inputs so its analysis can be rerun independently.

### 5. Reproduce CSQ4 (PM4Py and OCPA)

The [CSQ4 folder](analysis/OCPA%26pm4py/) contains the analytical scripts and saved tables/figures. From the repository root:

**PM4Py: descriptive Resource and Supplier statistics**

```bash
python "analysis/OCPA&pm4py/script/bq4_pm4py_analysis.py" \
  --input "data/intangible_asset_ocel2_run1.jsonocel" \
  --out "analysis/OCPA&pm4py/output"
```

**Convert the OCEL 2.0 source to an OCPA-compatible view**

```bash
python "analysis/OCPA&pm4py/script/convert_ocel2_for_ocpa.py" \
  "data/intangible_asset_ocel2_run1.jsonocel" \
  "data/ocpa_all_types.jsonocel" \
  --all-types
```

The **--all-types** option is required: without it, Resource and Supplier objects are excluded from the OCPA input. This compatibility conversion does not retain the full OCEL 2.0 semantics, including O2O relations and qualifiers.

**OCPA: actor-linked cross-object interactions**

```bash
python "analysis/OCPA&pm4py/script/ocpa_analysis_resource_perspective.py" \
  --input "data/ocpa_all_types.jsonocel" \
  --out "analysis/OCPA&pm4py/output/OCPA"
```

**Figures from the PM4Py and OCPA result workbooks**

```bash
python "analysis/OCPA&pm4py/script/generate_bq4_figures_from_excel.py" \
  --pm4py "analysis/OCPA&pm4py/output/tables/BQ4_PM4Py_results.xlsx" \
  --ocpa "analysis/OCPA&pm4py/output/OCPA/BQ4_OCPA_results.xlsx" \
  --out "analysis/OCPA&pm4py/output/figures"
```

These examples use Bash-style line continuations; Windows Command Prompt users should put each command on one line or replace backslashes at line ends with the Command Prompt continuation syntax.

**Important version-consistency note:** The CSQ4 PM4Py script defines Supplier participation as qualified participation in **Obtain Quotations** and Supplier selection as qualified participation in **Evaluate And Select Quotation**. For the thesis Supplier-rate comparison, both rates use the **total number of quotation procedures** as their denominator. Some previously committed result tables and the detailed CSQ4 README reflect older definitions. **Regenerate the PM4Py workbook and figures with the current script before treating the checked-in exports as an exact reproduction of the final Supplier figure.**

See the [detailed CSQ4 documentation](analysis/OCPA%26pm4py/README.md) for metric definitions and output descriptions; where its text conflicts with the current script, use the source code and freshly generated metadata as the basis for checking calculations.

## Interpretation and reproducibility boundaries

- **Simulation assumptions:** Arrival patterns, activity durations, routing probabilities, and resource capacities are scenario parameters; they were not fully calibrated against operational event data.
- **Single-run evidence:** The preserved baseline results describe one stochastic run. Independent replications and uncertainty quantification remain outside the archived baseline analysis.
- **Actor measures:** Resource event counts measure participation, **not** processing time, utilisation, workload intensity, or independently established capacity bottlenecks.
- **Supplier measures:** Being queried, being selected, and being associated with downstream events are different concepts. Supplier-linked accounting events do not mean Suppliers executed accounting work.
- **Object-centric conversion:** OCEL 1.0 files in this repository are analysis-specific compatibility views. Consult the canonical OCEL 2.0 data for qualified relationships and richer object information.
- **Scenario coverage:** The baseline simplifies object cardinalities and accounting-recognition semantics. Split/consolidated purchasing, cross-project reuse, full amortisation, and policy-compliance verification are not fully exercised.
- **Reproduction level:** The repository preserves models, inputs, queries, scripts, and selected outputs, but an independent end-to-end rebuild—from a fresh CPN execution through every thesis figure and the second what-if iteration—has not been established here.

## Where to start

- **Understanding the research design:** [Simulation Matrix](docs/Simulation_Matrix.docx) and [requirement traceability](docs/OCPS_Requirement_Traceability-final.xlsx).
- **Inspecting generated data:** [baseline OCEL 2.0](data/intangible_asset_ocel2_run1.jsonocel).
- **Reproducing baseline performance/synchronisation results:** [OCPQ guide](analysis/OCPQ/OCPQ_README.md).
- **Reproducing actor and cross-object analyses:** [CSQ4 guide](analysis/OCPA%26pm4py/README.md).

This repository serves as a **research transparency and analysis-level reproduction package** for the thesis, with documented limits on empirical validity and complete computational reproducibility.
