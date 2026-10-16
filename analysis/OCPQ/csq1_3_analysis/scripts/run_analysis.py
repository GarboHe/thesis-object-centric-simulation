#!/usr/bin/env python3
"""Reproduce CSQ1-CSQ3 descriptive results from archived OCPQ CSV exports."""
from __future__ import annotations

import re
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data/ocpq_exports"
SHARED = ROOT.parent / "ocpq_shared"
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
LATEX = False
DAY = 86400.0
STAGES = {
    "S1": ("Requirement and quotation acquisition", "Submit Requirement", "Obtain Quotations", "requirement_stage"),
    "S2": ("Quotation evaluation, contracting, and ordering", "Obtain Quotations", "Create Purchase Order", "sourcing_order_stage"),
    "S3": ("Fulfilment, acceptance, and accounting readiness", "Create Purchase Order", "Verify Accounting Prerequisites", "fulfilment_prereq_stage"),
    "S4": ("Accounting processing and posting", "Verify Accounting Prerequisites", "Post Accounting Voucher", "accounting_posting_stage"),
    "E2E": ("End-to-end", "Submit Requirement", "Post Accounting Voucher", "e2e_duration"),
}
ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "svg.hashsalt": "csq1-3"})


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def boolean(value) -> bool:
    text = str(value).strip().lower()
    check(text in {"true", "false"}, f"Invalid OCPQ Boolean: {value!r}")
    return text == "true"


def read_export(name: str, columns: list[str], rows: int) -> pd.DataFrame:
    path = SHARED / "baseline_milestone.csv" if name == "csq1_milestone_situation_table.csv" else EXPORTS / name
    data = pd.read_csv(path, dtype=str, keep_default_na=False)
    check(set(columns) <= set(data), f"Missing columns in {name}: {set(columns) - set(data)}")
    check(len(data) == rows, f"{name}: expected {rows} archived rows, found {len(data)}")
    check(not data[columns].eq("").any().any(), f"Missing required value in {name}")
    if "Satisfied" in data:
        check(data["Satisfied"].map(boolean).all(), f"Unsatisfied binding in {name}")
    return data


def unique(data: pd.DataFrame, columns: list[str], name: str) -> None:
    check(not data.duplicated(columns).any(), f"Duplicate {columns} in {name}")


def seconds(value: str) -> float:
    """Parse an OCPQ duration label; event timestamps are never used."""
    match = ISO_DURATION.fullmatch(value)
    check(match is not None and value not in {"P", "PT"}, f"Invalid duration: {value!r}")
    parts = match.groupdict()
    return sum(float(parts[key] or 0) * factor for key, factor in
               [("days", DAY), ("hours", 3600), ("minutes", 60), ("seconds", 1)])


def describe(values: pd.Series) -> dict:
    return {"n": int(len(values)), "mean": float(values.mean()),
            "median": float(values.median()),
            "q1": float(values.quantile(.25, interpolation="linear")),
            "q3": float(values.quantile(.75, interpolation="linear")),
            "min": float(values.min()), "max": float(values.max())}


