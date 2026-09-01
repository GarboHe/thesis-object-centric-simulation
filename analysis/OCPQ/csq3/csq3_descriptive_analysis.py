#!/usr/bin/env python3
"""Reproduce the descriptive CSQ3 results from raw OCPQ Situation Tables.

This script is designed for the CSQ3 reproduction package of the thesis.
It consumes the raw OCPQ exports directly; no manually normalised CSV is
required.

Primary input: Invoice-Asset CSQ3 Situation Table exported from OCPQ.
Expected columns (extra columns are allowed):
    o1, o2, e1, e2, e3, e4,
    synchronization_delay,
    readiness_to_verify,
    readiness_to_post,
    invoice_last, asset_last, tie
    [Satisfied]  # optional

The variables correspond to the preserved OCPQ query:
    o1 = Invoice
    o2 = Asset
    e1 = Receive Invoice
    e2 = Put Asset Into Use
    e3 = Verify Accounting Prerequisites
    e4 = Post Accounting Voucher

Secondary input: voucher-rework Situation Table exported from OCPQ.
Expected columns:
    o1 = Voucher
    e1 = Modify Accounting Voucher
    e2 = Post Accounting Voucher
    [Satisfied]  # optional

The main OCPQ query already computes the timing labels from event timestamps:
    synchronization_delay = max(e1.time(), e2.time()) - min(e1.time(), e2.time())
    readiness_to_verify   = e3.time() - max(e1.time(), e2.time())
    readiness_to_post     = e4.time() - max(e1.time(), e2.time())

Outputs:
    intermediate/csq3_case_level.csv
    intermediate/csq3_voucher_rework_crosscheck.csv
    results/tables/table_4_12.csv
    results/tables/csq3_summary_numeric.csv
    results/figures/csq3_post_readiness_distribution.pdf
    results/figures/csq3_post_readiness_distribution.png
    results/csq3_run_summary.txt

The current thesis numbering is:
    Figure 4.4 = OCPQ CSQ3 query view
    Table 4.12 = accounting-synchronisation/post-readiness summary
    Figure 4.5 = post-readiness distribution
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MAIN_REQUIRED = {
    "o1",
    "o2",
    "e1",
    "e2",
    "e3",
    "e4",
    "synchronization_delay",
    "readiness_to_verify",
    "readiness_to_post",
    "invoice_last",
    "asset_last",
    "tie",
}

REWORK_REQUIRED = {"o1", "e1", "e2"}

EXPECTED_REWORK_VOUCHERS = {"V-O-14", "V-O-21", "V-O-22"}

# Exact/raw values below are used only as reproduction checkpoints.  They are
# compared with small tolerances; thesis-facing values are rounded to 2 decimals.
EXPECTED = {
    "n": 25,
    "asset_later_n": 25,
    "invoice_later_n": 0,
    "tie_n": 0,
    "sync_mean_days": 9.1360556,
    "sync_median_days": 7.0020833,
    "sync_q1_days": 7.0020833,
    "sync_q3_days": 7.73125,
    "sync_min_days": 7.00208,
    "sync_max_days": 28.25208,
    "ready_to_verify_min": 2.0,
    "ready_to_post_29_n": 22,
    "ready_to_post_79_n": 3,
    "ready_to_post_mean_min": 35.0,
    "ready_to_post_median_min": 29.0,
}


_DURATION_RE = re.compile(
    r"^\s*(?P<sign>[+-])?"
    r"(?:(?P<d>\d+(?:\.\d+)?)d)?"
    r"(?:(?P<h>\d+(?:\.\d+)?)h)?"
    r"(?:(?P<m>\d+(?:\.\d+)?)m)?"
    r"(?:(?P<s>\d+(?:\.\d+)?)s)?\s*$",
    flags=re.IGNORECASE,
)

_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<d>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<m>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<s>\d+(?:\.\d+)?)S)?)?$",
    flags=re.IGNORECASE,
)

NUMERIC_UNIT_TO_SECONDS = {
    "seconds": 1.0,
    "milliseconds": 1e-3,
    "microseconds": 1e-6,
    "nanoseconds": 1e-9,
    "minutes": 60.0,
    "hours": 3600.0,
    "days": 86400.0,
}


def _parse_bool(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        raise ValueError("Missing boolean value in OCPQ label column.")
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def _filter_satisfied(df: pd.DataFrame) -> pd.DataFrame:
    """Keep satisfied bindings when the OCPQ export contains the column."""
    if "Satisfied" not in df.columns:
        return df.copy()
    mask = df["Satisfied"].map(_parse_bool)
    return df.loc[mask].copy()


def _compact_duration_to_seconds(text: str) -> float | None:
    """Parse OCPQ/CEL-like compact durations such as '168h3m' or '29m'."""
    match = _DURATION_RE.fullmatch(text)
    if not match:
        return None
    if not any(match.group(k) is not None for k in ("d", "h", "m", "s")):
        return None
    sign = -1.0 if match.group("sign") == "-" else 1.0
    days = float(match.group("d") or 0.0)
    hours = float(match.group("h") or 0.0)
    minutes = float(match.group("m") or 0.0)
    seconds = float(match.group("s") or 0.0)
    return sign * (days * 86400 + hours * 3600 + minutes * 60 + seconds)


def _iso_duration_to_seconds(text: str) -> float | None:
    match = _ISO_DURATION_RE.fullmatch(text)
    if not match:
        return None
    days = float(match.group("d") or 0.0)
    hours = float(match.group("h") or 0.0)
    minutes = float(match.group("m") or 0.0)
    seconds = float(match.group("s") or 0.0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def duration_value_to_seconds(value, numeric_unit: str) -> float:
    """Convert one exported OCPQ duration value to seconds.

    Supported representations include:
      * compact CEL/OCPQ strings: '168h3m', '29m', '79m'
      * pandas-style timedeltas: '7 days 00:03:00'
      * ISO-8601 durations: 'P7DT3M'
      * plain numeric values (unit controlled by --numeric-duration-unit)
    """
    if pd.isna(value):
        raise ValueError("Missing duration value in OCPQ export.")

    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        return float(value) * NUMERIC_UNIT_TO_SECONDS[numeric_unit]

    text = str(value).strip()
    if not text:
        raise ValueError("Empty duration value in OCPQ export.")

    # Plain numeric string.
    try:
        number = float(text)
        if math.isfinite(number):
            return number * NUMERIC_UNIT_TO_SECONDS[numeric_unit]
    except ValueError:
        pass

    parsed = _compact_duration_to_seconds(text)
    if parsed is not None:
        return parsed

    parsed = _iso_duration_to_seconds(text)
    if parsed is not None:
        return parsed

    # Last fallback for common forms such as '7 days 00:03:00'.
    try:
        td = pd.to_timedelta(text)
        if pd.isna(td):
            raise ValueError
        return float(td.total_seconds())
    except Exception as exc:  # noqa: BLE001 - provide a domain-specific message
        raise ValueError(
            f"Cannot parse duration value {value!r}. If the CSV stores plain numbers, "
            "set --numeric-duration-unit to the unit used by your OCPQ export."
        ) from exc


def duration_series_to_seconds(series: pd.Series, numeric_unit: str) -> pd.Series:
    return series.map(lambda x: duration_value_to_seconds(x, numeric_unit)).astype(float)


def _require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(
            f"{label} is missing required columns: {', '.join(missing)}\n"
            f"Columns found: {', '.join(map(str, df.columns))}"
        )


def _assert_close(actual: float, expected: float, atol: float, name: str) -> None:
    if not np.isclose(actual, expected, atol=atol, rtol=0):
        raise AssertionError(
            f"Checkpoint failed for {name}: actual={actual:.8f}, expected≈{expected:.8f}, "
            f"tolerance={atol}."
        )


def _run_thesis_checkpoints(df: pd.DataFrame, rework_used: bool) -> None:
    sync = df["sync_delay_days"]
    rtv = df["ready_to_verify_min"]
    rtp = df["ready_to_post_min"]

    checks = {
        "row count": (len(df), EXPECTED["n"]),
        "asset-later count": (int((df["prerequisite_ordering"] == "Asset later").sum()), EXPECTED["asset_later_n"]),
        "invoice-later count": (int((df["prerequisite_ordering"] == "Invoice later").sum()), EXPECTED["invoice_later_n"]),
        "tie count": (int((df["prerequisite_ordering"] == "Tie").sum()), EXPECTED["tie_n"]),
        "29-minute count": (int(np.isclose(rtp, 29.0, atol=1e-8).sum()), EXPECTED["ready_to_post_29_n"]),
        "79-minute count": (int(np.isclose(rtp, 79.0, atol=1e-8).sum()), EXPECTED["ready_to_post_79_n"]),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise AssertionError(f"Checkpoint failed for {name}: actual={actual}, expected={expected}.")

    _assert_close(float(sync.mean()), EXPECTED["sync_mean_days"], 1e-4, "synchronisation mean")
    _assert_close(float(sync.median()), EXPECTED["sync_median_days"], 1e-4, "synchronisation median")
    _assert_close(float(sync.quantile(0.25, interpolation="linear")), EXPECTED["sync_q1_days"], 1e-4, "synchronisation Q1")
    _assert_close(float(sync.quantile(0.75, interpolation="linear")), EXPECTED["sync_q3_days"], 1e-4, "synchronisation Q3")
    _assert_close(float(sync.min()), EXPECTED["sync_min_days"], 1e-4, "synchronisation minimum")
    _assert_close(float(sync.max()), EXPECTED["sync_max_days"], 1e-4, "synchronisation maximum")

    if not np.allclose(rtv, EXPECTED["ready_to_verify_min"], atol=1e-8, rtol=0):
        raise AssertionError("Checkpoint failed: readiness_to_verify is not 2 minutes in all 25 bindings.")
    _assert_close(float(rtp.mean()), EXPECTED["ready_to_post_mean_min"], 1e-8, "ready-to-post mean")
    _assert_close(float(rtp.median()), EXPECTED["ready_to_post_median_min"], 1e-8, "ready-to-post median")

    if rework_used:
        matched = df.loc[df["voucher_rework"]]
        if len(matched) != 3:
            raise AssertionError(f"Expected exactly 3 voucher-rework rows, found {len(matched)}.")
        if not np.allclose(matched["ready_to_post_min"], 79.0, atol=1e-8, rtol=0):
            raise AssertionError("The three voucher-rework rows do not all have ready_to_post = 79 minutes.")
        if not np.allclose(df.loc[~df["voucher_rework"], "ready_to_post_min"], 29.0, atol=1e-8, rtol=0):
            raise AssertionError("At least one non-rework row does not have ready_to_post = 29 minutes.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reproduce CSQ3 Table 4.12 and the post-readiness distribution from raw OCPQ exports."
    )
    ap.add_argument("main_csv", help="Raw 25-row Invoice-Asset OCPQ Situation Table CSV")
    ap.add_argument(
        "--voucher-rework-csv",
        default=None,
        help="Raw voucher-rework OCPQ Situation Table CSV (recommended for the exact 79-minute cross-check)",
    )
    ap.add_argument(
        "--out-dir",
        default=".",
        help="Root output directory. intermediate/ and results/ will be created below it.",
    )
    ap.add_argument(
        "--numeric-duration-unit",
        choices=sorted(NUMERIC_UNIT_TO_SECONDS),
        default="seconds",
        help=(
            "Unit to assume only when OCPQ duration cells are plain numeric values. "
            "Compact strings such as '29m' are parsed automatically. Default: seconds."
        ),
    )
    ap.add_argument(
        "--skip-checkpoints",
        action="store_true",
        help="Generate outputs without asserting the fixed baseline values reported in the thesis.",
    )
    args = ap.parse_args()

    root = Path(args.out_dir)
    intermediate = root / "intermediate"
    tables = root / "results" / "tables"
    figures = root / "results" / "figures"
    results = root / "results"
    for directory in (intermediate, tables, figures, results):
        directory.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.main_csv)
    _require_columns(raw, MAIN_REQUIRED, "Main CSQ3 Situation Table")
    raw = _filter_satisfied(raw)

    if len(raw) != 25:
        raise AssertionError(f"Expected 25 satisfied Invoice-Asset bindings, found {len(raw)}.")
    if raw[["o1", "o2"]].drop_duplicates().shape[0] != 25:
        raise AssertionError("Expected 25 unique Invoice-Asset bindings.")

    out = pd.DataFrame(
        {
            "invoice_id": raw["o1"].astype(str),
            "asset_id": raw["o2"].astype(str),
            "receive_invoice_event_id": raw["e1"].astype(str),
            "put_asset_into_use_event_id": raw["e2"].astype(str),
            "verify_event_id": raw["e3"].astype(str),
            "post_event_id": raw["e4"].astype(str),
        }
    )

    sync_seconds = duration_series_to_seconds(raw["synchronization_delay"], args.numeric_duration_unit)
    rtv_seconds = duration_series_to_seconds(raw["readiness_to_verify"], args.numeric_duration_unit)
    rtp_seconds = duration_series_to_seconds(raw["readiness_to_post"], args.numeric_duration_unit)

    out["sync_delay_days"] = sync_seconds / 86400.0
    out["ready_to_verify_min"] = rtv_seconds / 60.0
    out["ready_to_post_min"] = rtp_seconds / 60.0

    invoice_last = raw["invoice_last"].map(_parse_bool)
    asset_last = raw["asset_last"].map(_parse_bool)
    tie = raw["tie"].map(_parse_bool)

    # The three query labels are mutually exclusive by construction.
    if ((invoice_last.astype(int) + asset_last.astype(int) + tie.astype(int)) != 1).any():
        raise AssertionError("invoice_last, asset_last and tie are not mutually exclusive in every binding.")

    out["prerequisite_ordering"] = np.select(
        [asset_last, invoice_last, tie],
        ["Asset later", "Invoice later", "Tie"],
        default="Unexpected",
    )

    out["voucher_rework"] = False
    rework_used = False
    crosscheck = None

    if args.voucher_rework_csv:
        rework_raw = pd.read_csv(args.voucher_rework_csv)
        _require_columns(rework_raw, REWORK_REQUIRED, "Voucher-rework Situation Table")
        rework_raw = _filter_satisfied(rework_raw)

        if len(rework_raw) != 3:
            raise AssertionError(f"Expected 3 satisfied voucher-rework bindings, found {len(rework_raw)}.")

        rework = pd.DataFrame(
            {
                "voucher_id": rework_raw["o1"].astype(str),
                "modify_event_id": rework_raw["e1"].astype(str),
                "post_event_id": rework_raw["e2"].astype(str),
            }
        )

        if set(rework["voucher_id"]) != EXPECTED_REWORK_VOUCHERS:
            raise AssertionError(
                "Voucher-rework query did not return exactly the expected vouchers: "
                + ", ".join(sorted(EXPECTED_REWORK_VOUCHERS))
            )
        if rework["post_event_id"].duplicated().any():
            raise AssertionError("Duplicate Post Accounting Voucher event IDs in voucher-rework export.")

        out["voucher_rework"] = out["post_event_id"].isin(set(rework["post_event_id"]))
        crosscheck = out.merge(rework, on="post_event_id", how="left", validate="one_to_one")
        crosscheck["voucher_rework"] = crosscheck["voucher_id"].notna()
        crosscheck = crosscheck[
            [
                "invoice_id",
                "asset_id",
                "post_event_id",
                "voucher_id",
                "modify_event_id",
                "ready_to_post_min",
                "voucher_rework",
            ]
        ]
        crosscheck.to_csv(intermediate / "csq3_voucher_rework_crosscheck.csv", index=False)
        rework_used = True

    out.to_csv(intermediate / "csq3_case_level.csv", index=False)

    sync = out["sync_delay_days"]
    rtv = out["ready_to_verify_min"]
    rtp = out["ready_to_post_min"]

    n_asset = int((out["prerequisite_ordering"] == "Asset later").sum())
    n_invoice = int((out["prerequisite_ordering"] == "Invoice later").sum())
    n_tie = int((out["prerequisite_ordering"] == "Tie").sum())
    n29 = int(np.isclose(rtp, 29.0, atol=1e-8).sum())
    n79 = int(np.isclose(rtp, 79.0, atol=1e-8).sum())

    numeric = pd.DataFrame(
        [
            {
                "N": len(out),
                "asset_later_n": n_asset,
                "invoice_later_n": n_invoice,
                "tie_n": n_tie,
                "sync_mean_days": float(sync.mean()),
                "sync_median_days": float(sync.median()),
                "sync_q1_days": float(sync.quantile(0.25, interpolation="linear")),
                "sync_q3_days": float(sync.quantile(0.75, interpolation="linear")),
                "sync_min_days": float(sync.min()),
                "sync_max_days": float(sync.max()),
                "ready_to_verify_mean_min": float(rtv.mean()),
                "ready_to_verify_min_min": float(rtv.min()),
                "ready_to_verify_max_min": float(rtv.max()),
                "ready_to_post_mean_min": float(rtp.mean()),
                "ready_to_post_median_min": float(rtp.median()),
                "ready_to_post_min_min": float(rtp.min()),
                "ready_to_post_max_min": float(rtp.max()),
                "ready_to_post_29_n": n29,
                "ready_to_post_79_n": n79,
                "voucher_rework_n": int(out["voucher_rework"].sum()) if rework_used else np.nan,
            }
        ]
    )
    numeric.to_csv(tables / "csq3_summary_numeric.csv", index=False)

    table_412 = pd.DataFrame(
        [
            {
                "Measure": "Prerequisite ordering",
                "Baseline result": (
                    f"Asset readiness later than invoice receipt in {n_asset}/25 bindings; "
                    f"no invoice-later cases and no ties"
                    if n_invoice == 0 and n_tie == 0
                    else f"Asset-later {n_asset}/25; invoice-later {n_invoice}/25; ties {n_tie}/25"
                ),
            },
            {
                "Measure": "Synchronisation delay",
                "Baseline result": (
                    f"Mean {sync.mean():.2f} calendar days; median {sync.median():.2f}; "
                    f"Q1 {sync.quantile(0.25, interpolation='linear'):.2f}; "
                    f"Q3 {sync.quantile(0.75, interpolation='linear'):.2f}; "
                    f"range {sync.min():.2f}-{sync.max():.2f}"
                ),
            },
            {
                "Measure": "Readiness to Verify Accounting Prerequisites",
                "Baseline result": (
                    f"{rtv.iloc[0]:.0f} minutes in 25/25 bindings"
                    if np.allclose(rtv, rtv.iloc[0], atol=1e-8, rtol=0)
                    else f"Mean {rtv.mean():.2f} minutes; range {rtv.min():.2f}-{rtv.max():.2f}"
                ),
            },
            {
                "Measure": "Readiness to Post Accounting Voucher",
                "Baseline result": (
                    f"Mean {rtp.mean():.0f} minutes; median {rtp.median():.0f}; "
                    f"range {rtp.min():.0f}-{rtp.max():.0f} minutes"
                ),
            },
            {
                "Measure": "Normal post-readiness path",
                "Baseline result": f"{n29}/25 Requirements posted after 29 minutes",
            },
            {
                "Measure": "Voucher-rework path",
                "Baseline result": f"{n79}/25 Requirements posted after 79 minutes",
            },
        ]
    )
    table_412.to_csv(tables / "table_4_12.csv", index=False)

    freq = (
        pd.Series(np.round(rtp.to_numpy(dtype=float), 8), name="ready_to_post_min")
        .value_counts()
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(7, 4.5))
    xlabels = [str(int(x)) if float(x).is_integer() else str(x) for x in freq.index]
    bars = ax.bar(xlabels, freq.values)
    ax.set_xlabel("Post-readiness elapsed time (minutes)")
    ax.set_ylabel("Number of posted Requirements")
    ax.set_title("Distribution of post-readiness elapsed time")
    for bar, value in zip(bars, freq.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            str(int(value)),
            ha="center",
            va="bottom",
        )
    fig.tight_layout()
    fig.savefig(figures / "csq3_post_readiness_distribution.pdf", bbox_inches="tight")
    fig.savefig(figures / "csq3_post_readiness_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    if not args.skip_checkpoints:
        _run_thesis_checkpoints(out, rework_used=rework_used)
        checkpoint_status = "PASS"
    else:
        checkpoint_status = "SKIPPED"

    lines = [
        "CSQ3 reproduction summary",
        "=========================",
        f"Satisfied Invoice-Asset bindings: {len(out)}",
        f"Asset readiness later than invoice receipt: {n_asset}/25",
        f"Invoice later: {n_invoice}; ties: {n_tie}",
        f"Synchronisation delay mean: {sync.mean():.6f} calendar days",
        f"Synchronisation delay median: {sync.median():.6f} calendar days",
        f"Synchronisation delay Q1: {sync.quantile(0.25, interpolation='linear'):.6f}",
        f"Synchronisation delay Q3: {sync.quantile(0.75, interpolation='linear'):.6f}",
        f"Synchronisation delay range: {sync.min():.6f}-{sync.max():.6f} calendar days",
        f"Readiness-to-verify unique values (minutes): {sorted(set(np.round(rtv, 8)))}",
        f"Ready-to-post 29 min: {n29}/25",
        f"Ready-to-post 79 min: {n79}/25",
        f"Ready-to-post mean: {rtp.mean():.6f} min",
        f"Ready-to-post median: {rtp.median():.6f} min",
    ]
    if rework_used:
        matched = int(out["voucher_rework"].sum())
        lines.extend(
            [
                f"Voucher-rework rows matched by post event ID: {matched}/25",
                "Voucher-rework voucher IDs: " + ", ".join(sorted(EXPECTED_REWORK_VOUCHERS)),
                "Voucher-rework ready-to-post values (minutes): "
                + ", ".join(map(str, sorted(np.round(out.loc[out["voucher_rework"], "ready_to_post_min"], 8)))),
            ]
        )
    lines.append(f"Thesis checkpoint status: {checkpoint_status}")

    summary_path = results / "csq3_run_summary.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
