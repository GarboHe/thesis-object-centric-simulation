# -*- coding: utf-8 -*-
"""
Generate BQ4 thesis figures directly from PM4Py and OCPA Excel result tables.

Usage:
    python generate_bq4_figures_from_excel.py ^
        --pm4py "D:\IAProcessCPN\results\BQ4\BQ4_PM4Py_results.xlsx" ^
        --ocpa "D:\IAProcessCPN\results\BQ4\OCPA\BQ4_OCPA_results.xlsx" ^
        --out "D:\IAProcessCPN\results\BQ4\figures"

Required packages:
    pandas
    matplotlib
    openpyxl
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter


# ============================================================
# Visual style
# ============================================================

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": "#777777",
    "axes.labelcolor": "#333333",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "text.color": "#222222",
    "font.size": 10,
})

MUTED_BLUE = "#A9C3D8"
MUTED_BLUE_EDGE = "#7B9BB4"
MUTED_GREEN = "#C7D9B7"
MUTED_GREEN_EDGE = "#94AE7E"
MUTED_PURPLE = "#C9C3DB"
MUTED_PURPLE_EDGE = "#9B93B6"

HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "muted_teal",
    ["#FFFFFF", "#EEF5F3", "#D7E8E4", "#BCD7D1", "#98BFB7"]
)


def save_figure(fig, out_dir: Path, stem: str):
    """Save both PNG (300 dpi) and SVG."""
    png = out_dir / f"{stem}.png"
    svg = out_dir / f"{stem}.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved: {png}")
    print(f"Saved: {svg}")


# ============================================================
# Figure 1 — Resource workload
# Excel:
#   PM4Py workbook -> Resource_Workload
# Required columns:
#   resource, event_count
# ============================================================

def plot_resource_workload(pm4py_file: Path, out_dir: Path):
    df = pd.read_excel(pm4py_file, sheet_name="Resource_Workload")

    required = {"resource", "event_count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Resource_Workload missing columns: {sorted(missing)}")

    df = df[["resource", "event_count"]].copy()
    df = df.sort_values("event_count", ascending=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(
        df["resource"],
        df["event_count"],
        color=MUTED_BLUE,
        edgecolor=MUTED_BLUE_EDGE
    )

    ax.set_title("Event-based Resource Workload Distribution", fontsize=16, pad=14)
    ax.set_xlabel("Resource")
    ax.set_ylabel("Number of Events")
    ax.grid(axis="y", alpha=0.18)

    for bar, value in zip(bars, df["event_count"]):
        ax.annotate(
            f"{int(value)}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9
        )

    fig.tight_layout()
    save_figure(fig, out_dir, "BQ4_resource_workload")


# ============================================================
# Figure 2 — Resource × Activity heatmap
# Excel:
#   PM4Py workbook -> Resource_Activity
# Required columns:
#   resource, activity, event_count
# ============================================================

def plot_resource_activity_heatmap(pm4py_file: Path, out_dir: Path):
    df = pd.read_excel(pm4py_file, sheet_name="Resource_Activity")

    required = {"resource", "activity", "event_count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Resource_Activity missing columns: {sorted(missing)}")

    pivot = df.pivot_table(
        index="resource",
        columns="activity",
        values="event_count",
        aggfunc="sum",
        fill_value=0
    )

    # Keep resource order based on total workload.
    resource_order = (
        pivot.sum(axis=1)
        .sort_values(ascending=False)
        .index
        .tolist()
    )
    pivot = pivot.loc[resource_order]

    # Order activities approximately by process flow / first appearance.
    activity_order = df["activity"].drop_duplicates().tolist()
    activity_order = [a for a in activity_order if a in pivot.columns]
    pivot = pivot[activity_order]

    matrix = pivot.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(16, 6.5))
    im = ax.imshow(matrix, aspect="auto", cmap=HEATMAP_CMAP)

    ax.set_title("Resource–Activity Participation Heatmap", fontsize=16, pad=14)
    ax.set_xlabel("Activity")
    ax.set_ylabel("Resource")

    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)

    max_value = matrix.max() if matrix.size else 0
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            if value > 0:
                text_color = "white" if max_value and value >= max_value * 0.65 else "#263532"
                ax.text(
                    j, i, f"{int(value)}",
                    ha="center", va="center",
                    fontsize=9,
                    color=text_color
                )

    cbar = fig.colorbar(im, ax=ax, pad=0.01)
    cbar.set_label("Number of events")

    fig.tight_layout()
    save_figure(fig, out_dir, "BQ4_resource_activity_heatmap")


# ============================================================
# Figure 3 — Supplier participation vs selection
# Excel:
#   PM4Py workbook -> Supplier_Participation
#   PM4Py workbook -> Supplier_Selection
#
# Required columns:
#   supplier, participation_share
#   supplier, selection_share
# ============================================================

def plot_supplier_participation_selection(pm4py_file: Path, out_dir: Path):
    participation = pd.read_excel(
        pm4py_file,
        sheet_name="Supplier_Participation"
    )[["supplier", "participation_share"]]

    selection = pd.read_excel(
        pm4py_file,
        sheet_name="Supplier_Selection"
    )[["supplier", "selection_share"]]

    df = participation.merge(selection, on="supplier", how="outer").fillna(0)
    df = df.sort_values("supplier")

    x = np.arange(len(df))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10, 6))

    bars1 = ax.bar(
        x - width / 2,
        df["participation_share"],
        width,
        label="Participation share",
        color=MUTED_BLUE,
        edgecolor=MUTED_BLUE_EDGE
    )
    bars2 = ax.bar(
        x + width / 2,
        df["selection_share"],
        width,
        label="Selection share",
        color=MUTED_GREEN,
        edgecolor=MUTED_GREEN_EDGE
    )

    ax.set_title("Supplier Participation and Selection Shares", fontsize=16, pad=14)
    ax.set_xlabel("Supplier")
    ax.set_ylabel("Share")
    ax.set_xticks(x)
    ax.set_xticklabels(df["supplier"])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(
        0,
        max(df["participation_share"].max(), df["selection_share"].max()) * 1.25
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.18)

    for bars in (bars1, bars2):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1%}",
                (bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9
            )

    fig.tight_layout()
    save_figure(fig, out_dir, "BQ4_supplier_participation_vs_selection")


# ============================================================
# Figure 4 — Activity interaction hotspots
# Excel:
#   OCPA workbook -> 07_activity_hotspots
#
# Required columns:
#   activity
#   multi_object_events
#   mean_object_type_breadth
# ============================================================

def plot_activity_interaction_hotspots(ocpa_file: Path, out_dir: Path):
    df = pd.read_excel(ocpa_file, sheet_name="07_activity_hotspots")

    required = {
        "activity",
        "multi_object_events",
        "mean_object_type_breadth"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"07_activity_hotspots missing columns: {sorted(missing)}")

    df = df[
        ["activity", "multi_object_events", "mean_object_type_breadth"]
    ].copy()

    # Largest interaction breadth at the top.
    df = df.sort_values(
        ["mean_object_type_breadth", "multi_object_events"],
        ascending=[True, True]
    )

    fig, ax = plt.subplots(figsize=(12, 9))

    bars = ax.barh(
        df["activity"],
        df["mean_object_type_breadth"],
        color=MUTED_PURPLE,
        edgecolor=MUTED_PURPLE_EDGE
    )

    ax.set_title("Cross-Object Interaction Breadth by Activity", fontsize=16, pad=14)
    ax.set_xlabel("Mean number of business-object types per cross-object event")
    ax.set_ylabel("Activity")
    ax.set_xlim(0, max(7.0, df["mean_object_type_breadth"].max() * 1.28))
    ax.grid(axis="x", alpha=0.18)

    for bar, breadth, n_events in zip(
        bars,
        df["mean_object_type_breadth"],
        df["multi_object_events"]
    ):
        ax.annotate(
            f"{breadth:.2f}  |  n={int(n_events)}",
            (bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9
        )

    fig.tight_layout()
    save_figure(fig, out_dir, "BQ4_activity_interaction_hotspots")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate BQ4 figures directly from PM4Py/OCPA Excel tables."
    )
    parser.add_argument(
        "--pm4py",
        required=True,
        help="Path to BQ4_PM4Py_results.xlsx"
    )
    parser.add_argument(
        "--ocpa",
        required=True,
        help="Path to BQ4_OCPA_results.xlsx"
    )
    parser.add_argument(
        "--out",
        default="results/BQ4/figures",
        help="Output folder for PNG and SVG figures"
    )
    args = parser.parse_args()

    pm4py_file = Path(args.pm4py)
    ocpa_file = Path(args.ocpa)
    out_dir = Path(args.out)

    if not pm4py_file.exists():
        raise FileNotFoundError(f"PM4Py workbook not found: {pm4py_file}")
    if not ocpa_file.exists():
        raise FileNotFoundError(f"OCPA workbook not found: {ocpa_file}")

    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generating BQ4 figures...")
    plot_resource_workload(pm4py_file, out_dir)
    plot_resource_activity_heatmap(pm4py_file, out_dir)
    plot_supplier_participation_selection(pm4py_file, out_dir)
    plot_activity_interaction_hotspots(ocpa_file, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
