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
│   └── cpn models/
│       ├── baseline/
│       │   └── intangible_asset_v14.cpn
│       └── whatif/
│           └── intangible_asset_v15_whatif.cpn
├── data/
│   ├── raw_csv/
│   ├── raw_csv_whatif/
│   ├── csv_to_ocel2.py
│   ├── csv_to_ocel2_whatif.py
│   ├── intangible_asset_ocel2.sqlite
│   ├── intangible_asset_ocel2_run1.jsonocel
│   ├── intangible_asset_whatif_ocel2.sqlite
│   ├── intangible_asset_whatif_ocel2_jsonocel.zip
│   └── ocpa_all_types.jsonocel
├── analysis/
│   ├── verification/
│   │   ├── ocpa_verification.py
│   │   └── output/
│   ├── OCPQ/
│   │   ├── README.md
│   │   ├── csq1_3_analysis/
│   │   ├── ocpq_shared/
│   │   ├── requirements.txt
│   │   └── whatif_analysis/
│   └── OCPA&pm4py/
│       ├── data/
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
- [Baseline CPN model (v14)](models/cpn%20models/baseline/intangible_asset_v14.cpn) — executable procurement and accounting simulation.
- [High-volume what-if CPN model (v15)](models/cpn%20models/whatif/intangible_asset_v15_whatif.cpn) — scenario variant for the second analysis iteration.

### Data and verification

- [Baseline CPN-generated CSV tables](data/raw_csv/) — events, objects, qualified event-to-object links, object-to-object links, and type-specific tables.
- [Baseline CSV-to-OCEL 2.0 converter](data/csv_to_ocel2.py) — validates and converts the baseline CSV tables into OCEL 2.0 SQLite/JSON representations.
- [Baseline OCEL 2.0 JSON](data/intangible_asset_ocel2_run1.jsonocel) — canonical Run-1 input for the baseline analyses.
- [Baseline OCEL 2.0 SQLite](data/intangible_asset_ocel2.sqlite) — relational representation of the baseline simulated event data.
- [High-volume What-if CSV tables](data/raw_csv_whatif/) and [converter](data/csv_to_ocel2_whatif.py) — separate scenario inputs and conversion script.
- [High-volume What-if OCEL 2.0 SQLite](data/intangible_asset_whatif_ocel2.sqlite) and [JSONOCEL archive](data/intangible_asset_whatif_ocel2_jsonocel.zip) — preserved scenario data for the high-volume analysis.
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
| **CSQ1** | Submission-to-voucher-posting duration, stage contribution, and variability | OCPQ and descriptive statistics | [CSQ1–CSQ3 analysis guide](analysis/OCPQ/csq1_3_analysis/README.md) |
| **CSQ2** | Rework and routing characteristics associated with unusually long completed lifecycles | OCPQ and within-run comparisons | [CSQ1–CSQ3 analysis guide](analysis/OCPQ/csq1_3_analysis/README.md) |
| **CSQ3** | Invoice–Asset synchronisation and the delay from readiness to voucher posting | OCPQ and descriptive statistics | [CSQ1–CSQ3 analysis guide](analysis/OCPQ/csq1_3_analysis/README.md) |
| **CSQ4** | Resource and Supplier participation and cross-object interaction frequency/breadth | PM4Py and OCPA | [CSQ4](analysis/OCPA%26pm4py/) |

CSQ1 and CSQ2 analyse Requirements that reach accounting-voucher posting; the completion-time findings do not treat non-posted Requirements as completed observations. CSQ3 retains Invoice and Asset as distinct related objects. CSQ4 distinguishes **event participation** from resource utilisation and **Supplier participation** from final Supplier selection.

A second, exploratory **high-volume what-if iteration** extends the CSQ1 performance analysis. The repository preserves the variant CPN model, high-volume CSV/OCEL data, and an OCPQ-based analysis package under [What-if analysis](analysis/OCPQ/whatif_analysis/README.md). The package supports downstream comparison from the archived OCPQ exports; exact regeneration of the original simulation run is not guaranteed because the original simulation seeds were not retained.

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

These are **descriptive results of the preserved simulated run**, not claims about actual organisational performance. More detailed numerical checkpoints and definitions are available in the [CSQ1–CSQ3 analysis guide](analysis/OCPQ/csq1_3_analysis/README.md).

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

The high-volume scenario has a separate input set and converter:

```bash
python data/csv_to_ocel2_whatif.py --input-dir data/raw_csv_whatif
```

This command also writes its outputs inside `data/raw_csv_whatif/`, using scenario-specific filenames so that the baseline files are not overwritten. The preserved high-volume SQLite file and compressed JSONOCEL are available directly under [data/](data/).

