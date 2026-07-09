from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter


OUT_DIR = Path("submission/slide_assets")

COLORS = {
    "hybrid": "#2563eb",
    "bridge": "#dc2626",
    "dense": "#059669",
    "bm25": "#d97706",
    "gray": "#64748b",
    "light_gray": "#e2e8f0",
    "dark": "#0f172a",
    "success": "#16a34a",
    "partial": "#f59e0b",
    "missing": "#94a3b8",
}


def pct(x: float) -> str:
    return f"{x:.2f}%"


def setup_figure(title: str, subtitle: str | None = None):
    fig, ax = plt.subplots(figsize=(13.333, 7.5), dpi=144)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.text(0.055, 0.935, title, fontsize=24, fontweight="bold", color=COLORS["dark"])
    if subtitle:
        fig.text(0.055, 0.89, subtitle, fontsize=13, color=COLORS["gray"])
    return fig, ax


def save(fig, name: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(OUT_DIR / f"{name}.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def style_axis(ax):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", color=COLORS["light_gray"], linewidth=1)
    ax.tick_params(axis="both", labelsize=11, colors=COLORS["dark"])


def main_benchmark():
    fig, ax = setup_figure(
        "Bridge-Aware-Retrieval improves complete evidence coverage",
        "beir/hotpotqa/test - 7,405 queries - top-10 retrieval - Baseline = BM25 + Dense (RRF fusion)",
    )
    methods = ["Baseline\n(BM25 + Dense)", "Bridge-Aware-\nRetrieval"]
    full_support = [51.75, 60.08]
    latency = [0.76, 1.60]
    colors = [COLORS["hybrid"], COLORS["bridge"]]
    bars = ax.bar(methods, full_support, color=colors, width=0.48)
    ax.set_ylim(0, 75)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    style_axis(ax)
    ax.set_ylabel("Full-support@10", fontsize=12, color=COLORS["dark"])
    ax.text(
        0.5,
        0.80,
        "51.75% -> 60.08%",
        transform=fig.transFigure,
        ha="center",
        fontsize=30,
        fontweight="bold",
        color=COLORS["dark"],
    )
    ax.text(
        0.5,
        0.745,
        "+8.33 percentage points (+16.1% relative)",
        transform=fig.transFigure,
        ha="center",
        fontsize=15,
        color=COLORS["bridge"],
        fontweight="bold",
    )
    for bar, value, p95 in zip(bars, full_support, latency):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.4,
            pct(value),
            ha="center",
            fontsize=15,
            fontweight="bold",
            color=COLORS["dark"],
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            3.5,
            f"p95={p95:.2f}s",
            ha="center",
            fontsize=12,
            color="white",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=COLORS["dark"], edgecolor="none"),
        )
    fig.text(0.055, 0.035, "Baseline: BM25 + Dense retrieval. Bridge-Aware-Retrieval adds title/entity expansion for better evidence coverage, with higher latency.", fontsize=13, color=COLORS["gray"])
    save(fig, "03_main_benchmark_full_support")


def error_analysis():
    fig, ax = setup_figure(
        "Error analysis: Bridge-Aware-Retrieval reduces partial-support failures",
        "Evidence coverage breakdown on beir/hotpotqa/test: +617 full-support, -820 partial-support",
    )
    labels = ["Baseline\n(BM25 + Dense)", "Bridge-Aware-\nRetrieval"]
    success = np.array([3832, 4449])
    partial = np.array([3155, 2335])
    missing = np.array([418, 621])
    total = success + partial + missing
    success_p = success / total * 100
    partial_p = partial / total * 100
    missing_p = missing / total * 100
    y = np.arange(len(labels))
    ax.barh(y, success_p, color=COLORS["success"], label="Full-support success")
    ax.barh(y, partial_p, left=success_p, color=COLORS["partial"], label="Partial support")
    ax.barh(y, missing_p, left=success_p + partial_p, color=COLORS["missing"], label="Missing support")
    ax.set_xlim(0, 100)
    ax.set_yticks(y, labels)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(axis="both", labelsize=12, colors=COLORS["dark"])
    ax.grid(axis="x", color=COLORS["light_gray"])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False, fontsize=11)
    for i in range(len(labels)):
        ax.text(success_p[i] / 2, i, f"{success[i]:,}", va="center", ha="center", color="white", fontweight="bold")
        ax.text(success_p[i] + partial_p[i] / 2, i, f"{partial[i]:,}", va="center", ha="center", color=COLORS["dark"], fontweight="bold")
        ax.text(success_p[i] + partial_p[i] + missing_p[i] / 2, i, f"{missing[i]:,}", va="center", ha="center", color=COLORS["dark"], fontweight="bold")
    fig.text(0.055, 0.055, "Bridge-Aware-Retrieval targets the main HotpotQA failure mode: one support found, one missing.", fontsize=13, color=COLORS["gray"])
    save(fig, "04_error_analysis_stacked")


