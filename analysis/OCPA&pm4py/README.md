# BQ4 Reproduction Guide

This folder contains the scripts and supporting files required to reproduce the analyses used to answer **Business Question 4 (BQ4)** of the thesis.

> **BQ4:** How are resources and suppliers distributed across the process, and where do shared actors interact with multiple business objects?

The analysis is performed in two complementary parts:

1. **PM4Py analysis** for resource and supplier distributions.
2. **OCPA analysis** for cross-object interaction hotspots.

The final figures used in the thesis are generated from the exported PM4Py and OCPA result tables.

---

## 1. Analysis Pipeline

```text
Simulation
   ↓
OCEL 2.0 log
   │
   ├──────────────────────── PM4Py ──────────────────────────┐
   │                                                         │
   │  bq4_pm4py_analysis.py                                  │
   │         ↓                                               │
   │  BQ4_PM4Py_results.xlsx                                │
   │                                                         │
   └─ convert_ocel2_to_ocel1.py --all-types                 │
             ↓                                               │
       OCPA-compatible OCEL 1.0                              │
             ↓                                               │
       bq4_ocpa_interaction_analysis.py                      │
             ↓                                               │
       BQ4_OCPA_results.xlsx                                 │
                                                             │
             └──────────────────┬─────────────────────────────┘
                                ↓
                  generate_bq4_figures_from_excel.py
                                ↓
                         Thesis figures
```

The **OCEL 2.0 file is the canonical input dataset**.  
The OCEL 1.0 file is generated only as a compatibility view for OCPA.

---

## 2. Recommended Folder Structure

```text

```

The exact folder names can be changed, but the command paths below must be updated accordingly.

---

## 3. Software Requirements

The pipeline can be run in one environment if all dependencies are compatible. If PM4Py and OCPA dependency versions conflict, use two separate environments.


### 3.1 PM4Py Environment

The PM4Py environment is used for:

- reading and analyzing the original OCEL 2.0 log;
- resource workload analysis;
- resource–activity analysis;
- business-object coverage analysis;
- supplier participation and selection analysis;
- supplier concentration analysis;
- generation of intermediate result tables.

Required packages include:

```text
pm4py
pandas
numpy
openpyxl
```
#### Run

Example installation:
```bat
pip install pm4py pandas numpy openpyxl
```
### 3.2 OCPA Environment

The OCPA environment is used for the object-centric interaction analysis, including:

- actor–object interaction extraction;
- cross-object event identification;
- resource interaction hotspots;
- supplier-linked interaction hotspots;
- activity-level interaction breadth.
```
Required packages include:

```text
ocpa
pandas
numpy
openpyxl
```
### Run

Example installation:
```bat
pip install ocpa pandas numpy openpyxl
```

```text
The figure-generation script additionally requires: matplotlib
```
Example installation:
```bat
pip install matplotlib
```
---

## 4. Step 1 — PM4Py Analysis

### Script

```text
bq4_pm4py_analysis.py
```

### Purpose

This script calculates the descriptive PM4Py results used in BQ4:

- resource event-based workload;
- resource activity distribution;
- resource business-object coverage;
- monthly and weekly resource participation;
- supplier participation;
- supplier selection;
- supplier-selection concentration;
- supplementary supplier-order dependency.

### Run

Example:

```bat
cd /d D:\thesis-object-centric-simulation



python "analysis\OCPA&pm4py\script\bq4_pm4py_analysis.py" ^
  --input "data\intangible_asset_ocel2_run1.jsonocel" ^
  --out "analysis\OCPA&pm4py\output"
```

### Main Outputs

```text
analysis/OCPA&pm4py/output/tables/
├── resource_workload.csv
├── resource_activity_distribution.csv
├── resource_object_coverage.csv
├── resource_temporal_monthly.csv
├── resource_temporal_weekly.csv
├── supplier_participation.csv
├── supplier_selection.csv
├── supplier_concentration.csv
├── supplier_dependency.csv
└── BQ4_PM4Py_results.xlsx
```

The script also creates:

```text
analysis/OCPA&pm4py/output/metadata/bq4_pm4py_metadata.json
```

This metadata file records the input file hash, package versions, OCEL summary, and metric definitions.

---

## 5. PM4Py Metric Definitions

### Resource workload

Resource workload is operationalized as the number of **unique events in which a Resource object participates**.

It therefore represents event-based participation rather than processing time.

### Resource activity distribution

For each resource and activity:

```text
event_count
```

is the number of unique events in which the resource participates in that activity.

### Resource business-object coverage

For each resource and business-object type:

```text
coverage =
number of unique objects of that type associated with the resource
/
total number of objects of that type
```

The BQ4 coverage analysis considers:

```text
Requirement
Asset
Order
Invoice
AcceptanceRecord
Voucher
```

`Project` is excluded because it represents an overarching process-level object.

### Supplier participation

Supplier participation is the number of unique events in which a Supplier object participates.

### Supplier selection

Supplier selection is operationalized as Supplier participation in:

```text
Create Purchase Order
```

This definition is used to calculate the supplier selection share.

### Supplier concentration

The following descriptive concentration measures are calculated:

```text
HHI = sum(selection_share^2)

