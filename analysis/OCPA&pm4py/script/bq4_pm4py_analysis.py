# -*- coding: utf-8 -*-
"""
BQ4 - PM4Py Resource and Supplier Analysis
===========================================

Purpose
-------
Generate the PM4Py-side evidence used to answer BQ4:

    How are resources and suppliers distributed across the process,
    and where do shared actors interact with multiple business objects?

This script covers the descriptive PM4Py part of BQ4:
1. Resource event-based workload distribution
2. Resource activity distribution
3. Resource business-object coverage
4. Resource temporal distribution
5. Supplier participation
6. Supplier selection share
7. Supplier selection concentration (HHI, effective supplier count, top-1 share)
8. Supplier-order coverage/dependency (supplementary)

The cross-object interaction hotspot analysis is performed separately
with OCPA.

Input
-----
An OCEL 2.0 file readable by PM4Py, e.g.:

    intangible_asset_ocel2_run1.jsonocel

Outputs
-------
<out>/tables/
    resource_workload.csv
    resource_activity_distribution.csv
    resource_object_coverage.csv
    resource_temporal_monthly.csv
    resource_temporal_weekly.csv
    supplier_participation.csv
    supplier_selection.csv
    supplier_concentration.csv
    supplier_dependency.csv
    BQ4_PM4Py_results.xlsx

<out>/metadata/
    bq4_pm4py_metadata.json

Optional:
<out>/figures/
    BQ4_OCDFG_frequency.png
    BQ4_OCDFG_performance.png

Example
-------
python bq4_pm4py_analysis.py ^
    --input "D:\\IAProcessCPN\\intangible_asset_ocel2_run1.jsonocel" ^
    --out "D:\\IAProcessCPN\\results\\BQ4"

Optional OC-DFG export:
python bq4_pm4py_analysis.py ^
    --input "D:\\IAProcessCPN\\intangible_asset_ocel2_run1.jsonocel" ^
    --out "D:\\IAProcessCPN\\results\\BQ4" ^
    --export-ocdfg

Required packages
-----------------
pm4py
pandas
numpy
openpyxl

Notes
-----
- "Resource workload" is operationalized as the number of unique
  resource-event participations, not processing time.
- Supplier selection is operationalized as Supplier participation in
  the "Create Purchase Order" activity.
- HHI is used descriptively to characterize supplier-selection
  concentration within the simulated dataset.
- Project is not included in the business-object coverage set used
  for the BQ4 resource coverage analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import pm4py


# ============================================================
# BQ4 analysis definitions
# ============================================================

BUSINESS_TYPES = [
    "Requirement",
    "Asset",
    "Order",
    "Invoice",
    "AcceptanceRecord",
    "Voucher",
]

RESOURCE_TYPE = "Resource"
SUPPLIER_TYPE = "Supplier"

# Operational definition of a selected supplier.
SUPPLIER_SELECTION_ACTIVITY = "Create Purchase Order"


# ============================================================
# Helpers
# ============================================================

def sha256_file(path: Path) -> str:
    """Return SHA-256 hash of the input file for reproducibility."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def prepare_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy that Excel can store.

    Excel does not support timezone-aware datetime columns.
    CSV outputs retain the original timezone-aware values.
    """
    result = df.copy()

    for column in result.columns:
        dtype = result[column].dtype

        if isinstance(dtype, pd.DatetimeTZDtype):
            result[column] = result[column].dt.tz_localize(None)

    return result


def ensure_object_types(
    available_types: set[str],
    required_types: list[str],
    label: str,
) -> None:
    """Raise a clear error if required object types are absent."""
    missing = [x for x in required_types if x not in available_types]

    if missing:
        raise ValueError(
            f"Missing {label} object type(s): {missing}\n"
            f"Available object types: {sorted(available_types)}"
        )


def print_table(title: str, df: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)

    if df.empty:
        print("<empty>")
    else:
        print(df.to_string(index=False))


# ============================================================
# Analysis functions
# ============================================================

def analyze_resource_workload(
    relations: pd.DataFrame,
    eid: str,
    act: str,
    time_col: str,
    oid: str,
    otype: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate unique resource-event participation.

    Returns:
        resource_rel:
            Deduplicated Resource E2O relation table.
        resource_workload:
            Per-resource event counts, activity counts, time span,
            and workload share.
    """
    resource_rel = (
        relations.loc[relations[otype] == RESOURCE_TYPE]
        .drop_duplicates([eid, oid])
        .copy()
    )

    if resource_rel.empty:
        raise ValueError("No Resource relations were found in the OCEL.")

    resource_workload = (
        resource_rel
        .groupby(oid)
        .agg(
            event_count=(eid, "nunique"),
            activity_count=(act, "nunique"),
            first_event=(time_col, "min"),
            last_event=(time_col, "max"),
        )
        .reset_index()
        .rename(columns={oid: "resource"})
    )

    total_resource_participations = resource_workload["event_count"].sum()

    resource_workload["workload_share"] = (
        resource_workload["event_count"] / total_resource_participations
    )

    resource_workload = resource_workload.sort_values(
        ["event_count", "resource"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return resource_rel, resource_workload


def analyze_resource_activity(
    resource_rel: pd.DataFrame,
    eid: str,
    act: str,
    oid: str,
) -> pd.DataFrame:
    """Calculate Resource × Activity event participation."""
    resource_activity = (
        resource_rel
        .groupby([oid, act])
        .agg(event_count=(eid, "nunique"))
        .reset_index()
        .rename(
            columns={
                oid: "resource",
                act: "activity",
            }
        )
    )

    resource_activity["within_resource_share"] = (
        resource_activity["event_count"]
        / resource_activity
        .groupby("resource")["event_count"]
        .transform("sum")
    )

    return resource_activity.sort_values(
        ["resource", "event_count", "activity"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def analyze_resource_coverage(
    relations: pd.DataFrame,
    objects: pd.DataFrame,
    resource_rel: pd.DataFrame,
    eid: str,
    oid: str,
    otype: str,
) -> pd.DataFrame:
    """
    Calculate the number and fraction of business objects associated
    with each resource through shared events.

    A full Resource × Business-Type grid is returned; absent coverage
    is explicitly represented as zero.
    """
    resource_events = (
        resource_rel[[eid, oid]]
        .rename(columns={oid: "resource"})
        .drop_duplicates()
    )

    all_resources = sorted(resource_events["resource"].dropna().unique())

    rows = []

    for business_type in BUSINESS_TYPES:
        total_objects = objects.loc[
            objects[otype] == business_type,
            oid,
        ].nunique()

        business_rel = (
            relations.loc[
                relations[otype] == business_type,
                [eid, oid],
            ]
            .drop_duplicates()
            .rename(columns={oid: "business_object"})
        )

        joined = (
            resource_events
            .merge(business_rel, on=eid, how="inner")
            .drop_duplicates(["resource", "business_object"])
        )

        counts = (
            joined
            .groupby("resource")
            .agg(object_count=("business_object", "nunique"))
            .reindex(all_resources, fill_value=0)
            .reset_index()
        )

        counts["object_type"] = business_type
        counts["total_objects"] = total_objects

        if total_objects > 0:
            counts["coverage"] = counts["object_count"] / total_objects
        else:
            counts["coverage"] = np.nan

        rows.append(counts)

    coverage = pd.concat(rows, ignore_index=True)

    return coverage[
        [
            "resource",
            "object_type",
            "object_count",
            "total_objects",
            "coverage",
        ]
    ].sort_values(
        ["resource", "object_type"]
    ).reset_index(drop=True)


def analyze_resource_temporal(
    resource_rel: pd.DataFrame,
    eid: str,
    time_col: str,
    oid: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate monthly and weekly resource-event participation."""
    temporal = resource_rel.copy()

    # Explicitly drop timezone only for period grouping labels.
    period_time = temporal[time_col]

    if isinstance(period_time.dtype, pd.DatetimeTZDtype):
        period_time = period_time.dt.tz_localize(None)

    temporal["month"] = period_time.dt.to_period("M").astype(str)
    temporal["week"] = period_time.dt.to_period("W").astype(str)

    monthly = (
        temporal
        .groupby([oid, "month"])
        .agg(event_count=(eid, "nunique"))
        .reset_index()
        .rename(columns={oid: "resource"})
        .sort_values(["month", "resource"])
        .reset_index(drop=True)
    )

    weekly = (
        temporal
        .groupby([oid, "week"])
        .agg(event_count=(eid, "nunique"))
        .reset_index()
        .rename(columns={oid: "resource"})
        .sort_values(["week", "resource"])
        .reset_index(drop=True)
    )

    return monthly, weekly


def analyze_supplier_participation(
    relations: pd.DataFrame,
    eid: str,
    act: str,
    oid: str,
    otype: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate supplier event participation and participation shares."""
    supplier_rel = (
        relations.loc[relations[otype] == SUPPLIER_TYPE]
        .drop_duplicates([eid, oid])
        .copy()
    )

    if supplier_rel.empty:
        raise ValueError("No Supplier relations were found in the OCEL.")

    supplier_participation = (
        supplier_rel
        .groupby(oid)
        .agg(
            event_count=(eid, "nunique"),
            activity_count=(act, "nunique"),
        )
        .reset_index()
        .rename(columns={oid: "supplier"})
    )

    total_participations = supplier_participation["event_count"].sum()

    supplier_participation["participation_share"] = (
        supplier_participation["event_count"] / total_participations
    )

    supplier_participation = supplier_participation.sort_values(
        ["participation_share", "supplier"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return supplier_rel, supplier_participation


def analyze_supplier_selection(
    supplier_rel: pd.DataFrame,
    eid: str,
    act: str,
    oid: str,
) -> pd.DataFrame:
    """
    Operationalize supplier selection as participation in
    'Create Purchase Order'.
    """
    all_suppliers = sorted(supplier_rel[oid].dropna().unique())

    selected_supplier = (
        supplier_rel.loc[
            supplier_rel[act] == SUPPLIER_SELECTION_ACTIVITY
        ]
        .drop_duplicates([eid, oid])
    )

    selection = (
        selected_supplier
        .groupby(oid)
        .agg(selected_orders=(eid, "nunique"))
        .reindex(all_suppliers, fill_value=0)
        .reset_index()
        .rename(columns={oid: "supplier"})
    )

    total_selections = selection["selected_orders"].sum()

    if total_selections > 0:
        selection["selection_share"] = (
            selection["selected_orders"] / total_selections
        )
    else:
        selection["selection_share"] = 0.0

    return selection.sort_values(
        ["selection_share", "supplier"],
        ascending=[False, True],
    ).reset_index(drop=True)


def analyze_supplier_concentration(
    supplier_selection: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate descriptive supplier-selection concentration metrics."""
    shares = supplier_selection["selection_share"].astype(float)

    hhi = float((shares ** 2).sum())
    effective_supplier_count = float(1 / hhi) if hhi > 0 else np.nan
    top1_share = float(shares.max()) if len(shares) > 0 else np.nan

    return pd.DataFrame(
        {
            "metric": [
                "HHI",
                "effective_supplier_count",
                "top1_selection_share",
                "number_of_suppliers",
                "total_selected_orders",
            ],
            "value": [
                hhi,
                effective_supplier_count,
                top1_share,
                int(len(supplier_selection)),
                int(supplier_selection["selected_orders"].sum()),
            ],
        }
    )


def analyze_supplier_dependency(
    relations: pd.DataFrame,
    objects: pd.DataFrame,
    supplier_rel: pd.DataFrame,
    eid: str,
    oid: str,
    otype: str,
) -> pd.DataFrame:
    """
    Supplementary metric:
    fraction of unique Order objects associated with each Supplier.

    In the current simulation this may closely mirror selection share,
    so it is exported for traceability but need not be reported as an
    independent BQ4 finding.
    """
    order_rel = (
        relations.loc[
            relations[otype] == "Order",
            [eid, oid],
        ]
        .drop_duplicates()
        .rename(columns={oid: "order"})
    )

    supplier_events = (
        supplier_rel[[eid, oid]]
        .rename(columns={oid: "supplier"})
        .drop_duplicates()
    )

    supplier_order = (
        supplier_events
        .merge(order_rel, on=eid, how="inner")
        .drop_duplicates(["supplier", "order"])
    )

    all_suppliers = sorted(supplier_events["supplier"].dropna().unique())

    total_orders = objects.loc[
        objects[otype] == "Order",
        oid,
    ].nunique()

    dependency = (
        supplier_order
        .groupby("supplier")
        .agg(order_count=("order", "nunique"))
        .reindex(all_suppliers, fill_value=0)
        .reset_index()
    )

    dependency["total_orders"] = total_orders

    if total_orders > 0:
        dependency["order_dependency_share"] = (
            dependency["order_count"] / total_orders
        )
    else:
        dependency["order_dependency_share"] = np.nan

    return dependency.sort_values(
        ["order_dependency_share", "supplier"],
        ascending=[False, True],
    ).reset_index(drop=True)


# ============================================================
# Output functions
# ============================================================

def save_results(
    results: Dict[str, pd.DataFrame],
    tables_dir: Path,
) -> Path:
    """Save CSV tables and a consolidated Excel workbook."""
    csv_names = {
        "Resource_Workload": "resource_workload.csv",
        "Resource_Activity": "resource_activity_distribution.csv",
        "Resource_Coverage": "resource_object_coverage.csv",
        "Resource_Temporal_Monthly": "resource_temporal_monthly.csv",
        "Resource_Temporal_Weekly": "resource_temporal_weekly.csv",
        "Supplier_Participation": "supplier_participation.csv",
        "Supplier_Selection": "supplier_selection.csv",
        "Supplier_Concentration": "supplier_concentration.csv",
        "Supplier_Dependency": "supplier_dependency.csv",
    }

    for key, filename in csv_names.items():
        results[key].to_csv(
            tables_dir / filename,
            index=False,
        )

    excel_path = tables_dir / "BQ4_PM4Py_results.xlsx"

    try:
        with pd.ExcelWriter(
            excel_path,
            engine="openpyxl",
        ) as writer:
            for sheet_name, df in results.items():
                prepare_for_excel(df).to_excel(
                    writer,
                    sheet_name=sheet_name[:31],
                    index=False,
                )
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "openpyxl is required to create BQ4_PM4Py_results.xlsx.\n"
            "Install it in the active environment with:\n"
            "    pip install openpyxl"
        ) from exc

    return excel_path


def save_metadata(
    metadata_path: Path,
    input_file: Path,
    ocel,
    results: Dict[str, pd.DataFrame],
) -> None:
    """Save analysis definitions and software/data provenance."""
    metadata = {
        "analysis": "BQ4 PM4Py resource and supplier analysis",
        "input_file": str(input_file.resolve()),
        "input_sha256": sha256_file(input_file),
        "software": {
            "pm4py": getattr(pm4py, "__version__", "unknown"),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "ocel_summary": {
            "events": int(len(ocel.events)),
            "objects": int(len(ocel.objects)),
            "relations": int(len(ocel.relations)),
            "object_types": sorted(pm4py.ocel_get_object_types(ocel)),
        },
        "definitions": {
            "resource_workload": (
                "Number of unique events in which a Resource object participates."
            ),
            "resource_workload_share_denominator": (
                "Sum of unique event participations across all Resource objects."
            ),
            "resource_coverage": (
                "Unique business objects associated with a Resource through shared "
                "events, divided by the total number of objects of that type."
            ),
            "business_object_types_for_coverage": BUSINESS_TYPES,
            "supplier_participation": (
                "Number of unique events in which a Supplier object participates."
            ),
            "supplier_selection": (
                f"Supplier participation in activity "
                f"'{SUPPLIER_SELECTION_ACTIVITY}'."
            ),
            "supplier_concentration_hhi": (
                "Sum of squared supplier selection shares; used descriptively."
            ),
            "supplier_effective_count": "1 / HHI.",
            "supplier_dependency": (
                "Unique Order objects associated with each Supplier divided by "
                "the total number of Order objects; supplementary metric."
            ),
        },
        "output_rows": {
            name: int(len(df))
            for name, df in results.items()
        },
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def export_ocdfg(ocel, figures_dir: Path) -> None:
    """
    Optionally export full OC-DFG overview figures.

    These are supplementary overview figures and are not required for
    the main BQ4 findings. Graphviz may be required by the local PM4Py
    visualization setup.
    """
    print("\nDiscovering optional OC-DFG...")

    ocdfg = pm4py.discover_ocdfg(ocel)

    pm4py.save_vis_ocdfg(
        ocdfg,
        str(figures_dir / "BQ4_OCDFG_frequency.png"),
        annotation="frequency",
    )

    pm4py.save_vis_ocdfg(
        ocdfg,
        str(figures_dir / "BQ4_OCDFG_performance.png"),
        annotation="performance",
        performance_aggregation="mean",
    )

    print("OC-DFG figures saved.")


# ============================================================
# Main pipeline
# ============================================================

def run(input_file: Path, out_dir: Path, make_ocdfg: bool = False) -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input OCEL not found: {input_file}")

    tables_dir = out_dir / "tables"
    figures_dir = out_dir / "figures"
    metadata_dir = out_dir / "metadata"

    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("BQ4 - PM4Py RESOURCE AND SUPPLIER ANALYSIS")
    print("=" * 72)
    print(f"Input: {input_file.resolve()}")
    print(f"Output: {out_dir.resolve()}")

    # --------------------------------------------------------
    # Load OCEL 2.0
    # --------------------------------------------------------
    print("\nLoading OCEL 2.0 with PM4Py...")

    ocel = pm4py.read_ocel2(str(input_file))

    eid = ocel.event_id_column
    act = ocel.event_activity
    time_col = ocel.event_timestamp
    oid = ocel.object_id_column
    otype = ocel.object_type_column

    events = ocel.events.copy()
    objects = ocel.objects.copy()
    relations = ocel.relations.copy()

    relations[time_col] = pd.to_datetime(
        relations[time_col],
        utc=True,
    )

    available_types = set(pm4py.ocel_get_object_types(ocel))

    ensure_object_types(
        available_types,
        [RESOURCE_TYPE, SUPPLIER_TYPE],
        "actor",
    )

    present_business_types = [
        x for x in BUSINESS_TYPES
        if x in available_types
    ]

    if not present_business_types:
        raise ValueError(
            "None of the configured business object types were found.\n"
            f"Configured: {BUSINESS_TYPES}\n"
            f"Available: {sorted(available_types)}"
        )

    # Coverage should reflect the configured BQ4 scope.
    missing_business_types = [
        x for x in BUSINESS_TYPES
        if x not in available_types
    ]

    if missing_business_types:
        print(
            "\nWARNING: The following configured business object types "
            f"are absent and will have zero/NaN coverage: {missing_business_types}"
        )

    print("OCEL loaded.")
    print(f"Events: {len(events)}")
    print(f"Objects: {len(objects)}")
    print(f"Relations: {len(relations)}")
    print(f"Object types: {sorted(available_types)}")

    # --------------------------------------------------------
    # Resource analysis
    # --------------------------------------------------------
    resource_rel, resource_workload = analyze_resource_workload(
        relations,
        eid,
        act,
        time_col,
        oid,
        otype,
    )

    resource_activity = analyze_resource_activity(
        resource_rel,
        eid,
        act,
        oid,
    )

    resource_coverage = analyze_resource_coverage(
        relations,
        objects,
        resource_rel,
        eid,
        oid,
        otype,
    )

    resource_monthly, resource_weekly = analyze_resource_temporal(
        resource_rel,
        eid,
        time_col,
        oid,
    )

    # --------------------------------------------------------
    # Supplier analysis
    # --------------------------------------------------------
    supplier_rel, supplier_participation = analyze_supplier_participation(
        relations,
        eid,
        act,
        oid,
        otype,
    )

    supplier_selection = analyze_supplier_selection(
        supplier_rel,
        eid,
        act,
        oid,
    )

    supplier_concentration = analyze_supplier_concentration(
        supplier_selection
    )

    supplier_dependency = analyze_supplier_dependency(
        relations,
        objects,
        supplier_rel,
        eid,
        oid,
        otype,
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------
    results = {
        "Resource_Workload": resource_workload,
        "Resource_Activity": resource_activity,
        "Resource_Coverage": resource_coverage,
        "Resource_Temporal_Monthly": resource_monthly,
        "Resource_Temporal_Weekly": resource_weekly,
        "Supplier_Participation": supplier_participation,
        "Supplier_Selection": supplier_selection,
        "Supplier_Concentration": supplier_concentration,
        "Supplier_Dependency": supplier_dependency,
    }

    print_table("RESOURCE WORKLOAD", resource_workload)
    print_table("RESOURCE × ACTIVITY", resource_activity)
    print_table("RESOURCE BUSINESS-OBJECT COVERAGE", resource_coverage)
    print_table("SUPPLIER PARTICIPATION", supplier_participation)
    print_table("SUPPLIER SELECTION", supplier_selection)
    print_table("SUPPLIER CONCENTRATION", supplier_concentration)

    # --------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------
    excel_path = save_results(
        results,
        tables_dir,
    )

    metadata_path = metadata_dir / "bq4_pm4py_metadata.json"

    save_metadata(
        metadata_path,
        input_file,
        ocel,
        results,
    )

    # Optional full OC-DFG
    if make_ocdfg:
        export_ocdfg(
            ocel,
            figures_dir,
        )

    print("\n" + "=" * 72)
    print("BQ4 PM4Py ANALYSIS COMPLETED")
    print("=" * 72)
    print(f"Excel workbook: {excel_path.resolve()}")
    print(f"Metadata:       {metadata_path.resolve()}")
    print(f"CSV tables:     {tables_dir.resolve()}")

    hhi = supplier_concentration.loc[
        supplier_concentration["metric"] == "HHI",
        "value",
    ].iloc[0]

    effective = supplier_concentration.loc[
        supplier_concentration["metric"] == "effective_supplier_count",
        "value",
    ].iloc[0]

    top1 = supplier_concentration.loc[
        supplier_concentration["metric"] == "top1_selection_share",
        "value",
    ].iloc[0]

    print("\nSupplier concentration summary:")
    print(f"HHI: {hhi:.6f}")
    print(f"Effective supplier count: {effective:.6f}")
    print(f"Top-1 selection share: {top1:.4%}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reproducible PM4Py resource and supplier "
            "analysis tables for BQ4."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the source OCEL 2.0 file.",
    )

    parser.add_argument(
        "--out",
        default="results/BQ4",
        help="BQ4 output directory (default: results/BQ4).",
    )

    parser.add_argument(
        "--export-ocdfg",
        action="store_true",
        help=(
            "Also export frequency/performance OC-DFG overview figures. "
            "This is optional and may require Graphviz."
        ),
    )

    args = parser.parse_args()

    run(
        input_file=Path(args.input),
        out_dir=Path(args.out),
        make_ocdfg=args.export_ocdfg,
    )


if __name__ == "__main__":
    main()