def external_benchmark():
    fig, ax = setup_figure(
        "External benchmark context: BEIR / Pyserini HotpotQA",
        "Metric: nDCG@10. Baseline = BM25 + Dense retrieval (RRF fusion).",
    )
    systems = [
        "BGE-base-en-v1.5",
        "Bridge-Aware-\nRetrieval",
        "Baseline\n(BM25 + Dense)",
        "SPLADE++",
        "Contriever MS MARCO",
        "BM25 flat",
        "BM25 multifield",
    ]
    values = [72.60, 71.20, 70.01, 68.70, 63.80, 63.30, 60.30]
    colors = [COLORS["gray"], COLORS["bridge"], COLORS["hybrid"], COLORS["gray"], COLORS["gray"], COLORS["gray"], COLORS["gray"]]
    y = np.arange(len(systems))
    ax.barh(y, values, color=colors, height=0.58)
    ax.set_yticks(y, systems)
    ax.invert_yaxis()
    ax.set_xlim(55, 75)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color=COLORS["light_gray"])
    ax.tick_params(axis="both", labelsize=11, colors=COLORS["dark"])
    for yy, v in zip(y, values):
        ax.text(v + 0.25, yy, pct(v), va="center", fontsize=12, fontweight="bold", color=COLORS["dark"])
    fig.text(0.055, 0.055, "Context comparison only: index construction, model size, quantization, and runtime differ.", fontsize=12, color=COLORS["gray"])
    save(fig, "05_external_beir_ndcg")


def storage_tradeoff():
    fig, ax = setup_figure(
        "TurboVec storage trade-off",
        "Full HotpotQA dense vectors: 5.23M docs, 384 dimensions",
    )
    labels = ["Raw float32 vectors", "Raw float16 vectors", "TurboVec 4-bit .tvim"]
    sizes = [8.04, 4.02, 1.07]
    colors = [COLORS["gray"], COLORS["dense"], COLORS["bridge"]]
    y = np.arange(len(labels))
    bars = ax.barh(y, sizes, color=colors, height=0.55)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 8.8)
    ax.set_xlabel("")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color=COLORS["light_gray"])
    ax.tick_params(axis="both", labelsize=12, colors=COLORS["dark"])
    for bar, value in zip(bars, sizes):
        ax.text(value + 0.12, bar.get_y() + bar.get_height() / 2, f"{value:.2f} GB", va="center", fontsize=14, fontweight="bold", color=COLORS["dark"])
    fig.text(0.53, 0.55, "~7.5x smaller\nthan raw float32", fontsize=22, fontweight="bold", color=COLORS["bridge"])
    fig.text(0.055, 0.055, "Note: Elasticsearch dense_vector would also include HNSW/Lucene/JVM/cache overhead not counted here.", fontsize=12, color=COLORS["gray"])
    save(fig, "06_turbovec_storage_tradeoff")


def paraphrase_robustness():
    fig, ax = setup_figure(
        "Paraphrase robustness",
        "Metric: Full-support@10 across 200-query paraphrase sets",
    )
    xlabels = ["Original", "Mild", "Strong", "Lexical\nStrong"]
    x = np.arange(len(xlabels))
    series = {
        "BM25": ([36.5, 36.5, 37.5, 34.0], COLORS["bm25"]),
        "Dense": ([51.5, 51.5, 51.5, 49.5], COLORS["dense"]),
        "Baseline": ([53.5, 51.5, 51.5, 48.0], COLORS["hybrid"]),
    }
    for name, (vals, color) in series.items():
        ax.plot(x, vals, marker="o", linewidth=3, markersize=7, color=color, label=name)
    ax.set_xticks(x, xlabels)
    ax.set_ylim(30, 58)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax.set_ylabel("Full-support@10", fontsize=12)
    style_axis(ax)
    ax.legend(loc="lower left", ncol=2, frameon=False, fontsize=11)
    ax.annotate(
        "Lexical Strong\nis the real stress test",
        xy=(3, 49.5),
        xytext=(2.25, 55),
        arrowprops=dict(arrowstyle="->", color=COLORS["dark"], lw=1.5),
        fontsize=13,
        fontweight="bold",
        color=COLORS["dark"],
    )
    fig.text(0.055, 0.055, "Dense retrieval is the most stable under lexical substitution; baseline is strongest on original queries.", fontsize=12, color=COLORS["gray"])
    save(fig, "07_paraphrase_robustness")