effective_supplier_count = 1 / HHI

top1_selection_share = largest supplier selection share
```

HHI is used only as a descriptive measure within the simulated dataset.

### Supplier dependency

The script also exports the proportion of unique Order objects associated with each supplier.

This measure is supplementary and may overlap strongly with supplier selection share in the current simulation.

---

## 6. Step 2 — Convert OCEL 2.0 for OCPA
OCPA uses an OCEL 1.0-compatible JSONOCEL file in this reproduction pipeline. Generate it from the canonical OCEL 2.0 file as follows:

### Script

```text
convert_ocel2_to_ocel1.py
```

OCPA currently uses an OCEL 1.0-compatible JSONOCEL representation in this analysis.

Run:

```bat
conda activate ocpa-thesis

python "analysis\OCPA&pm4py\script\convert_ocel2_for_ocpa.py" ^
  "data\intangible_asset_ocel2_run1.jsonocel" ^
  "data\ocpa_all_types.jsonocel" ^
  --all-types
```

### Important

The option:

```text
--all-types
```

must be included for BQ4.

Without it, the converter retains only the core business-object types and excludes `Resource` and `Supplier`, which are required for the BQ4 OCPA analysis.

The converted OCEL 1.0 file is only a **compatibility view**.

The conversion does not preserve the complete OCEL 2.0 semantics, including:

- O2O relations;
- relation qualifiers;
- full history of changing object attributes.

Therefore, the original OCEL 2.0 file remains the canonical dataset.

---

## 7. Step 3 — OCPA Cross-Object Interaction Analysis

### Script

```text
bq4_ocpa_interaction_analysis.py
```

### Purpose

This script answers the object-centric part of BQ4:

> Where do shared actors interact with multiple business objects?

The focal actor types are:

```text
Resource
Supplier
```

The business-object types are:

```text
Requirement
Asset
Order
Invoice
AcceptanceRecord
Voucher
```

`Project` is deliberately excluded from interaction-breadth calculations because it is an umbrella object and would otherwise systematically increase the measured breadth.

### Current Input Configuration


Then run:

```bat
python "analysis\OCPA&pm4py\script\ocpa_analysis_resource_perspective.py" ^
  --input "data\ocpa_all_types.jsonocel" ^
  --out "analysis\OCPA&pm4py\output\OCPA"
```

### Main Outputs

```text
analysis/OCPA&pm4py/output/OCPA/
├── 01_actor_object_interactions.csv
├── 02_actor_event_interaction.csv
├── 03_multi_object_events.csv
├── 04_BQ4_interaction_hotspots.csv
├── 05_actor_object_summary.csv
├── 06_actor_overall_summary.csv
├── 07_activity_hotspots.csv
├── 08_resource_hotspots.csv
├── 09_supplier_hotspots.csv
└── BQ4_OCPA_results.xlsx
```

---

## 8. OCPA Metric Definitions

### Cross-object event

An actor-event is considered cross-object when it is associated with at least **two different business-object types**.

Formally:

```text
cross_object_type =
object_type_breadth >= 2
```

### Object-type breadth

```text
object_type_breadth =
number of distinct business-object types associated with an actor-event
```

### Business-object count

```text
business_object_count =
number of distinct individual business objects associated with an actor-event
```

### Interaction frequency

```text
interaction_events =
number of cross-object events for an actor at an activity
```

### Interaction breadth

At activity level:

```text
mean_object_type_breadth =
average number of distinct business-object types involved
in cross-object actor-events
```

This allows BQ4 to distinguish between:

- **high-frequency interaction hotspots**, and
- **high-breadth interaction hotspots**.

---

## 9. Interpretation of Supplier-Linked OCPA Results

Resource and Supplier results should not be interpreted identically.

A `Resource` object represents an execution resource participating in an activity.

A `Supplier` object may remain related to downstream events after supplier selection. Therefore, a Supplier associated with a downstream accounting event should **not** be interpreted as executing that accounting activity.

Supplier results should instead be interpreted as:

```text
supplier-linked cross-object interactions
```

or:

```text
supplier-associated downstream relationships
```

---

## 10. Step 4 — Generate Thesis Figures

### Script

```text
generate_bq4_figures_from_excel.py
```

This script generates the four principal BQ4 figures directly from the exported Excel results.

Run:

```bat
python "analysis\OCPA&pm4py\script\generate_bq4_figures_from_excel.py" ^
  --pm4py "analysis\OCPA&pm4py\output\tables\BQ4_PM4Py_results.xlsx" ^
  --ocpa "analysis\OCPA&pm4py\output\OCPA\BQ4_OCPA_results.xlsx" ^
  --out "analysis\OCPA&pm4py\output\figures"