A full fresh simulation requires CPN Tools and one of the two models:

- [Baseline CPN model (v14)](models/cpn%20models/baseline/intangible_asset_v14.cpn)
- [High-volume what-if CPN model (v15)](models/cpn%20models/whatif/intangible_asset_v15_whatif.cpn)

Both models set `OCEL_DIR` to `./` and configure the CPN Tools output directory as `<same as model>`. These are separate settings: before a full run, verify that the custom CSV logger writes to the corresponding model folder on your CPN Tools installation. The logger initializes its files when `initialize OCEL log` fires; if no CSV files appear, check the resolved working/output directory and write permissions. Run the two models separately because their CSV filenames overlap. Keep new simulation output separate from the archived reference exports in `data/raw_csv/` and `data/raw_csv_whatif/`.

If the generated CSV files are in the corresponding model folder, convert them with the appropriate script:

```bash
python data/csv_to_ocel2.py --input-dir "models/cpn models/baseline" --sqlite intangible_asset_ocel2.sqlite --json intangible_asset_ocel2.jsonocel
python data/csv_to_ocel2_whatif.py --input-dir "models/cpn models/whatif" --sqlite intangible_asset_whatif_ocel2.sqlite --json intangible_asset_whatif_ocel2.jsonocel
```

These commands write the newly converted files into the model folders and leave the preserved OCEL files under `data/` unchanged. If CPN Tools writes the CSVs elsewhere, pass that actual directory to `--input-dir` instead.

### 3. Verify activity–object participation

The [verification folder](analysis/verification/) contains the script, CSV matrices, workbook, and figures used to inspect event-to-object participation and per-activity cardinalities.

**Note:** The verification script resolves `data/ocpa_all_types.jsonocel` from the repository structure and writes its CSV matrices and Excel workbook to `analysis/verification/output/`; no machine-specific path edit is needed. It requires a compatible OCPA installation, pandas, and openpyxl. The checked-in PNG matrices are preserved figures and are not regenerated by this script.

### 4. Reproduce CSQ1–CSQ3 (OCPQ)

Start with the [OCPQ overview](analysis/OCPQ/README.md). It links to the [CSQ1–CSQ3 analysis guide](analysis/OCPQ/csq1_3_analysis/README.md) and the [high-volume What-if guide](analysis/OCPQ/whatif_analysis/README.md).

From the repository root, install the analysis dependencies and run the downstream analyses against the preserved OCPQ exports:

```bash
python -m pip install -r analysis/OCPQ/requirements.txt
python analysis/OCPQ/csq1_3_analysis/scripts/run_analysis.py
python analysis/OCPQ/whatif_analysis/scripts/reproduce.py
```

There are two levels of reproduction:

1. **Downstream analysis:** run the Python scripts against the preserved OCPQ CSV exports. The CSQ1–CSQ3 script checks export consistency and produces four PDF figures and four CSV tables; the What-if script produces two PDF figures and one CSV table.
2. **Query-level reproduction:** open the relevant baseline or high-volume SQLite log in OCPQ Desktop, import the documented query JSON, execute the queries, export the Situation Tables to the paths specified in the relevant guide, and then run the Python scripts.

The scripts check key export properties, including required columns, satisfied bindings, unique Requirement IDs, matching event IDs, and stage-duration additivity. CSQ2's archived feature and mapping exports allow its downstream analysis to be rerun without re-executing OCPQ.

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

**Version-consistency note:** The current PM4Py script defines Supplier participation as qualified participation in **Obtain Quotations** and Supplier selection as qualified participation in **Evaluate And Select Quotation**. For the thesis Supplier-rate comparison, both rates use the **total number of quotation procedures** as their denominator. Some checked-in CSQ4 output files may predate the current definitions. To reproduce the Supplier figure consistently, rerun the PM4Py and OCPA analyses above, then run the figure-generation script against the newly generated workbooks. The current metric definitions are documented in the [CSQ4 analysis scripts](analysis/OCPA%26pm4py/script/), and saved figures and selected tables are available under [CSQ4 outputs](analysis/OCPA%26pm4py/output/).

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
- **Reproducing baseline performance/synchronisation results:** [CSQ1–CSQ3 guide](analysis/OCPQ/csq1_3_analysis/README.md).
- **Reproducing the high-volume What-if comparison:** [What-if guide](analysis/OCPQ/whatif_analysis/README.md).
- **Reproducing actor and cross-object analyses:** [CSQ4 analysis scripts](analysis/OCPA%26pm4py/script/) and [saved outputs](analysis/OCPA%26pm4py/output/).

This repository serves as a **research transparency and analysis-level reproduction package** for the thesis, with documented limits on empirical validity and complete computational reproducibility.