def vimqa_results():
    fig, ax = setup_figure(
        "VimQA retrieval extension",
        "Vietnamese retrieval proxy: 3,623 documents, 9,044 queries",
    )
    methods = ["BM25", "BKAI dense", "Hybrid"]
    recall = [96.27, 87.16, 96.44]
    mrr = [86.06, 72.72, 82.77]
    ndcg = [88.59, 76.25, 86.09]
    x = np.arange(len(methods))
    w = 0.24
    ax.bar(x - w, recall, width=w, color=COLORS["success"], label="Recall@10")
    ax.bar(x, mrr, width=w, color=COLORS["hybrid"], label="MRR@10")
    ax.bar(x + w, ndcg, width=w, color=COLORS["bridge"], label="nDCG@10")
    ax.set_xticks(x, methods)
    ax.set_ylim(65, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    style_axis(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=3, frameon=False, fontsize=11)
    fig.text(0.58, 0.70, "Default: BM25", fontsize=22, fontweight="bold", color=COLORS["dark"])
    fig.text(0.58, 0.64, "Best rank-sensitive metrics\nand lowest p95 latency (84 ms)", fontsize=13, color=COLORS["gray"])
    save(fig, "08_vimqa_extension")


def reranker_ablation():
    fig, ax = setup_figure(
        "RRF vs reranker ablation",
        "Reranking improves order, but not complete evidence coverage",
    )
    metrics = ["Full-support@10", "MRR@10", "nDCG@10"]
    rrf = [54.5, 86.91, 72.91]
    rerank = [54.5, 92.68, 74.64]
    x = np.arange(len(metrics))
    w = 0.34
    ax.bar(x - w / 2, rrf, width=w, color=COLORS["hybrid"], label="RRF")
    ax.bar(x + w / 2, rerank, width=w, color=COLORS["bridge"], label="Reranker")
    ax.set_xticks(x, metrics)
    ax.set_ylim(45, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    style_axis(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    for i, (a, b) in enumerate(zip(rrf, rerank)):
        ax.text(i - w / 2, a + 1.2, pct(a), ha="center", fontsize=10, fontweight="bold")
        ax.text(i + w / 2, b + 1.2, pct(b), ha="center", fontsize=10, fontweight="bold")
    fig.text(0.055, 0.055, "Full-support net wins: RRF-only 14, reranker-only 14, net reranker wins 0.", fontsize=12, color=COLORS["gray"])
    save(fig, "09_rrf_vs_reranker")


def metadata_funnel():
    fig, ax = setup_figure(
        "Metadata filtering narrows the search space",
        "Synthetic HotpotQA metadata demo: author / created_at / modified_at",
    )
    labels = ["Full corpus", "author = Nguyen An", "January 2024", "author + January 2024"]
    docs = [5_233_329, 40_886, 222_239, 1_793]
    y = np.arange(len(labels))
    colors = [COLORS["gray"], COLORS["hybrid"], COLORS["dense"], COLORS["bridge"]]
    ax.barh(y, docs, color=colors, height=0.55)
    ax.set_xscale("log")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color=COLORS["light_gray"])
    ax.tick_params(axis="both", labelsize=12, colors=COLORS["dark"])
    for yy, value in zip(y, docs):
        ax.text(value * 1.08, yy, f"{value:,}", va="center", fontsize=13, fontweight="bold", color=COLORS["dark"])
    fig.text(0.52, 0.64, "author + date\nnarrows by 99.97%", fontsize=22, fontweight="bold", color=COLORS["bridge"])
    fig.text(0.055, 0.055, "Metadata is used as structured filters, not embedded into dense vectors.", fontsize=12, color=COLORS["gray"])
    save(fig, "10_metadata_filtering_funnel")


def conclusion_summary():
    fig = plt.figure(figsize=(13.333, 7.5), dpi=144)
    fig.patch.set_facecolor("white")
    fig.text(0.055, 0.92, "Final contribution", fontsize=25, fontweight="bold", color=COLORS["dark"])
    cards = [
        ("Full-corpus system", "5.23M docs\nAPI + UI\nBenchmark", COLORS["hybrid"]),
        ("Baseline retrieval", "BM25 + Dense\nRRF fusion", COLORS["dense"]),
        ("Bridge-Aware-Retrieval", "+8.33 pp\nFull-support@10", COLORS["bridge"]),
    ]
    for i, (title, body, color) in enumerate(cards):
        x = 0.07 + i * 0.305
        rect = plt.Rectangle((x, 0.28), 0.27, 0.43, transform=fig.transFigure, color=color, alpha=0.10)
        fig.patches.append(rect)
        fig.text(x + 0.02, 0.63, title, fontsize=17, fontweight="bold", color=color)
        fig.text(x + 0.02, 0.42, body, fontsize=22, fontweight="bold", color=COLORS["dark"], linespacing=1.25)
    fig.text(0.055, 0.09, "From keyword search -> baseline (BM25 + Dense) -> Bridge-Aware-Retrieval", fontsize=15, color=COLORS["gray"])
    save(fig, "11_conclusion_summary")


def main():
    main_benchmark()
    error_analysis()
    external_benchmark()
    storage_tradeoff()
    paraphrase_robustness()
    vimqa_results()
    reranker_ablation()
    metadata_funnel()
    conclusion_summary()
    print(f"Wrote chart assets to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
