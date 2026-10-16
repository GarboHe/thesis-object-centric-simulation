#!/usr/bin/env python3
"""Reproduce what-if figures and the overall comparison from archived CSV inputs.

OCPQ exports provide the per-Requirement durations. The scenario summary
provides the reported log-level descriptors used in Table 4.14.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path
import re
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DAY = Decimal(86400)
SCENARIOS = ("baseline", "high_volume")
NAMES = {"baseline": "Baseline", "high_volume": "High-volume"}
STAGES = (
    ("S1", "requirement_stage", "Requirement and\nquotation acquisition"),
    ("S2", "sourcing_order_stage", "Evaluation, contracting,\nand ordering"),
    ("S3", "fulfilment_prereq_stage", "Fulfilment, acceptance,\nand accounting readiness"),
    ("S4", "accounting_posting_stage", "Accounting processing\nand posting"),
)
INTERVALS = (
    ("d1", "Submit requirement →\nfirst review"),
    ("d2", "Final review →\nobtain quotations"),
    ("d3", "Obtain quotations →\nquotation evaluation"),
    ("d4", "Contract-need check →\npurchase-order creation"),
    ("d5", "Purchase-order creation →\ndeliverable receipt"),
    ("d6", "Deliverable receipt →\nfirst acceptance"),
)
BLUE, RED = "#4C78A8", "#E45756"
STAGE_COLORS = (BLUE, "#F2A541", "#59A14F", "#B279A2")
DURATION = re.compile(
    r"^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?"
    r"(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
)



def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: empty export")
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"{path}: malformed CSV row")
    return rows


def duration_seconds(raw: str) -> Decimal:
    """Convert an ISO elapsed-duration label to seconds."""
    match = DURATION.fullmatch(raw.strip())
    if not match or not any(x is not None for x in match.groups()):
        raise ValueError(f"Invalid or negative OCPQ duration: {raw!r}")
    parts = [Decimal(x or 0) for x in match.groups()]
    return sum((a * b for a, b in zip(parts, (86400, 3600, 60, 1))), Decimal(0))


def mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def summary(values: list[Decimal]) -> dict:
    return {"n": len(values), "mean_days": mean(values) / DAY,
            "median_days": statistics.median(values) / DAY,
            "min_days": min(values) / DAY, "max_days": max(values) / DAY}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_bindings(rows, source):
    ids = [r["o1"] for r in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{source}: Requirement IDs must be nonempty and unique")
    if any(r["Satisfied"].strip().lower() != "true" for r in rows):
        raise ValueError(f"{source}: an unsatisfied binding was exported")


def load_inputs(root: Path):
    stage_rows, diagnostic_rows, comparisons, totals, checks = [], [], [], {}, {}
    for scenario in SCENARIOS:
        folder = root / "data" / "ocpq" / scenario
        mp = root.parent / "ocpq_shared/baseline_milestone.csv" if scenario == "baseline" else folder / "milestone.csv"
        dp = folder / "diagnostic.csv"
        common = {"o1", "o1.demand_source", "Satisfied", *(f"e{i}" for i in range(1, 6))}
        milestones = read_csv(mp, common | {"e2e_duration", *(x[1] for x in STAGES)})
        diagnostics = read_csv(dp, common | {*(x[0] for x in INTERVALS), "nr", "na"})
        validate_bindings(milestones, mp)
        validate_bindings(diagnostics, dp)
        index = {r["o1"]: r for r in milestones}
        if set(index) != {r["o1"] for r in diagnostics}:
            raise ValueError(f"{scenario}: milestone and diagnostic cohorts differ")
        for row in diagnostics:
            parent = index[row["o1"]]
            for key in ("o1.demand_source", *(f"e{i}" for i in range(1, 6))):
                if row[key] != parent[key]:
                    raise ValueError(f"{scenario}, {row['o1']}: {key} binding differs")
            if any(int(row[k]) < 1 for k in ("nr", "na")):
                raise ValueError(f"{scenario}: missing eligible review or acceptance")
        e2e = [duration_seconds(r["e2e_duration"]) for r in milestones]
        max_residual = Decimal(0)
        for row, total in zip(milestones, e2e):
            residual = abs(sum((duration_seconds(row[k]) for _, k, _ in STAGES), Decimal(0)) - total)
            max_residual = max(max_residual, residual)
        if max_residual != 0:
            raise ValueError(f"{scenario}: S1-S4 do not sum exactly to E2E")
        aggregate_e2e = sum(e2e, Decimal(0))
        if aggregate_e2e <= 0:
            raise ValueError(f"{scenario}: aggregate E2E must be positive")
        totals[scenario] = {"posted_requirements": len(milestones), **summary(e2e)}
        for stage, column, _ in STAGES:
            values = [duration_seconds(r[column]) for r in milestones]
            stage_rows.append({"scenario": scenario, "stage": stage, **summary(values),
                               "share_percent": sum(values, Decimal(0)) / aggregate_e2e * 100})
        for key, label in INTERVALS:
            values = [duration_seconds(r[key]) for r in diagnostics]
            diagnostic_rows.append({"scenario": scenario, "interval": key,
                                    "description": label.replace("\n", " "), **summary(values)})
        checks[scenario] = {"milestone_rows": len(milestones), "diagnostic_rows": len(diagnostics),
                            "one_satisfied_row_per_requirement": True,
                            "same_requirement_cohort": True, "same_e1_to_e5_bindings": True,
                            "max_stage_sum_residual_seconds": str(max_residual),
                            "requirements_with_multiple_reviews": sum(int(r["nr"]) > 1 for r in diagnostics),
                            "requirements_with_multiple_acceptances": sum(int(r["na"]) > 1 for r in diagnostics)}
    for key, label in INTERVALS:
        b, h = [next(r["mean_days"] for r in diagnostic_rows if r["scenario"] == s and r["interval"] == key) for s in SCENARIOS]
        if b <= 0:
            raise ValueError(f"{key}: a positive baseline mean is required for a ratio and log axis")
        comparisons.append({"interval": key, "description": label.replace("\n", " "),
                            "baseline_mean_days": b, "high_volume_mean_days": h,
                            "ratio_high_over_baseline": h / b, "absolute_increase_days": h - b,
                            "baseline_display": f"{b:.2f}", "high_volume_display": f"{h:.2f}",
                            "ratio_display": f"{h / b:.1f}", "increase_display": f"{h - b:.2f}"})
    return stage_rows, diagnostic_rows, comparisons, totals, checks


def save_figure(fig, output, stem):
    fig.savefig(output / f"{stem}.pdf", bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def plot_diagnostics(comparisons, output):
    fig, ax = plt.subplots(figsize=(9.4, 5.8))
    y = np.arange(len(INTERVALS))
    baseline = np.array([float(r["baseline_mean_days"]) for r in comparisons])
    high = np.array([float(r["high_volume_mean_days"]) for r in comparisons])
    winner = max(range(len(comparisons)), key=lambda i: comparisons[i]["absolute_increase_days"])
    ax.axhspan(winner - 0.45, winner + 0.45, color="#FFF1CC", alpha=.8, zorder=0)
    for yi, b, h in zip(y, baseline, high):
        ax.plot([b, h], [yi, yi], color="#AAAAAA", lw=1.8, zorder=1)
    ax.scatter(baseline, y, s=43, color=BLUE, label="Baseline", zorder=3)
    ax.scatter(high, y, s=46, marker="s", color=RED, label="High-volume", zorder=3)
    for yi, b, h, row in zip(y, baseline, high, comparisons):
        ax.annotate(row["baseline_display"], (b, yi), xytext=(0, -12), textcoords="offset points",
                    ha="center", va="center", color=BLUE, fontsize=9.3, fontweight="semibold")
        ax.annotate(f"{row['high_volume_display']}  (×{row['ratio_display']})", (h, yi),
                    xytext=(5, 0), textcoords="offset points", ha="left", va="center",
                    color=RED, fontsize=9.3, fontweight="semibold")
    ax.annotate(f"Largest absolute increase: +{comparisons[winner]['increase_display']} days",
                (high[winner], winner), xytext=(.995, .96), textcoords="axes fraction",
                ha="right", va="top", color="#705414", fontsize=9.2, fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": "#8C6D1F", "lw": .9})
    ax.set_xscale("log")
    ax.set_xlim(min(baseline.min(), high.min()) * .64, max(baseline.max(), high.max()) * 12)
    ax.set_ylim(5.55, -.6)
    ax.set_yticks(y, labels=[label for _, label in INTERVALS], fontsize=9.5)
    ax.set_xlabel("Mean interval duration (calendar days; log scale)", fontsize=9.5)
    ax.set_title("Diagnostic localisation of delay under increased volume", loc="left",
                 fontsize=12, fontweight="bold", pad=15)
    ax.grid(axis="x", color="#D9D9D9", lw=.7, alpha=.85)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right", fontsize=9.3)
    fig.subplots_adjust(left=.305, right=.985, top=.88, bottom=.16)
    fig.text(.305, .035, "Means: 2 decimals. Ratios: unrounded high-volume mean / baseline mean.",
             fontsize=8.1, color="#555555")
    save_figure(fig, output, "interval_diagnostics")


def plot_stages(rows, output):
    fig, (absolute, share) = plt.subplots(1, 2, figsize=(11.7, 5.25),
        gridspec_kw={"width_ratios": [1.42, 1], "wspace": .34})
    means = {s: np.array([float(next(r["mean_days"] for r in rows if r["scenario"] == s and r["stage"] == k)) for k, _, _ in STAGES]) for s in SCENARIOS}
    shares = np.array([[float(next(r["share_percent"] for r in rows if r["scenario"] == s and r["stage"] == k)) for k, _, _ in STAGES] for s in SCENARIOS])
    y, height = np.arange(4), .30
    for s, offset, color in (("baseline", height/1.7, BLUE), ("high_volume", -height/1.7, RED)):
        absolute.barh(y+offset, means[s], height=height, color=color, label=NAMES[s])
        for yi, value in zip(y, means[s]):
            absolute.annotate(f"{value:.2f}", (value, yi+offset), xytext=(4,0), textcoords="offset points",
                              ha="left", va="center", color=color, fontsize=9, fontweight="semibold")
    absolute.set_xscale("log")
    absolute.set_xlim(.01, max(v.max() for v in means.values())*2.7)
    absolute.set_yticks(y, labels=[f"{k}  {label}" for k, _, label in STAGES], fontsize=9.3)
    absolute.invert_yaxis()
    absolute.set_xlabel("Mean stage duration (calendar days; log scale)", fontsize=9.3)
    absolute.set_title("(a) Absolute mean duration", loc="left", fontsize=11, fontweight="bold")
    absolute.legend(frameon=False, loc="lower right", fontsize=9)
    left = np.zeros(2)
    for i, color in enumerate(STAGE_COLORS):
        bars = share.barh(["Baseline", "High-volume"], shares[:, i], left=left,
                          height=.48, color=color, label=STAGES[i][0])
        for bar, value in zip(bars, shares[:, i]):
            if value >= 6:
                share.text(bar.get_x()+bar.get_width()/2, bar.get_y()+bar.get_height()/2,
                           f"{value:.1f}%", ha="center", va="center", fontsize=9,
                           color="white" if i in (0,2,3) else "#333333", fontweight="bold")
        left += shares[:, i]
    share.set_xlim(0, 100)
    share.invert_yaxis()
    share.set_xlabel("Share of aggregate elapsed time (%)", fontsize=9.3)
    share.set_title("(b) Temporal composition", loc="left", fontsize=11, fontweight="bold")
    share.legend(title="Stage", ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(.5,-.16),
                 columnspacing=1, handlelength=1.2, fontsize=9, title_fontsize=9)
    for ax in (absolute, share):
        ax.grid(axis="x", color="#D9D9D9", lw=.7, alpha=.85)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    share.spines["left"].set_visible(False)
    share.tick_params(axis="y", length=0)
    fig.suptitle("Stage-level comparison of baseline and high-volume scenarios",
                 x=.055, y=.99, ha="left", fontsize=12.5, fontweight="bold")
    fig.subplots_adjust(left=.27, right=.98, top=.85, bottom=.22)
    save_figure(fig, output, "stage_comparison")


def overall_comparison(root, totals):
    rows = read_csv(root / "data" / "scenario_summary.csv", {
        "scenario", "submitted_requirements", "arrival_span_days", "drain_down_days", "source"})
    scenario_values = {}
    for row in rows:
        scenario = row["scenario"]
        if scenario not in SCENARIOS or scenario in scenario_values:
            raise ValueError("scenario_summary.csv must contain each scenario exactly once")
        submitted = int(row["submitted_requirements"])
        arrival = Decimal(row["arrival_span_days"])
        drain = Decimal(row["drain_down_days"])
        if submitted < totals[scenario]["posted_requirements"]:
            raise ValueError(f"{scenario}: submitted count is below posted count")
        if any(not v.is_finite() or v < 0 for v in (arrival, drain)) or not row["source"].strip():
            raise ValueError(f"{scenario}: invalid scenario summary")
        scenario_values[scenario] = {"submitted_requirements": submitted,
                                     "arrival_span_days": arrival, "drain_down_days": drain}
    if set(scenario_values) != set(SCENARIOS):
        raise ValueError("scenario_summary.csv must contain both scenarios")
    specs = [
        ("submitted_requirements", "Submitted Requirements", "reported scenario summary"),
        ("arrival_span_days", "Requirement-arrival span (days)", "reported scenario summary"),
        ("posted_requirements", "Posted Requirements", "computed from OCPQ milestone export"),
        ("mean_days", "Mean submission-to-posting elapsed time (days)", "computed from OCPQ milestone export"),
        ("median_days", "Median submission-to-posting elapsed time (days)", "computed from OCPQ milestone export"),
        ("drain_down_days", "Drain-down after final arrival (days)", "reported scenario summary"),
    ]
    result = []
    for key, label, provenance in specs:
        values = {s: (totals[s] if key in totals[s] else scenario_values[s])[key] for s in SCENARIOS}
        result.append({"metric": key, "measure": label, **values, "source": provenance})
    return result


def write_latex_table(path, rows):
    lines = [r"\begin{tabular}{lrr}", r"\hline",
             r"Measure & Baseline & High-volume what-if \\", r"\hline"]
    for row in rows:
        values = [(f"{int(row[s]):,}" if "requirements" in row["metric"] else f"{row[s]:.2f}") for s in SCENARIOS]
        lines.append(f"{row['measure']} & {values[0]} & {values[1]} " + r"\\")
    lines.extend([r"\hline", r"\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, help="Output directory; defaults to ROOT/results")
    parser.add_argument("--latex", action="store_true", help="Also generate the LaTeX comparison table.")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir.resolve() if args.output_dir else root / "results"
    try:
        stages, diagnostics, comparison, totals, checks = load_inputs(root)
        overall = overall_comparison(root, totals)
        output.mkdir(parents=True, exist_ok=True)
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                             "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
                             "axes.edgecolor": "#777777", "axes.linewidth": .8,
                             "xtick.color": "#333333", "ytick.color": "#333333"})
        write_csv(output / "overall_comparison.csv", overall)
        if args.latex:
            write_latex_table(output / "overall_comparison.tex", overall)
        plot_stages(stages, output)
        plot_diagnostics(comparison, output)
        print(f"Generated overall comparison, stage comparison and interval diagnostics in {output}")
    except (ValueError, OSError, KeyError, ArithmeticError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