```

### Outputs

```text
analysis/OCPA&pm4py/output/figures/
├── BQ4_resource_workload.png
├── BQ4_resource_workload.svg
├── BQ4_resource_activity_heatmap.png
├── BQ4_resource_activity_heatmap.svg
├── BQ4_supplier_participation_vs_selection.png
├── BQ4_supplier_participation_vs_selection.svg
├── BQ4_activity_interaction_hotspots.png
└── BQ4_activity_interaction_hotspots.svg
```

The PNG files are intended for direct use in the thesis.  
The SVG files provide vector versions.

---

## 11. How the Outputs Answer BQ4

The BQ4 evidence chain is:

| BQ4 aspect | Source |
|---|---|
| Resource workload distribution | `Resource_Workload` |
| Resource activity specialization | `Resource_Activity` |
| Resource business-object coverage | `Resource_Coverage` |
| Supplier participation | `Supplier_Participation` |
| Supplier selection | `Supplier_Selection` |
| Supplier concentration | `Supplier_Concentration` |
| Actor-level cross-object hotspots | `04_BQ4_interaction_hotspots` |
| Activity-level cross-object hotspots | `07_activity_hotspots` |
| Resource-specific hotspots | `08_resource_hotspots` |
| Supplier-linked hotspots | `09_supplier_hotspots` |

The main BQ4 findings should therefore be traceable from:

```text
OCEL
  ↓
analysis script
  ↓
CSV / Excel result
  ↓
figure
  ↓
reported thesis finding
```

---

## 12. Reproducibility Scope

These scripts support **analysis-level reproducibility**.

Given the same OCEL input file, software versions, and analysis definitions, another researcher should be able to reproduce:

- resource workload values;
- resource activity distributions;
- resource object coverage;
- supplier participation shares;
- supplier selection shares;
- HHI and effective supplier count;
- OCPA interaction hotspots;
- the thesis figures.

This does **not by itself provide end-to-end simulation reproducibility**.

To reproduce the OCEL itself from the simulation, the following must additionally be preserved:

- CPN model;
- simulation configuration;
- parameter values;
- initial marking;
- random seed or stochastic settings;
- number of simulation runs;
- OCEL export procedure.

---

## 13. Recommended Reproduction Order

Run the files in this order:

```text
1. bq4_pm4py_analysis.py

2. convert_ocel2_to_ocel1.py --all-types

3. bq4_ocpa_interaction_analysis.py

4. generate_bq4_figures_from_excel.py
```

A successful reproduction should generate both:

```text
BQ4_PM4Py_results.xlsx
BQ4_OCPA_results.xlsx
```

before the figure-generation script is executed.

---

## 14. Thesis Reporting Note

The PM4Py and OCPA results serve different analytical roles.

PM4Py is used for descriptive actor-level analysis:

```text
Who participates?
How frequently?
In which activities?
Across which business objects?
How are suppliers distributed and selected?
```

OCPA is used for focused object-centric interaction analysis:

```text
Where do shared actors interact with multiple business-object types?
How frequent are these interactions?
How broad are these interactions?
```

The two analyses should therefore be interpreted as complementary rather than interchangeable.

---

## 15. Suggested Citation / Supporting Material Statement

A concise statement for the thesis or repository can be written as:

> The BQ4 analysis was reproduced from the generated OCEL using PM4Py and OCPA. PM4Py was used to derive resource and supplier distribution metrics, while OCPA was used to identify cross-object actor-interaction hotspots. Intermediate result tables and visualization scripts were retained to provide traceability between the input event data, calculated metrics, figures, and reported findings.

---