def save_plot(fig, stem: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def tex_escape(value) -> str:
    mapping = {"&": r"\&", "%": r"\%", "_": r"\_", "#": r"\#", "$": r"\$"}
    text = "".join(mapping.get(c, c) for c in str(value)).replace(">=", r"$\geq$ ")
    activities = {activity for spec in STAGES.values() for activity in spec[1:3]}
    for activity in sorted(activities, key=len, reverse=True):
        text = text.replace(activity, r"\emph{" + activity + "}")
    return text


def save_tex(stem: str, caption: str, headers: list[str], rows: list[list], specification: str) -> None:
    if not LATEX:
        return
    lines = [r"\begin{table}[tbp]", r"\centering\footnotesize", r"\setlength{\tabcolsep}{3pt}",
             r"\caption{" + caption + "}", r"\label{tab:" + stem + "}",
             r"\begin{tabularx}{\linewidth}{" + specification + "}", r"\toprule",
             " & ".join(headers) + r" \\", r"\midrule"]
    lines += [" & ".join(tex_escape(cell) for cell in row) + r" \\" for row in rows]
    lines += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    (TABLES / f"{stem}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def csq1() -> tuple[pd.DataFrame, dict]:
    columns = ["o1", "e1", "e2", "e3", "e4", "e5", "Satisfied"] + [v[3] for v in STAGES.values()]
    raw = read_export("csq1_milestone_situation_table.csv", columns, 25)
    unique(raw, ["o1"], "CSQ1 milestone export")
    unique(raw, ["e5"], "CSQ1 post events")
    data = raw[["o1", "e1", "e2", "e3", "e4", "e5"]].rename(columns={"o1": "requirement_id"}).copy()
    for key, spec in STAGES.items():
        data[f"{key}_days"] = raw[spec[3]].map(seconds) / DAY
    check(np.allclose(data[[f"S{i}_days" for i in range(1, 5)]].sum(axis=1),
                      data["E2E_days"], rtol=0, atol=1e-10), "CSQ1 stages do not sum to E2E")

    # Match existing OCPQ exports by event ID. Do not subtract path timestamps.
    path = read_export("csq1_path_connections.csv", ["source_id", "target_id"], 25)
    unique(path, ["source_id", "target_id"], "OCPQ path connections")
    matched = path[["source_id", "target_id"]].merge(
        data[["requirement_id", "e1", "e5", "E2E_days"]],
        left_on=["source_id", "target_id"], right_on=["e1", "e5"],
        how="outer", validate="one_to_one", indicator=True)
    check(matched["_merge"].eq("both").all(), "Path and milestone event-ID pairs differ")

    statistics, rows, tex_rows = {}, [], []
    total = data["E2E_days"].sum()
    for key, (name, start, end, _) in STAGES.items():
        stats = describe(data[f"{key}_days"])
        stats["aggregate_share_percent"] = float(100 * data[f"{key}_days"].sum() / total)
        statistics[key] = stats
        rows.append({"stage": key, "description": name, "interval": f"{start} -> {end}", "n": stats["n"],
                     **{f"{k}_days": round(stats[k], 2) for k in ["mean", "median", "q1", "q3", "min", "max"]},
                     "aggregate_share_percent": round(stats["aggregate_share_percent"], 2)})
        tex_rows.append([f"{key} {name}" if key != "E2E" else name, f"{start} to {end}", stats["n"],
                         f"{stats['mean']:.2f}", f"{stats['median']:.2f}",
                         f"{stats['q1']:.2f}--{stats['q3']:.2f}", f"{stats['min']:.2f}--{stats['max']:.2f}",
                         f"{stats['aggregate_share_percent']:.2f}"])
    pd.DataFrame(rows).to_csv(TABLES / "csq1_stage_summary.csv", index=False)
    save_tex("csq1_stage_summary", "Stage-level decomposition of simulated submission-to-posting elapsed time. Durations are in calendar days.",
             ["Stage", "Interval", "N", "Mean", "Median", "Q1--Q3", "Range", "Share (\\%)"], tex_rows,
             r"@{}>{\raggedright\arraybackslash}p{.16\linewidth}>{\raggedright\arraybackslash}Xrrrrrr@{}")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot([data[f"S{i}_days"] for i in range(1, 5)], tick_labels=["S1", "S2", "S3", "S4"], whis=1.5, showfliers=True)
    ax.set(xlabel="Process stage", ylabel="Elapsed time (calendar days)",
           title="Distribution of stage durations for posted Requirements")
    save_plot(fig, "csq1_stage_duration_distribution")
    from path_figure import build_path_figure
    statistics["histogram"] = build_path_figure(matched["E2E_days"], ROOT, FIGURES)
    return data, statistics


def event_counts(name: str, rows: int, feature: str) -> pd.Series:
    raw = read_export(name, ["o1", "e1"], rows)
    unique(raw, ["o1", "e1"], name)
    if feature == "acceptance_rework_count":
        check("e1.decision" in raw and raw["e1.decision"].eq("ACCEPTANCE_REWORK").all(),
              "Acceptance-rework export contains a different decision")
    return raw.groupby("o1").size().rename(feature).rename_axis("requirement_id")


def voucher_mapping(cases: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_export("csq2_requirement_voucher_mapping.csv", ["o1", "o2", "e1"], 25)
    mapping = raw[["o1", "o2", "e1"]].rename(columns={"o1": "requirement_id", "o2": "voucher_id", "e1": "post_event_id"})
    for key in ["requirement_id", "voucher_id", "post_event_id"]:
        unique(mapping, [key], "Requirement-Voucher mapping")
    cross = cases[["requirement_id", "e5"]].merge(mapping, on="requirement_id", how="outer", validate="one_to_one", indicator=True)
    check(cross["_merge"].eq("both").all() and cross["e5"].eq(cross["post_event_id"]).all(),
          "Requirement-Voucher mapping does not match the CSQ1 posting cohort")
    raw = read_export("csq3_voucher_rework_situation_table.csv", ["o1", "e1", "e2", "Satisfied"], 3)
    rework = raw[["o1", "e1", "e2"]].rename(columns={"o1": "voucher_id", "e1": "modify_event_id", "e2": "post_event_id"})
    unique(rework, ["voucher_id", "modify_event_id", "post_event_id"], "Voucher-rework export")
    mapped = rework.merge(mapping, on=["voucher_id", "post_event_id"], how="left", validate="many_to_one", indicator=True)
    check(mapped["_merge"].eq("both").all(), "Unmatched voucher-rework binding")
    return mapping, mapped.drop(columns="_merge")


def csq2(cases: pd.DataFrame, rework: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    data = cases[["requirement_id", "S3_days", "E2E_days"]].copy()
    p75 = float(data["E2E_days"].quantile(.75, interpolation="linear"))
    data["group"] = np.where(data["E2E_days"] >= p75, "upper-tail", "remaining")
    specifications = [
        ("csq2_requirement_modification_situation_table.csv", 2, "requirement_modification_count"),
        ("csq2_acceptance_rework_situation_table.csv", 8, "acceptance_rework_count"),
        ("csq2_contract_review_situation_table.csv", 7, "contract_review_count")]
    for name, n, feature in specifications:
        counts = event_counts(name, n, feature)
        data = data.join(counts, on="requirement_id", validate="one_to_one")
        data[feature] = data[feature].fillna(0).astype(int)
    counts = rework.groupby("requirement_id").size().rename("voucher_rework_count")
    data = data.join(counts, on="requirement_id", validate="one_to_one")
    data["voucher_rework_count"] = data["voucher_rework_count"].fillna(0).astype(int)
    groups = [data.loc[data["group"].eq(g)] for g in ["upper-tail", "remaining"]]
    sizes = [len(g) for g in groups]
    check(all(sizes), "Empty CSQ2 comparison group")
    rows = [["Median submission-to-posting time (calendar days)"] + [f"{g['E2E_days'].median():.2f}" for g in groups]]
    specifications = [("Requirement with at least one Requirement modification", "requirement_modification_count"),
                      ("Requirement with at least one acceptance rework", "acceptance_rework_count"),
                      ("Total acceptance-rework occurrences", "acceptance_rework_count"),
                      ("Requirement passing through Contract Review", "contract_review_count"),
                      ("Requirement with at least one voucher rework", "voucher_rework_count")]
    for name, feature in specifications:
        values = []
        for group in groups:
            n = int(group[feature].sum()) if name.startswith("Total") else int(group[feature].gt(0).sum())
            values.append(str(n) if name.startswith("Total") else f"{n} ({100*n/len(group):.1f}%)")
        rows.append([name] + values)
    headers = ["Characteristic", f"Upper-tail (n={sizes[0]})", f"Remaining (n={sizes[1]})"]
    pd.DataFrame(rows, columns=headers).to_csv(TABLES / "csq2_upper_tail_comparison.csv", index=False)
    save_tex("csq2_upper_tail_comparison", "Observed rework and routing characteristics of upper-tail and remaining posted Requirements",
             headers, rows, "@{}Xrr@{}")
    depth = data.groupby("acceptance_rework_count", sort=True).agg(
        n=("requirement_id", "size"), mean_S3_days=("S3_days", "mean"), mean_E2E_days=("E2E_days", "mean")).reset_index()
    depth.round(2).to_csv(TABLES / "csq2_acceptance_rework_depth.csv", index=False)
    save_tex("csq2_acceptance_rework_depth", "Acceptance-rework depth and realised elapsed time among posted Requirements",
             ["Acceptance rework cycles", "N", "Mean S3 days", "Mean E2E days"],
             [[int(r.acceptance_rework_count), int(r.n), f"{r.mean_S3_days:.2f}", f"{r.mean_E2E_days:.2f}"] for r in depth.itertuples()],
             "@{}Xrrr@{}")

    ranked = data.sort_values(["E2E_days", "requirement_id"], kind="stable").reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    upper = ranked["group"].eq("upper-tail")
    median = ranked["E2E_days"].median()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for mask, label, color in [(~upper, "Remaining posted Requirements", "tab:blue"), (upper, "Upper-tail Requirements", "tab:orange")]:
        ax.scatter(ranked.loc[mask, "rank"], ranked.loc[mask, "E2E_days"], label=label, color=color, s=38, zorder=3)
    ax.axhline(p75, color="dodgerblue", linestyle="--", linewidth=1.2, label=f"P75 = {p75:.2f} d")
    ax.axhline(median, color="dodgerblue", linestyle=":", linewidth=1.2, label=f"Median = {median:.2f} d")
    for row in ranked.loc[upper].itertuples():
        ax.annotate(row.requirement_id, (row.rank, row.E2E_days), xytext=(4, 5), textcoords="offset points", fontsize=8)
    ax.text(.012, .975, f"N = {len(ranked)}\nMean = {ranked['E2E_days'].mean():.2f} d\nMedian = {median:.2f} d\nP75 = {p75:.2f} d\nUpper-tail N = {int(upper.sum())}", transform=ax.transAxes, va="top")
    ax.set(title="Distribution of submission-to-posting elapsed time",
           xlabel="Posted Requirements ranked by submission-to-posting duration",
           ylabel="Submission-to-posting elapsed time (calendar days)",
           xlim=(-.2, len(ranked)+1.2), ylim=(ranked["E2E_days"].min()-1, ranked["E2E_days"].max()+1.5))
    ax.set_xticks(np.arange(0, len(ranked)+1, 5))
    ax.grid(alpha=.28, zorder=0)
    ax.legend(loc="center left", fontsize=9)
    save_plot(fig, "csq2_e2e_duration_distribution")
    stats = {"p75_days": p75, "upper_tail_n": sizes[0], "remaining_n": sizes[1],
             "upper_tail_requirement_ids": sorted(data.loc[data["group"].eq("upper-tail"), "requirement_id"], key=lambda s:int(s.split("-")[-1])),
             "rework_depth": depth.to_dict(orient="records")}
    return data, stats


def csq3(cases: pd.DataFrame, mapping: pd.DataFrame, rework: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    columns = ["o1", "o2", "e1", "e2", "e3", "e4", "synchronization_delay", "readiness_to_verify",
               "readiness_to_post", "invoice_wait", "asset_wait", "invoice_last", "asset_last", "tie", "Satisfied"]
    raw = read_export("csq3_invoice_asset_situation_table.csv", columns, 25)
    unique(raw, ["o1", "o2"], "CSQ3 Invoice-Asset pairs")
    unique(raw, ["e4"], "CSQ3 post events")
    data = raw[["o1", "o2", "e1", "e2", "e3", "e4"]].rename(columns={
        "o1": "invoice_id", "o2": "asset_id", "e1": "receive_invoice_event_id", "e2": "put_asset_into_use_event_id",
        "e3": "verify_event_id", "e4": "post_event_id"}).copy()
    for label, output, factor in [("synchronization_delay", "sync_delay_days", DAY),
                                  ("readiness_to_verify", "ready_to_verify_min", 60),
                                  ("readiness_to_post", "ready_to_post_min", 60),
                                  ("invoice_wait", "invoice_wait_days", DAY), ("asset_wait", "asset_wait_days", DAY)]:
        data[output] = raw[label].map(seconds) / factor
    flags = raw[["invoice_last", "asset_last", "tie"]].map(boolean)
    check(flags.astype(int).sum(axis=1).eq(1).all(), "CSQ3 prerequisite-order labels must be mutually exclusive")
    data["prerequisite_ordering"] = np.select([flags["asset_last"], flags["invoice_last"], flags["tie"]], ["Asset later", "Invoice later", "Tie"], default="Invalid")
    cross = data.merge(mapping, on="post_event_id", how="outer", validate="one_to_one", indicator=True)
    check(cross["_merge"].eq("both").all(), "CSQ3 posting cohort does not match the Requirement-Voucher mapping")
    data = cross.drop(columns="_merge")
    cross = data.merge(cases[["requirement_id", "e4", "e5"]], on="requirement_id", validate="one_to_one")
    check(cross["verify_event_id"].eq(cross["e4"]).all() and cross["post_event_id"].eq(cross["e5"]).all(),
          "CSQ3 verify/post event IDs differ from the CSQ1 milestones")
    data["voucher_rework"] = data["post_event_id"].isin(rework["post_event_id"])
    sync, verify, post = data["sync_delay_days"], data["ready_to_verify_min"], data["ready_to_post_min"]
    normal, repeated = data.loc[~data["voucher_rework"], "ready_to_post_min"], data.loc[data["voucher_rework"], "ready_to_post_min"]
    check(len(normal)>0 and len(repeated)>0 and normal.nunique()==1 and repeated.nunique()==1,
          "Archived normal/rework post-readiness groups no longer have a single duration")
    n = len(data)
    counts = data["prerequisite_ordering"].value_counts()
    rows = [
        ["Prerequisite ordering", f"Asset later {counts.get('Asset later', 0)}/{n}; invoice later {counts.get('Invoice later', 0)}/{n}; ties {counts.get('Tie', 0)}/{n}"],
        ["Synchronisation delay", f"Mean {sync.mean():.2f} calendar days; median {sync.median():.2f}; Q1 {sync.quantile(.25):.2f}; Q3 {sync.quantile(.75):.2f}; range {sync.min():.2f}--{sync.max():.2f}"],
        ["Readiness to Verify Accounting Prerequisites", f"{verify.iloc[0]:g} minutes in {n}/{n} bindings" if verify.nunique()==1 else f"Mean {verify.mean():.2f} minutes; range {verify.min():g}--{verify.max():g}"],
        ["Readiness to Post Accounting Voucher", f"Mean {post.mean():g} minutes; median {post.median():g}; range {post.min():g}--{post.max():g} minutes"],
        ["Normal post-readiness path", f"{len(normal)}/{n} Requirements posted after {normal.iloc[0]:g} minutes"],
        ["Voucher-rework path", f"{len(repeated)}/{n} Requirements posted after {repeated.iloc[0]:g} minutes"]]
    pd.DataFrame(rows, columns=["Measure", "Baseline result"]).to_csv(TABLES / "csq3_timing_summary.csv", index=False)
    save_tex("csq3_timing_summary", "Accounting-synchronisation and post-readiness results for the 25 analysed Invoice--Asset pairs",
             ["Measure", "Baseline result"], rows, r"@{}>{\raggedright\arraybackslash}p{.38\linewidth}X@{}")

    ranked = data.sort_values(["sync_delay_days", "invoice_id", "asset_id"], kind="stable").reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked)+1)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(ranked["rank"], ranked["sync_delay_days"], s=45, color="tab:blue", zorder=3)
    ax.axhline(sync.mean(), color="tab:blue", linestyle="--", linewidth=1.2, label=f"Mean = {sync.mean():.2f} d")
    ax.axhline(sync.median(), color="tab:blue", linestyle=":", linewidth=1.2, label=f"Median = {sync.median():.2f} d")
    for i, row in enumerate(ranked.tail(4).itertuples()):
        offset, ha, va = ((-6, -6), "right", "top") if i==0 else (((-6, 6), "right", "bottom") if i==3 else ((5, 6), "left", "bottom"))
        ax.annotate(f"{row.invoice_id}\n{row.sync_delay_days:.2f} d", (row.rank, row.sync_delay_days),
                    xytext=offset, textcoords="offset points", fontsize=8, ha=ha, va=va)
    ax.text(.01, .97, f"N = {n}\nMean = {sync.mean():.2f} d\nMedian = {sync.median():.2f} d\nQ1-Q3 = {sync.quantile(.25):.2f}-{sync.quantile(.75):.2f} d\nRange = {sync.min():.2f}-{sync.max():.2f} d", transform=ax.transAxes, va="top")
    ax.set(title="Distribution of Invoice-Asset synchronisation delay",
           xlabel="Invoice-Asset pairs ranked by synchronisation delay", ylabel="Synchronisation delay (calendar days)",
           xlim=(-.2, n+1.2), ylim=(sync.min()-1, sync.max()+2.1))
    ax.set_xticks(np.arange(0, n+1, 5))
    ax.grid(alpha=.3, zorder=0)
    ax.legend(loc="center right")
    save_plot(fig, "csq3_sync_delay_distribution")
    return data, {"sync_delay_days": describe(sync), "ready_to_verify_minutes": describe(verify),
                  "ready_to_post_minutes": describe(post), "ordering_counts": {str(k):int(v) for k,v in counts.items()},
                  "normal_n": len(normal), "voucher_rework_n": len(repeated),
                  "normal_post_minutes": float(normal.iloc[0]), "rework_post_minutes": float(repeated.iloc[0])}


def main() -> None:
    global LATEX
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latex", action="store_true", help="Also generate LaTeX tables.")
    LATEX = parser.parse_args().latex
    for directory in [TABLES, FIGURES]:
        directory.mkdir(parents=True, exist_ok=True)
    c1, _ = csq1()
    mapping, rework = voucher_mapping(c1)
    c2, _ = csq2(c1, rework)
    c3, _ = csq3(c1, mapping, rework)
    check(len(c1)==len(c2)==len(c3)==25, "Cohort size mismatch")
    print("CSQ1-CSQ3 complete: 4 PDF figures and 4 CSV tables; export consistency checks passed.")
    print(f"Outputs: {RESULTS}")


if __name__ == "__main__":
    main()
