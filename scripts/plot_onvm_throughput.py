#!/usr/bin/env python3
"""Parse ONVM manager stdout logs and plot UPF throughput experiments.

Example:
    python scripts/plot_onvm_throughput.py log/onvm_mgr_20260511_010758.log

Outputs:
    <stem>_parsed.csv
    <stem>_summary.csv
    <stem>_segments.csv
    <stem>_summary.png/.pdf
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from statistics import mean, median


PORT_RE = re.compile(
    r"Port\s+(\d+)\s+-\s+rx:\s*(\d+)\s*"
    r"\(\s*(\d+)\s+pps\)\s*tx:\s*(\d+)\s*"
    r"\(\s*(\d+)\s+pps\)"
)
NF_RE = re.compile(
    r"^(upf_lb|upf_u)\s+"
    r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+"
    r"(\d+)\s*/\s*(\d+)\s+"
    r"(\d+)\s*/\s*(\d+)\s+"
    r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)"
)
ANSI_RE = re.compile(r"\x1B\[[0-9;?]*[A-Za-z]")

EXPERIMENT_LABELS = {
    "lb_1upf": "LB + 1 UPF-U",
    "lb_2upf": "LB + 2 UPF-U",
    "pure_lb": "Pure UPF-LB",
    "idle": "Idle",
    "other_active": "Other active",
}
EXPERIMENT_ORDER = ["lb_1upf", "lb_2upf", "pure_lb"]

# RColorBrewer "Paired" palette.
BLUE_LT = "#A6CEE3"
BLUE_DK = "#1F78B4"
GREEN_LT = "#B2DF8A"
GREEN_DK = "#33A02C"
RED_LT = "#FB9A99"
RED_DK = "#E31A1C"
ORANGE_LT = "#FDBF6F"
ORANGE_DK = "#FF7F00"
PURPLE_LT = "#CAB2D6"
PURPLE_DK = "#6A3D9A"
YELLOW_LT = "#FFFF99"
BROWN_DK = "#B15928"
PAIRED = [
    BLUE_LT, BLUE_DK,
    GREEN_LT, GREEN_DK,
    RED_LT, RED_DK,
    ORANGE_LT, ORANGE_DK,
    PURPLE_LT, PURPLE_DK,
    YELLOW_LT, BROWN_DK,
]

LB_COLOR = ORANGE_DK
UPF1_COLOR = BLUE_DK
UPF2_COLOR = GREEN_DK
CEILING_COLOR = RED_DK
MARKERS = ["s", "D", "^", "d", "o", "v", "P", "X"]
LINESTYLES = ["-", "--", "-.", ":", "-", "--", "-.", ":"]

ACADEMIC_COLORS = [
    BLUE_LT, BLUE_DK, GREEN_LT, GREEN_DK, RED_LT, RED_DK,
    ORANGE_LT, ORANGE_DK, PURPLE_LT, PURPLE_DK, YELLOW_LT, BROWN_DK,
]

ACADEMIC_RC_BASE = {
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica", "Liberation Sans"],
    "font.weight": "bold",
    "font.size": 16,
    "axes.titlesize": 16,
    "axes.labelsize": 16,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 14,
    "lines.linewidth": 1.5,
    "lines.markersize": 12,
    "axes.linewidth": 1.5,
    "axes.edgecolor": "black",
    "axes.axisbelow": True,
    "xtick.major.width": 1.5,
    "xtick.major.size": 3,
    "ytick.major.width": 1.5,
    "ytick.major.size": 3,
    "xtick.minor.width": 1.0,
    "xtick.minor.size": 2,
    "ytick.minor.width": 1.0,
    "ytick.minor.size": 2,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.linewidth": 1.0,
    "grid.alpha": 0.6,
    "axes.grid.axis": "y",
    "legend.frameon": False,
    "legend.handlelength": 1.5,
    "legend.handletextpad": 0.4,
    "legend.columnspacing": 1.0,
    "hatch.linewidth": 0.5,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
}


def clean_line(line: str) -> str:
    return ANSI_RE.sub("", line).replace("\x1b[2J", "").replace("\x1b[H", "").strip()


def finish_snapshot(snapshots: list[dict], cur: dict | None) -> None:
    if cur and (cur["ports"] or cur["nfs"]):
        snapshots.append(cur)


def parse_log(log_path: Path) -> list[dict]:
    snapshots: list[dict] = []
    cur: dict | None = None
    sample = -1

    for raw in log_path.read_text(errors="replace").splitlines():
        line = clean_line(raw)

        port_match = PORT_RE.search(line)
        if port_match:
            port = int(port_match.group(1))
            if port == 0:
                finish_snapshot(snapshots, cur)
                sample += 1
                cur = {"sample": sample, "ports": {}, "nfs": []}
            if cur is None:
                sample += 1
                cur = {"sample": sample, "ports": {}, "nfs": []}
            cur["ports"][port] = {
                "rx_total": int(port_match.group(2)),
                "rx_pps": int(port_match.group(3)),
                "tx_total": int(port_match.group(4)),
                "tx_pps": int(port_match.group(5)),
            }
            continue

        nf_match = NF_RE.match(line)
        if nf_match and cur is not None:
            cur["nfs"].append(
                {
                    "tag": nf_match.group(1),
                    "iid": int(nf_match.group(2)),
                    "sid": int(nf_match.group(3)),
                    "core": int(nf_match.group(4)),
                    "rx_pps": int(nf_match.group(5)),
                    "tx_pps": int(nf_match.group(6)),
                    "rx_drop": int(nf_match.group(7)),
                    "tx_drop": int(nf_match.group(8)),
                    "out": int(nf_match.group(9)),
                    "tonf": int(nf_match.group(10)),
                    "drop": int(nf_match.group(11)),
                }
            )

    finish_snapshot(snapshots, cur)
    return snapshots


def classify_snapshot(lb: dict | None, upf_rows: list[dict], active_threshold: int) -> str:
    active_upfs = [
        row
        for row in upf_rows
        if row["rx_pps"] > active_threshold or row["tx_pps"] > active_threshold
    ]
    if not lb or lb["rx_pps"] <= active_threshold:
        return "idle"
    if lb["tx_pps"] <= active_threshold and not active_upfs:
        return "pure_lb"
    if len(active_upfs) >= 2:
        return "lb_2upf"
    if len(active_upfs) == 1:
        return "lb_1upf"
    return "other_active"


def rows_from_snapshots(snapshots: list[dict], active_threshold: int) -> list[dict]:
    rows: list[dict] = []
    for snap in snapshots:
        lb_rows = [nf for nf in snap["nfs"] if nf["tag"] == "upf_lb"]
        upf_rows = [nf for nf in snap["nfs"] if nf["tag"] == "upf_u"]
        lb = max(lb_rows, key=lambda nf: nf["rx_pps"], default=None)
        experiment = classify_snapshot(lb, upf_rows, active_threshold)

        by_sid = {nf["sid"]: nf for nf in upf_rows}
        port0 = snap["ports"].get(0, {})
        port1 = snap["ports"].get(1, {})
        upf14 = by_sid.get(14, {})
        upf15 = by_sid.get(15, {})
        rows.append(
            {
                "sample": snap["sample"],
                "experiment": experiment,
                "port0_rx_pps": port0.get("rx_pps", 0),
                "port0_tx_pps": port0.get("tx_pps", 0),
                "port1_rx_pps": port1.get("rx_pps", 0),
                "port1_tx_pps": port1.get("tx_pps", 0),
                "lb_iid": lb.get("iid", 0) if lb else 0,
                "lb_core": lb.get("core", 0) if lb else 0,
                "lb_rx_pps": lb.get("rx_pps", 0) if lb else 0,
                "lb_tx_pps": lb.get("tx_pps", 0) if lb else 0,
                "lb_drop": lb.get("drop", 0) if lb else 0,
                "upf14_rx_pps": upf14.get("rx_pps", 0),
                "upf14_tx_pps": upf14.get("tx_pps", 0),
                "upf14_drop": upf14.get("drop", 0),
                "upf15_rx_pps": upf15.get("rx_pps", 0),
                "upf15_tx_pps": upf15.get("tx_pps", 0),
                "upf15_drop": upf15.get("drop", 0),
            }
        )
    return rows


def percentile(values: list[int], q: float) -> int:
    values = sorted(values)
    if not values:
        return 0
    idx = round((len(values) - 1) * q)
    return values[idx]


def summarize(rows: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for experiment in EXPERIMENT_ORDER:
        vals = [row for row in rows if row["experiment"] == experiment]
        if not vals:
            continue
        lb_rx = [int(row["lb_rx_pps"]) for row in vals]
        lb_tx = [int(row["lb_tx_pps"]) for row in vals]
        summary.append(
            {
                "experiment": experiment,
                "samples": len(vals),
                "lb_rx_avg_pps": round(mean(lb_rx)),
                "lb_rx_median_pps": round(median(lb_rx)),
                "lb_rx_p95_pps": percentile(lb_rx, 0.95),
                "lb_rx_max_pps": max(lb_rx),
                "lb_tx_avg_pps": round(mean(lb_tx)),
                "upf14_rx_avg_pps": round(mean([int(row["upf14_rx_pps"]) for row in vals])),
                "upf15_rx_avg_pps": round(mean([int(row["upf15_rx_pps"]) for row in vals])),
            }
        )
    return summary


def find_segments(rows: list[dict]) -> list[dict]:
    segments: list[dict] = []
    cur: dict | None = None
    for row in rows:
        experiment = row["experiment"]
        sample = int(row["sample"])
        if cur is None or cur["experiment"] != experiment:
            if cur:
                segments.append(cur)
            cur = {
                "experiment": experiment,
                "start_sample": sample,
                "end_sample": sample,
                "count": 1,
                "max_lb_rx": int(row["lb_rx_pps"]),
                "max_lb_tx": int(row["lb_tx_pps"]),
            }
        else:
            cur["end_sample"] = sample
            cur["count"] += 1
            cur["max_lb_rx"] = max(cur["max_lb_rx"], int(row["lb_rx_pps"]))
            cur["max_lb_tx"] = max(cur["max_lb_tx"], int(row["lb_tx_pps"]))
    if cur:
        segments.append(cur)
    return segments


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows and not fieldnames:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def setup_matplotlib():
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".matplotlib"))
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib
    from cycler import cycler
    from matplotlib import font_manager

    matplotlib.use("Agg")
    rc = dict(ACADEMIC_RC_BASE)
    rc["axes.prop_cycle"] = cycler("color", ACADEMIC_COLORS)
    matplotlib.rcParams.update(rc)

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    font_path = font_manager.findfont(
        font_manager.FontProperties(family="Arial"),
        fallback_to_default=True,
    )
    font_props = font_manager.FontProperties(fname=font_path, weight="bold", size=16)

    return plt, FuncFormatter, font_props


def style_ax(ax, font_props, enforce: bool = False) -> None:
    ax.xaxis.label.set_fontproperties(font_props)
    ax.yaxis.label.set_fontproperties(font_props)
    ax.title.set_fontproperties(font_props)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(font_props)

    legend = ax.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontproperties(font_props)

    if not enforce:
        return

    for spine in ax.spines.values():
        spine.set_linewidth(ACADEMIC_RC_BASE["axes.linewidth"])
        spine.set_edgecolor(ACADEMIC_RC_BASE["axes.edgecolor"])

    ax.tick_params(
        axis="both",
        which="major",
        direction=ACADEMIC_RC_BASE["xtick.direction"],
        width=ACADEMIC_RC_BASE["xtick.major.width"],
        length=ACADEMIC_RC_BASE["xtick.major.size"],
        labelsize=ACADEMIC_RC_BASE["xtick.labelsize"],
    )
    ax.tick_params(
        axis="both",
        which="minor",
        direction=ACADEMIC_RC_BASE["xtick.direction"],
        width=ACADEMIC_RC_BASE["xtick.minor.width"],
        length=ACADEMIC_RC_BASE["xtick.minor.size"],
    )
    ax.set_axisbelow(ACADEMIC_RC_BASE["axes.axisbelow"])
    grid_axis = ACADEMIC_RC_BASE["axes.grid.axis"]
    grid_kwargs = {
        "linestyle": ACADEMIC_RC_BASE["grid.linestyle"],
        "linewidth": ACADEMIC_RC_BASE["grid.linewidth"],
        "alpha": ACADEMIC_RC_BASE["grid.alpha"],
    }
    ax.xaxis.grid(False)
    ax.yaxis.grid(False)
    if grid_axis in ("x", "both"):
        ax.xaxis.grid(True, **grid_kwargs)
    if grid_axis in ("y", "both"):
        ax.yaxis.grid(True, **grid_kwargs)

    for line in ax.get_lines():
        line.set_linewidth(ACADEMIC_RC_BASE["lines.linewidth"])
        line.set_markersize(ACADEMIC_RC_BASE["lines.markersize"])


def style_fig(fig, font_props, legend_ncol: int | None = None,
              legend_loc: str = "top", enforce: bool = False, **legend_kwargs) -> None:
    for ax in fig.get_axes():
        style_ax(ax, font_props, enforce=enforce)

    if legend_ncol is None:
        for legend in fig.legends:
            for text in legend.get_texts():
                text.set_fontproperties(font_props)
        return

    seen = {}
    for ax in fig.get_axes():
        handles, labels = ax.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            if label not in seen:
                seen[label] = handle
        if ax.get_legend() is not None:
            ax.get_legend().remove()

    if not seen:
        return

    if legend_loc == "top":
        kwargs = {
            "ncol": legend_ncol,
            "frameon": False,
            "prop": font_props,
            "loc": "upper center",
            "bbox_to_anchor": (0.5, 1.0),
        }
    else:
        kwargs = {
            "ncol": legend_ncol,
            "frameon": False,
            "prop": font_props,
            "loc": legend_loc,
        }
    kwargs.update(legend_kwargs)
    fig.legend(list(seen.values()), list(seen.keys()), **kwargs)


def plot_summary(summary: list[dict], output_prefix: Path) -> None:
    plt, FuncFormatter, font_props = setup_matplotlib()

    by_exp = {row["experiment"]: row for row in summary}
    order = [exp for exp in EXPERIMENT_ORDER if exp in by_exp]
    labels = [EXPERIMENT_LABELS[exp] for exp in order]
    lb_avg = [int(by_exp[exp]["lb_rx_avg_pps"]) / 1_000_000 for exp in order]
    upf14_avg = [int(by_exp[exp]["upf14_rx_avg_pps"]) / 1_000_000 for exp in order]
    upf15_avg = [int(by_exp[exp]["upf15_rx_avg_pps"]) / 1_000_000 for exp in order]
    upf_total_avg = [upf14 + upf15 for upf14, upf15 in zip(upf14_avg, upf15_avg)]
    fig, ax = plt.subplots(figsize=(10.4, 5.9), dpi=160)
    x_positions = list(range(len(order)))
    width = 0.34

    lb_bars = ax.bar(
        [x - width / 2 for x in x_positions],
        lb_avg,
        width=width,
        color=LB_COLOR,
        edgecolor="#2d2d2d",
        linewidth=0.7,
        label="UPF-LB avg RPS",
    )
    upf_bars = ax.bar(
        [x + width / 2 for x in x_positions],
        upf_total_avg,
        width=width,
        color=UPF1_COLOR,
        edgecolor="#2d2d2d",
        linewidth=0.7,
        label="UPF-U 1 avg RPS",
    )

    # Split the two-worker UPF-U total bar to show each worker's share.
    for i, exp in enumerate(order):
        if upf14_avg[i] > 0 and upf15_avg[i] > 0:
            ax.bar(
                x_positions[i] + width / 2,
                upf14_avg[i],
                width=width,
                color=UPF1_COLOR,
                edgecolor="#2d2d2d",
                linewidth=0.7,
            )
            ax.bar(
                x_positions[i] + width / 2,
                upf15_avg[i],
                width=width,
                bottom=upf14_avg[i],
                color=UPF2_COLOR,
                edgecolor="#2d2d2d",
                linewidth=0.7,
                label="UPF-U 2 avg RPS",
            )

    for bars in (lb_bars, upf_bars):
        for bar in bars:
            if bar.get_height() <= 0:
                continue
            center_x = bar.get_x() + bar.get_width() / 2
            ax.text(
                center_x,
                bar.get_height() + 0.055,
                f"{bar.get_height():.2f}",
                ha="center",
                va="bottom",
                fontsize=14,
                fontweight="bold",
                fontproperties=font_props,
            )

    ax.set_title("")
    fig.suptitle("UPF-LB RPS Scaling", y=0.965, fontproperties=font_props)
    ax.set_ylabel("Requests per second (Mpps)")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max(lb_avg + upf_total_avg + [3.0]) * 1.1)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.1f}"))
    style_fig(fig, font_props, legend_ncol=4, legend_loc="top", enforce=True,
              bbox_to_anchor=(0.5, 0.91))
    fig.tight_layout(rect=(0, 0.02, 1, 0.895))
    fig.savefig(output_prefix.with_name(output_prefix.name + "_summary.png"), bbox_inches="tight")
    fig.savefig(output_prefix.with_name(output_prefix.name + "_summary.pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_timeline(rows: list[dict], segments: list[dict], summary: list[dict], output_prefix: Path) -> None:
    plt, _, font_props = setup_matplotlib()
    by_exp = {row["experiment"]: row for row in summary}
    ceiling = int(by_exp["pure_lb"]["lb_rx_avg_pps"]) / 1_000_000 if "pure_lb" in by_exp else None

    samples = [int(row["sample"]) for row in rows]
    lb_rx = [int(row["lb_rx_pps"]) / 1_000_000 for row in rows]
    lb_tx = [int(row["lb_tx_pps"]) / 1_000_000 for row in rows]
    upf14 = [int(row["upf14_rx_pps"]) / 1_000_000 for row in rows]
    upf15 = [int(row["upf15_rx_pps"]) / 1_000_000 for row in rows]

    fig, ax = plt.subplots(figsize=(12, 5.8), dpi=160)
    for seg in segments:
        experiment = seg["experiment"]
        if experiment == "idle":
            continue
        start = int(seg["start_sample"])
        end = int(seg["end_sample"])
        segment_color = {
            "lb_1upf": BLUE_DK,
            "lb_2upf": GREEN_DK,
            "pure_lb": RED_DK,
        }.get(experiment, "#999999")
        ax.axvspan(start, end, color=segment_color, alpha=0.12)
        ax.text(
            (start + end) / 2,
            3.08,
            EXPERIMENT_LABELS.get(experiment, experiment),
            ha="center",
            va="center",
            fontsize=9,
            color="#333333",
        )

    ax.plot(samples, lb_rx, label="UPF-LB rx", color="#D64D4D", linewidth=1.7)
    ax.plot(samples, lb_tx, label="UPF-LB tx", color="#8C2D2D", linewidth=1.2, alpha=0.75)
    ax.plot(samples, upf14, label="UPF-U SID 14 rx", color="#4C78A8", linewidth=1.0, alpha=0.85)
    ax.plot(samples, upf15, label="UPF-U SID 15 rx", color="#59A14F", linewidth=1.0, alpha=0.85)
    if ceiling is not None:
        ax.axhline(ceiling, color="#B23A48", linestyle="--", linewidth=1.5, label=f"Pure LB avg {ceiling:.2f} Mpps")

    ax.set_title("ONVM Throughput Samples Across Experiments", fontsize=15, fontweight="bold", pad=14)
    ax.set_xlabel("ONVM refresh sample index")
    ax.set_ylabel("Requests per second")
    ax.set_ylim(0, max([3.0] + lb_rx + lb_tx + upf14 + upf15) * 1.08)
    ax.grid(axis="y", color="#d8dde6", linewidth=0.8)
    ax.set_axisbelow(True)
    style_fig(fig, font_props, legend_ncol=3, legend_loc="top", enforce=True)
    fig.tight_layout()
    fig.savefig(output_prefix.with_name(output_prefix.name + "_timeline.png"), bbox_inches="tight")
    fig.savefig(output_prefix.with_name(output_prefix.name + "_timeline.pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="ONVM manager raw stdout log")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory; defaults to the log directory")
    parser.add_argument("--prefix", default=None, help="Output filename prefix; defaults to input log stem")
    parser.add_argument("--active-threshold", type=int, default=1000, help="PPS threshold used to classify active NFs")
    parser.add_argument("--no-plots", action="store_true", help="Only write CSV files")
    args = parser.parse_args()

    log_path = args.log
    out_dir = args.out_dir or log_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = out_dir / (args.prefix or log_path.stem)

    snapshots = parse_log(log_path)
    rows = rows_from_snapshots(snapshots, args.active_threshold)
    summary = summarize(rows)
    segments = find_segments(rows)

    write_csv(output_prefix.with_name(output_prefix.name + "_parsed.csv"), rows)
    write_csv(output_prefix.with_name(output_prefix.name + "_summary.csv"), summary)
    write_csv(
        output_prefix.with_name(output_prefix.name + "_segments.csv"),
        segments,
        ["experiment", "start_sample", "end_sample", "count", "max_lb_rx", "max_lb_tx"],
    )

    if not args.no_plots:
        plot_summary(summary, output_prefix)

    print(f"Parsed snapshots: {len(rows)}")
    print(f"Wrote prefix: {output_prefix}")
    for row in summary:
        print(
            f"{row['experiment']}: "
            f"lb_avg={int(row['lb_rx_avg_pps']) / 1_000_000:.3f} Mpps, "
            f"upf14_avg={int(row['upf14_rx_avg_pps']) / 1_000_000:.3f} Mpps, "
            f"upf15_avg={int(row['upf15_rx_avg_pps']) / 1_000_000:.3f} Mpps"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
