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
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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
    fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
    pdfmetrics.registerFont(TTFont("PathSans", str(fonts / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("PathSansBold", str(fonts / "DejaVuSans-Bold.ttf")))
    bins = np.linspace(days.min(), days.max(), 7)
    counts, _ = np.histogram(days, bins=bins)
    if counts.tolist() != [19, 2, 2, 0, 1, 1]:
        raise ValueError("The baseline histogram frequencies have changed.")
    metrics = json.loads((root / "assets/csq1_path_metrics.json").read_text())
    if metrics["support"] != len(days):
        raise ValueError("Path support does not match exported connections.")

    fig, ax = plt.subplots(figsize=(6.65, 3.55))
    ax.hist(days, bins=bins, weights=np.full(len(days), 100 / len(days)),
            color="#ffc795", edgecolor="#c57b47", linewidth=.85, rwidth=.95)
    ax.axvline(days.mean(), color="#d45b27", linestyle=(0, (4, 3)),
               linewidth=1.2, label=f"Mean: {days.mean():.2f} days")
    ax.set_xlim(days.min() - 1, days.max() + 1)
    ax.set_ylim(0, 84)
    ax.set_xticks([16, 20, 24, 28, 32, 36, 38])
    ax.set_yticks([0, 20, 40, 60, 80], ["0%", "20%", "40%", "60%", "80%"])
    ax.set_xlabel("Submission-to-posting duration (calendar days)")
    ax.set_ylabel("Share of completed lifecycles")
    ax.grid(axis="y", color="#e6e6e6", linewidth=.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#888888")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    chart = io.BytesIO()
    fig.savefig(chart, format="pdf", metadata={"CreationDate": None})
    plt.close(fig)

    base = io.BytesIO()
    c = canvas.Canvas(base, pagesize=(520, 660), invariant=1)
    c.setTitle("Baseline OCPQ path and submission-to-posting distribution")
    c.setFont("PathSansBold", 11)
    c.drawString(12, 640, "(a) OCPQ path through the same Requirement object")
    c.drawString(12, 330, "Query results")
    headings = ["Support", "Coverage", "Selectivity", "Reach", "Exclusivity"]
    for i, heading in enumerate(headings):
        x = 12 + i * 101
        c.setFont("PathSans", 10)
        c.drawString(x, 310, heading)
        c.setFont("PathSansBold", 11)
        value = metrics[heading.lower()]
        c.drawString(x, 291, str(value) if heading == "Support" else f"{value:.3f}")
    c.setFont("PathSansBold", 11)
    c.drawString(12, 266, "(b) Throughput-time distribution for 25 completed lifecycles")
    c.setFont("PathSans", 10)
    c.drawString(12, 246, f"Min: {days.min():.2f}    Median: {days.median():.2f}"
                 f"    Mean: {days.mean():.2f}    Max: {days.max():.2f} days")
    c.showPage()
    c.save()
    pdf = merge_artwork(base.getvalue(), root / "assets/csq1_path_type_graph.pdf",
                        5, 348, 510, 282)
    pdf = merge_artwork(pdf, chart.getvalue(), 4, 3, 512, 235)
    (figures / "csq1_path_throughput.pdf").write_bytes(pdf)
    summary = {
        "n_connections": len(days), "mean_days": float(days.mean()),
        "median_days": float(days.median()), "min_days": float(days.min()),
        "max_days": float(days.max()), "bin_edges_days": bins.tolist(),
        "bin_counts": counts.tolist(), "bin_shares_percent": (counts / len(days) * 100).tolist(),
        "seconds_per_calendar_day": 86400,
    }
    return summary
