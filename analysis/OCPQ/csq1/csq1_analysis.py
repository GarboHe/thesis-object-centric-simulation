#!/usr/bin/env python3
"""Reproduce CSQ1 stage-decomposition results from raw OCPQ exports.

Primary input
-------------
Raw OCPQ Situation Table exported from `csq1_milestone_query.json`.

Expected core columns:
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
    [Satisfied]  # optional but expected in the current export

OCPQ duration labels:
    S1  = requirement_stage
    S2  = sourcing_order_stage
    S3  = fulfilment_prereq_stage
    S4  = accounting_posting_stage
    E2E = e2e_duration

The current OCPQ export uses ISO-8601-like duration strings such as:
    PT1620S
    PT2862300S

All durations are converted to calendar elapsed days:
    calendar_days = elapsed_seconds / 86400

Optional path input
-------------------
`csq1_path_connections.csv` with:
    source_id
    target_id
    source_time
    target_time

When supplied, the script joins:
    e1 == source_id
    e5 == target_id

and verifies:
    target_time - source_time == e2e_duration

Outputs
-------
intermediate/csq1_case_level.csv
intermediate/csq1_path_milestone_crosscheck.csv   (if path CSV supplied)
results/tables/table_4_9.csv
results/tables/csq1_summary_numeric.csv
results/figures/csq1_stage_duration_distribution.pdf
results/figures/csq1_stage_duration_distribution.png
results/csq1_run_summary.txt

Current thesis numbering:
    Figure 4.2 = OCPQ path / throughput result
    Table 4.9  = CSQ1 stage-level decomposition
    Figure 4.3 = CSQ1 stage-duration boxplot
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MAIN_REQUIRED = {
    "o1",
    "e1",
    "e2",
    "e3",
    "e4",
    "e5",
    "e2e_duration",
    "requirement_stage",
    "sourcing_order_stage",
    "fulfilment_prereq_stage",
    "accounting_posting_stage",
}

PATH_REQUIRED = {
    "source_id",
    "target_id",
    "source_time",
    "target_time",
}

STAGE_ORDER = ["S1", "S2", "S3", "S4", "E2E"]

SOURCE_COLUMNS = {
    "S1": "requirement_stage",
    "S2": "sourcing_order_stage",
    "S3": "fulfilment_prereq_stage",
    "S4": "accounting_posting_stage",
    "E2E": "e2e_duration",
}

INTERVALS = {
    "S1": "Submit Requirement -> Obtain Quotations",
    "S2": "Obtain Quotations -> Create Purchase Order",
    "S3": "Create Purchase Order -> Verify Accounting Prerequisites",
    "S4": "Verify Accounting Prerequisites -> Post Accounting Voucher",
    "E2E": "Submit Requirement -> Post Accounting Voucher",
}

STAGE_NAMES = {
    "S1": "S1 Requirement and quotation acquisition",
    "S2": "S2 Quotation evaluation, contracting, and ordering",
    "S3": "S3 Fulfilment, acceptance, and accounting readiness",
    "S4": "S4 Accounting processing and posting",
    "E2E": "End-to-end",
}

# Current thesis-facing checkpoints, used only to verify the reproduced
# baseline results. They do not generate or replace calculated values.
EXPECTED_2DP = {
    "S1": {
        "mean": 10.23, "median": 11.02, "q1": 9.02, "q3": 11.02,
        "min": 9.02, "max": 11.08, "share": 51.22
    },
    "S2": {
        "mean": 0.45, "median": 0.17, "q1": 0.17, "q3": 0.98,
        "min": 0.17, "max": 1.98, "share": 2.24
    },
    "S3": {
        "mean": 9.27, "median": 7.09, "q1": 7.09, "q3": 7.82,
        "min": 7.09, "max": 29.00, "share": 46.43
    },
    "S4": {
        "mean": 0.02, "median": 0.02, "q1": 0.02, "q3": 0.02,
        "min": 0.02, "max": 0.05, "share": 0.11
    },
    "E2E": {
        "mean": 19.97, "median": 18.30, "q1": 17.05, "q3": 19.30,
        "min": 16.30, "max": 38.31, "share": 100.00
    },
}

ISO_DURATION_RE = re.compile(
    r"^(?P<sign>[+-])?"
    r"P"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$",
    flags=re.IGNORECASE,
)


def parse_bool(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        raise ValueError("Missing boolean value.")
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def filter_satisfied(df: pd.DataFrame) -> pd.DataFrame:
    if "Satisfied" not in df.columns:
        return df.copy()
    mask = df["Satisfied"].map(parse_bool)
    return df.loc[mask].copy()


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"{label} is missing required columns: {', '.join(missing)}\n"
            f"Columns found: {', '.join(map(str, df.columns))}"
        )


def duration_to_seconds(value) -> float:
    """Parse OCPQ duration values into seconds.

    The primary supported representation is ISO-8601-like text such as
    PT1620S or P1DT2H3M4S. Numeric values are interpreted as seconds.
    """
    if pd.isna(value):
        raise ValueError("Missing duration value.")

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = str(value).strip()

    # Some CSV readers may coerce a pure numeric string.
    try:
        return float(text)
    except ValueError:
        pass

    match = ISO_DURATION_RE.fullmatch(text)
    if not match:
        # Fallback for duration strings that pandas can understand.
        try:
            td = pd.to_timedelta(text)
            return float(td.total_seconds())
        except Exception as exc:
            raise ValueError(
                f"Cannot parse OCPQ duration value {value!r}. "
                "Expected a value such as PT1620S."
            ) from exc

    groups = match.groupdict()
    sign = -1.0 if groups["sign"] == "-" else 1.0
    days = float(groups["days"] or 0)
    hours = float(groups["hours"] or 0)
    minutes = float(groups["minutes"] or 0)
    seconds = float(groups["seconds"] or 0)

    return sign * (
        days * 86400.0
        + hours * 3600.0
        + minutes * 60.0
        + seconds
    )


def parse_timestamp_series(series: pd.Series, column_name: str) -> pd.Series:
    try:
        result = pd.to_datetime(series, utc=True, errors="raise")
    except Exception as exc:
        raise ValueError(
            f"Could not parse timestamp column {column_name!r}."
        ) from exc
    if result.isna().any():
        raise ValueError(f"Missing timestamp value in {column_name!r}.")
    return result


def describe(series: pd.Series) -> dict[str, float]:
    return {
        "N": int(series.size),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "q1": float(series.quantile(0.25, interpolation="linear")),
        "q3": float(series.quantile(0.75, interpolation="linear")),
        "min": float(series.min()),
        "max": float(series.max()),
    }


def assert_reported_value(actual: float, expected: float, label: str) -> None:
    """Compare at the two-decimal precision reported in the thesis."""
    actual_2dp = round(float(actual) + 1e-12, 2)
    if not np.isclose(actual_2dp, expected, atol=1e-9, rtol=0):
        raise AssertionError(
            f"Thesis checkpoint failed for {label}: "
            f"actual={actual:.10f} (reported {actual_2dp:.2f}), "
            f"expected={expected:.2f}."
        )


def run_thesis_checkpoints(
    stats: dict[str, dict[str, float]],
    shares: dict[str, float],
) -> None:
    for stage in STAGE_ORDER:
        expected = EXPECTED_2DP[stage]
        actual = stats[stage]

        for key in ["mean", "median", "q1", "q3", "min", "max"]:
            assert_reported_value(
                actual[key],
                expected[key],
                f"{stage} {key}",
            )

        assert_reported_value(
            shares[stage],
            expected["share"],
            f"{stage} share",
        )

    assert_reported_value(
        shares["S1"] + shares["S3"],
        97.65,
        "S1 + S3 combined share",
    )


def build_path_crosscheck(
    case_df: pd.DataFrame,
    path_csv: str | Path,
    output_path: Path,
) -> dict[str, float]:
    path = pd.read_csv(path_csv)
    require_columns(path, PATH_REQUIRED, "Path connections CSV")

    if len(path) != 25:
        raise AssertionError(
            f"Expected 25 OCPQ path connections, found {len(path)}."
        )

    path["source_id"] = path["source_id"].astype(str)
    path["target_id"] = path["target_id"].astype(str)
    path["source_time"] = parse_timestamp_series(
        path["source_time"], "source_time"
    )
    path["target_time"] = parse_timestamp_series(
        path["target_time"], "target_time"
    )

    if (path["source_time"] > path["target_time"]).any():
        raise AssertionError(
            "At least one path connection has source_time > target_time."
        )

    path["path_e2e_days"] = (
        (path["target_time"] - path["source_time"]).dt.total_seconds()
        / 86400.0
    )

    left = case_df.copy()
    left["e1"] = left["e1"].astype(str)
    left["e5"] = left["e5"].astype(str)

    merged = left.merge(
        path,
        how="left",
        left_on=["e1", "e5"],
        right_on=["source_id", "target_id"],
        validate="one_to_one",
        indicator=True,
    )

    if not (merged["_merge"] == "both").all():
        missing = merged.loc[
            merged["_merge"] != "both",
            ["requirement_id", "e1", "e5"],
        ]
        raise AssertionError(
            "Not every milestone row matched an OCPQ path connection by e1/e5 event IDs.\n"
            + missing.to_string(index=False)
        )

    difference = merged["path_e2e_days"] - merged["E2E_days"]
    if not np.allclose(difference, 0.0, atol=1e-10, rtol=0):
        bad = merged.loc[
            ~np.isclose(difference, 0.0, atol=1e-10, rtol=0),
            ["requirement_id", "e1", "e5", "path_e2e_days", "E2E_days"],
        ].copy()
        bad["difference_days"] = (
            bad["path_e2e_days"] - bad["E2E_days"]
        )
        raise AssertionError(
            "Path throughput and milestone e2e_duration differ for at least one row:\n"
            + bad.to_string(index=False)
        )

    cross = merged[
        [
            "requirement_id",
            "e1",
            "e5",
            "source_id",
            "target_id",
            "source_time",
            "target_time",
            "path_e2e_days",
            "E2E_days",
        ]
    ].copy()
    cross["difference_days"] = (
        cross["path_e2e_days"] - cross["E2E_days"]
    )
    cross.to_csv(output_path, index=False)

    return describe(path["path_e2e_days"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce CSQ1 stage-decomposition results from raw OCPQ exports."
        )
    )
    parser.add_argument(
        "milestone_csv",
        help=(
            "Raw 25-row CSQ1 milestone Situation Table exported from OCPQ."
        ),
    )
    parser.add_argument(
        "--path-connections-csv",
        default=None,
        help=(
            "Optional OCPQ Path Schema connection export. When supplied, "
            "the script cross-checks e1/e5 event IDs and E2E duration."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Output root directory (default: current directory).",
    )
    parser.add_argument(
        "--skip-checkpoints",
        action="store_true",
        help=(
            "Generate outputs without requiring equality to the current thesis baseline. "
            "Do not use this flag for the formal baseline reproduction."
        ),
    )
    args = parser.parse_args()

    root = Path(args.out_dir)
    intermediate_dir = root / "intermediate"
    tables_dir = root / "results" / "tables"
    figures_dir = root / "results" / "figures"
    results_dir = root / "results"

    for directory in [
        intermediate_dir,
        tables_dir,
        figures_dir,
        results_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.milestone_csv)
    raw = filter_satisfied(raw)
    require_columns(raw, MAIN_REQUIRED, "Milestone Situation Table")

    if len(raw) != 25:
        raise AssertionError(
            f"Expected 25 satisfied posted-Requirement bindings, found {len(raw)}."
        )

    if raw["o1"].astype(str).nunique() != 25:
        raise AssertionError(
            "Expected 25 unique Requirement IDs in column o1."
        )

    df = pd.DataFrame(
        {
            "requirement_id": raw["o1"].astype(str),
            "e1": raw["e1"].astype(str),
            "e2": raw["e2"].astype(str),
            "e3": raw["e3"].astype(str),
            "e4": raw["e4"].astype(str),
            "e5": raw["e5"].astype(str),
        }
    )

    # Preserve the Requirement attribute in the normalized intermediate
    # dataset when it is present in the raw OCPQ export.
    if "o1.demand_source" in raw.columns:
        df["demand_source"] = raw["o1.demand_source"].astype(str)

    for stage, source_column in SOURCE_COLUMNS.items():
        seconds = raw[source_column].map(duration_to_seconds).astype(float)

        if (seconds < -1e-9).any():
            bad = raw.loc[
                seconds < -1e-9,
                ["o1", source_column],
            ]
            raise AssertionError(
                f"Negative duration detected in {source_column}:\n"
                + bad.to_string(index=False)
            )

        df[f"{stage}_seconds"] = seconds
        df[f"{stage}_days"] = seconds / 86400.0

    stage_sum_seconds = df[
        ["S1_seconds", "S2_seconds", "S3_seconds", "S4_seconds"]
    ].sum(axis=1)

    if not np.allclose(
        stage_sum_seconds,
        df["E2E_seconds"],
        atol=1e-6,
        rtol=0,
    ):
        bad_mask = ~np.isclose(
            stage_sum_seconds,
            df["E2E_seconds"],
            atol=1e-6,
            rtol=0,
        )
        bad = df.loc[
            bad_mask,
            [
                "requirement_id",
                "S1_seconds",
                "S2_seconds",
                "S3_seconds",
                "S4_seconds",
                "E2E_seconds",
            ],
        ].copy()
        bad["stage_sum_seconds"] = bad[
            ["S1_seconds", "S2_seconds", "S3_seconds", "S4_seconds"]
        ].sum(axis=1)

        raise AssertionError(
            "S1 + S2 + S3 + S4 does not equal E2E for at least one Requirement:\n"
            + bad.to_string(index=False)
        )

    # Keep the user-facing intermediate file concise.
    output_columns = [
        "requirement_id",
    ]
    if "demand_source" in df.columns:
        output_columns.append("demand_source")
    output_columns += [
        "e1",
        "e2",
        "e3",
        "e4",
        "e5",
        "S1_days",
        "S2_days",
        "S3_days",
        "S4_days",
        "E2E_days",
    ]

    df[output_columns].to_csv(
        intermediate_dir / "csq1_case_level.csv",
        index=False,
    )

    series = {
        "S1": df["S1_days"],
        "S2": df["S2_days"],
        "S3": df["S3_days"],
        "S4": df["S4_days"],
        "E2E": df["E2E_days"],
    }

    stats = {
        stage: describe(values)
        for stage, values in series.items()
    }

    total_e2e_days = float(df["E2E_days"].sum())

    shares = {
        "S1": float(df["S1_days"].sum() / total_e2e_days * 100.0),
        "S2": float(df["S2_days"].sum() / total_e2e_days * 100.0),
        "S3": float(df["S3_days"].sum() / total_e2e_days * 100.0),
        "S4": float(df["S4_days"].sum() / total_e2e_days * 100.0),
        "E2E": 100.0,
    }

    # Full-precision machine-readable output.
    numeric_rows = []
    for stage in STAGE_ORDER:
        d = stats[stage]
        numeric_rows.append(
            {
                "stage": stage,
                "N": d["N"],
                "mean_days": d["mean"],
                "median_days": d["median"],
                "q1_days": d["q1"],
                "q3_days": d["q3"],
                "min_days": d["min"],
                "max_days": d["max"],
                "share_percent": shares[stage],
            }
        )

    pd.DataFrame(numeric_rows).to_csv(
        tables_dir / "csq1_summary_numeric.csv",
        index=False,
    )

    # Thesis-facing Table 4.9.
    table_rows = []
    for stage in STAGE_ORDER:
        d = stats[stage]
        table_rows.append(
            {
                "Stage": STAGE_NAMES[stage],
                "Interval": INTERVALS[stage],
                "N": d["N"],
                "Mean (calendar days)": f"{d['mean']:.2f}",
                "Median (calendar days)": f"{d['median']:.2f}",
                "Q1-Q3 (calendar days)": f"{d['q1']:.2f}-{d['q3']:.2f}",
                "Range (calendar days)": f"{d['min']:.2f}-{d['max']:.2f}",
                "Share (%)": f"{shares[stage]:.2f}",
            }
        )

    pd.DataFrame(table_rows).to_csv(
        tables_dir / "table_4_9.csv",
        index=False,
    )

    # Figure 4.3: 25 observations per stage, standard 1.5 IQR whiskers,
    # outliers retained and shown individually.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(
        [
            df["S1_days"].to_numpy(),
            df["S2_days"].to_numpy(),
            df["S3_days"].to_numpy(),
            df["S4_days"].to_numpy(),
        ],
        tick_labels=["S1", "S2", "S3", "S4"],
        whis=1.5,
        showfliers=True,
    )
    ax.set_xlabel("Process stage")
    ax.set_ylabel("Elapsed time (calendar days)")
    ax.set_title("Distribution of stage durations for posted Requirements")
    fig.tight_layout()
    fig.savefig(
        figures_dir / "csq1_stage_duration_distribution.pdf",
        bbox_inches="tight",
    )
    fig.savefig(
        figures_dir / "csq1_stage_duration_distribution.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)

    path_stats = None
    if args.path_connections_csv:
        path_stats = build_path_crosscheck(
            df,
            args.path_connections_csv,
            intermediate_dir / "csq1_path_milestone_crosscheck.csv",
        )

    checkpoint_status = "SKIPPED"
    if not args.skip_checkpoints:
        run_thesis_checkpoints(stats, shares)
        checkpoint_status = "PASS"

    lines = [
        "CSQ1 reproduction summary",
        "=========================",
        "",
        f"Satisfied posted-Requirement bindings: {len(df)}",
        "",
        "Stage statistics (calendar days)",
        "--------------------------------",
    ]

    for stage in STAGE_ORDER:
        d = stats[stage]
        lines.append(
            f"{stage}: N={d['N']}; "
            f"mean={d['mean']:.6f}; "
            f"median={d['median']:.6f}; "
            f"Q1={d['q1']:.6f}; "
            f"Q3={d['q3']:.6f}; "
            f"range={d['min']:.6f}-{d['max']:.6f}; "
            f"share={shares[stage]:.6f}%"
        )

    lines.extend(
        [
            "",
            f"S1 + S3 aggregate share: "
            f"{shares['S1'] + shares['S3']:.6f}%",
        ]
    )

    if path_stats is not None:
        lines.extend(
            [
                "",
                "OCPQ Path Schema cross-check",
                "----------------------------",
                "Matched all 25 milestone rows to path connections by e1/e5 event IDs: YES",
                "Path throughput equals milestone e2e_duration row by row: YES",
                (
                    f"Path throughput: mean={path_stats['mean']:.6f}; "
                    f"median={path_stats['median']:.6f}; "
                    f"range={path_stats['min']:.6f}-"
                    f"{path_stats['max']:.6f} calendar days"
                ),
            ]
        )

    lines.extend(
        [
            "",
            f"Thesis checkpoint status: {checkpoint_status}",
        ]
    )

    summary_text = "\n".join(lines) + "\n"
    (results_dir / "csq1_run_summary.txt").write_text(
        summary_text,
        encoding="utf-8",
    )
    print(summary_text, end="")


if __name__ == "__main__":
    main()
