# CSQ4 Reproduction

Run the commands below in Git Bash, starting from the repository root. Use separate Python environments for PM4Py and OCPA.

```bash
cd 'analysis/OCPA&pm4py'
```

## 1. Generate PM4Py results

Activate the PM4Py environment, then run:

```bash
python -m pip install pm4py pandas numpy matplotlib openpyxl

python script/bq4_pm4py_analysis.py \
  --input data/intangible_asset_ocel2_run1.jsonocel \
  --out output
```

## 2. Convert the input for OCPA

```bash
python script/convert_ocel2_for_ocpa.py \
  data/intangible_asset_ocel2_run1.jsonocel \
  data/ocpa_all_types.jsonocel \
  --all-types
```

## 3. Generate OCPA results

Activate the separate OCPA environment, then run:

```bash
python -m pip install 'ocpa==1.3.4' 'pandas==2.2.2' 'numpy==1.26.4' 'scipy==1.13.1' 'networkx==2.8.8' openpyxl

python script/ocpa_analysis_resource_perspective.py \
  --input data/ocpa_all_types.jsonocel \
  --out output/OCPA
```

## 4. Generate figures

Return to the PM4Py environment and run:

```bash
python script/generate_bq4_figures_from_excel.py \
  --pm4py output/tables/BQ4_PM4Py_results.xlsx \
  --ocpa output/OCPA/BQ4_OCPA_results.xlsx \
  --out output/figures
```

Tables are saved under `output/tables/` and `output/OCPA/`, metadata under `output/metadata/`, and figures under `output/figures/` in PNG, SVG, and PDF formats.
