"""Exploratory: two ways to count the passengers lost when airports are removed.

Question: when airports are removed, how much of the year's traffic is lost?
The answer depends on what "still served" means, so two measures are kept side
by side (exploratory, not a required deliverable):

- passengers_kept (used in resilience.py): share of the year's published
  passengers carried by routes that still exist, i.e. routes that do not touch
  a removed airport. A route that survives in a small cut-off component (for
  example Saint-Martin - Saint-Barthelemy) still counts.
- passengers_connected: share carried by routes inside the largest connected
  component (LCC) only. Traffic that survives in a fragment cut off from the
  main network is counted as lost. It is never higher than passengers_kept;
  at 0 removals it is already below 1 because the intact graph has small
  separate components.

The gap between the two is the traffic that still flies but is cut off from
the main network.

Same graph, same attack orders and same random seeds as resilience.py
(static orders computed once on the intact graph: degree, passengers,
betweenness; random = mean over N_RANDOM seeds), so the curves line up with
results/resilience_curves_<year>.csv.

Usage:
    python src/passenger_metrics.py            # 2019, 2020, 2025
Outputs: results/passenger_metrics_curves.csv, results/passenger_metrics_scenarios.csv,
results/passenger_metrics_2025.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from build_graph import build_graph
from resilience import MAX_REMOVED, N_RANDOM, SCENARIOS, attack_order

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
YEARS = (2019, 2020, 2025)
STRATEGIES = ("degree", "passengers", "betweenness", "random")
METRICS = {  # column: (label, colour from the validated default palette)
    "passengers_kept": ("Routes still flying (passengers_kept)", "#2a78d6"),
    "passengers_connected": ("Routes in the largest component (passengers_connected)", "#eb6834"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def passenger_shares(H: nx.Graph, total_pax: float) -> dict:
    """Both passenger measures for H (the graph after removals)."""
    if H.number_of_nodes() == 0:
        return {"passengers_kept": 0.0, "passengers_connected": 0.0}
    lcc = H.subgraph(max(nx.connected_components(H), key=len))
    return {
        "passengers_kept": sum(p for _, _, p in H.edges(data="passengers")) / total_pax,
        "passengers_connected": sum(p for _, _, p in lcc.edges(data="passengers")) / total_pax,
    }


def curve(G: nx.Graph, order: list, total_pax: float, max_removed: int = MAX_REMOVED) -> pd.DataFrame:
    H = G.copy()
    rows = []
    for k in range(max_removed + 1):
        if k > 0:
            H.remove_node(order[k - 1])
        rows.append({"removed": k, "last_removed": order[k - 1] if k else "",
                     **passenger_shares(H, total_pax)})
    return pd.DataFrame(rows)


def curves(G: nx.Graph) -> pd.DataFrame:
    total_pax = sum(p for _, _, p in G.edges(data="passengers"))
    parts = []
    for s in STRATEGIES[:-1]:
        parts.append(curve(G, attack_order(G, s), total_pax).assign(strategy=s))
    rand = pd.concat([curve(G, attack_order(G, "random", seed), total_pax)
                      for seed in range(N_RANDOM)])
    mean = rand.groupby("removed")[list(METRICS)].mean().reset_index()
    parts.append(mean.assign(last_removed="", strategy="random"))
    out = pd.concat(parts, ignore_index=True)
    out["gap"] = out["passengers_kept"] - out["passengers_connected"]
    out.insert(0, "year", G.graph["year"])
    return out[["year", "strategy", "removed", "last_removed", *METRICS, "gap"]]


def scenarios(G: nx.Graph) -> pd.DataFrame:
    total_pax = sum(p for _, _, p in G.edges(data="passengers"))
    rows = []
    for name, removed in SCENARIOS.items():
        H = G.copy()
        H.remove_nodes_from(removed)
        rows.append({"year": G.graph["year"], "scenario": name, **passenger_shares(H, total_pax)})
    df = pd.DataFrame(rows)
    df["gap"] = df["passengers_kept"] - df["passengers_connected"]
    return df


def plot(df: pd.DataFrame, year: int, path: Path) -> None:
    d = df[df["year"] == year]
    titles = {"degree": "Targeted: degree", "passengers": "Targeted: passengers",
              "betweenness": "Targeted: betweenness (static)",
              "random": f"Random failure (mean of {N_RANDOM})"}
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.2), sharey=True)
    for ax, s in zip(axes, STRATEGIES):
        g = d[d["strategy"] == s]
        for col, (label, color) in METRICS.items():
            ax.plot(g["removed"], g[col], color=color, linewidth=2, label=label)
        ax.set_title(titles[s], loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Airports removed", fontsize=8.5, color=MUTED)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.set_ylim(0, 1.02)
        ax.set_xlim(0, MAX_REMOVED)
        ax.set_xticks(range(0, MAX_REMOVED + 1, 5))
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#d6d5d0")
        ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    axes[0].set_ylabel("Share of the year's passengers", fontsize=8.5, color=MUTED)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", ncol=2, frameon=False, fontsize=9,
               bbox_to_anchor=(0.01, 0.93), labelcolor=INK)
    fig.suptitle(f"Exploratory, {year}: passengers still served after removing airports, two definitions",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86), w_pad=2.5)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def main(years) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    graphs = {y: build_graph(y) for y in years}
    cur = pd.concat([curves(G) for G in graphs.values()], ignore_index=True)
    scen = pd.concat([scenarios(G) for G in graphs.values()], ignore_index=True)
    cur.to_csv(RESULTS_DIR / "passenger_metrics_curves.csv", index=False)
    scen.to_csv(RESULTS_DIR / "passenger_metrics_scenarios.csv", index=False)
    if 2025 in graphs:
        plot(cur, 2025, RESULTS_DIR / "passenger_metrics_2025.png")
    pd.set_option("display.width", 200)
    print(scen.round(3).to_string(index=False))
    print()
    print(cur[cur["removed"].isin([1, 2, 5, 10])].round(3).to_string(index=False))


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or YEARS)
