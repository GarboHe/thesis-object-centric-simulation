"""Assemble Figure 4.3 using archived OCPQ artwork and exported duration labels."""
from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pypdf import PdfReader, PdfWriter, Transformation
WIDTH = 160 / 25.4

BLUE = '#35658A'

ORANGE = '#B96B32'

TEAL = '#488779'

PURPLE = '#7B6F97'

GREY = '#757575'

INK = '#252525'

STAGE_COLOURS = (BLUE, ORANGE, TEAL, PURPLE)

def apply_style() -> None:
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 9.5,
        'axes.labelsize': 9.5, 'axes.titlesize': 10,
        'axes.titleweight': 'semibold', 'xtick.labelsize': 9,
        'ytick.labelsize': 9, 'legend.fontsize': 9,
        'text.color': INK, 'axes.labelcolor': INK,
        'axes.edgecolor': '#888888', 'axes.linewidth': .65,
        'xtick.color': INK, 'ytick.color': INK,
        'xtick.major.width': .65, 'ytick.major.width': .65,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'savefig.facecolor': 'white', 'pdf.fonttype': 42,
        'ps.fonttype': 42, 'svg.fonttype': 'none',
        'svg.hashsalt': 'ocps-thesis',
        'axes.spines.top': False, 'axes.spines.right': False,
        'grid.color': '#E3E7EA', 'grid.linewidth': .6,
    })

def grid(ax, axis='y') -> None:
    ax.set_axisbelow(True)
    ax.grid(axis=axis)

apply_style()


def merge_artwork(base: bytes, artwork: Path | bytes, x: float, y: float,
                  width: float, height: float) -> bytes:
    page = PdfReader(io.BytesIO(base)).pages[0]
    source = PdfReader(io.BytesIO(artwork) if isinstance(artwork, bytes)
                       else str(artwork)).pages[0]
    sw, sh = float(source.mediabox.width), float(source.mediabox.height)
    scale = min(width / sw, height / sh)
    source_transform = Transformation().scale(scale).translate(
        x + (width - sw * scale) / 2, y + (height - sh * scale) / 2)
    page.merge_transformed_page(source, source_transform)
    writer = PdfWriter()
    writer.add_page(page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_path_figure(days: pd.Series, root: Path, figures: Path) -> dict:
    """Durations come from the event-ID matched milestone export."""
    bins = np.linspace(days.min(), days.max(), 7)
    counts, _ = np.histogram(days, bins=bins)
    if counts.tolist() != [19, 2, 2, 0, 1, 1]:
        raise ValueError("The baseline histogram frequencies have changed.")
    metrics = json.loads((root / "assets/csq1_path_metrics.json").read_text())
    if metrics["support"] != len(days):
        raise ValueError("Path support does not match exported connections.")

    fig = plt.figure(figsize=(WIDTH, 8.2))
    fig.text(.03, .978, "(a) OCPQ path through the same Requirement object", fontsize=10, weight="semibold")
    fig.text(.03, .51, "Query results", fontsize=9.5, weight="semibold")
    headings = ["Support", "Coverage", "Selectivity", "Reach", "Exclusivity"]
    for x, heading in zip(np.linspace(.03, .81, 5), headings):
        fig.text(x, .48, heading, fontsize=9)
        value = metrics[heading.lower()]
        fig.text(x, .45, str(value) if heading == "Support" else f"{value:.3f}", fontsize=9.5, weight="semibold")
    fig.text(.03, .40, "(b) Throughput-time distribution for 25 completed lifecycles", fontsize=10, weight="semibold")
    fig.text(.03, .37, f"Min: {days.min():.2f}   Median: {days.median():.2f}   Mean: {days.mean():.2f}   Max: {days.max():.2f} days", fontsize=9)
    ax = fig.add_axes([.13, .105, .84, .23])
    ax.hist(days, bins=bins, weights=np.full(len(days), 100 / len(days)),
            color=BLUE, edgecolor="white", rwidth=.96)
    ax.axvline(days.mean(), color=ORANGE, linestyle="--", linewidth=1.1,
               label=f"Mean: {days.mean():.2f} days")
    ax.set_xlim(days.min()-1, days.max()+1)
    ax.set_ylim(0, 84)
    ax.set_xticks([16, 20, 24, 28, 32, 36, 38])
    ax.set_yticks([0, 20, 40, 60, 80], ["0%", "20%", "40%", "60%", "80%"])
    ax.set_xlabel("Submission-to-posting duration (calendar days)")
    ax.set_ylabel("Share of completed lifecycles")
    grid(ax)
    ax.legend(frameon=False, loc="upper right")
    buffer = io.BytesIO()
    fig.savefig(buffer, format="pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    pw, ph = WIDTH * 72, 8.2 * 72
    pdf = merge_artwork(buffer.getvalue(), root / "assets/csq1_path_type_graph.pdf",
                        .03*pw, .55*ph, .94*pw, .40*ph)
    (figures / "csq1_path_throughput.pdf").write_bytes(pdf)
    summary = {
        "n_connections": len(days), "mean_days": float(days.mean()),
        "median_days": float(days.median()), "min_days": float(days.min()),
        "max_days": float(days.max()), "bin_edges_days": bins.tolist(),
        "bin_counts": counts.tolist(), "bin_shares_percent": (counts / len(days) * 100).tolist(),
        "seconds_per_calendar_day": 86400,
    }
    return summary
