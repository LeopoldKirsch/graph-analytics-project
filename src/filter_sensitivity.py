"""Are the results an artefact of which routes DGAC publishes?

DGAC only publishes a route-month when it has >= 10,000 passenger-
equivalents and >= 3 airlines, none above 85% of the traffic. We cannot add
the hidden routes back, but we can check whether the conclusions move when
we make the filter *stricter* in two ways:
- passenger threshold: keep only routes above 50k / 100k / 250k / 500k
  passengers a year (the core of the network);
- year-round routes: keep only routes published in at least 6 or 12 months
  (removes seasonal routes, which enter and leave the data).

If CDG's role, the diameter and the hub ranking barely change as the graph
shrinks, the conclusions do not hinge on marginal routes. This is evidence
of robustness, not proof: the routes the rule hides cannot be tested.

Each filtered graph keeps only airports with at least one remaining route.
This applies to the baseline too, so the domestic baseline here (25 airports)
differs from views.py (31 airports including 6 without a domestic route), and
normalised betweenness values differ accordingly.

Usage:
    python src/filter_sensitivity.py   # 2025, writes results/sensitivity_2025.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd

from build_graph import build_graph
from centrality import freeman_centralization
from core_metrics import largest_component
from views import domestic_graph

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

VARIANTS = [
    ("baseline (all published routes)", lambda d: True),
    (">= 50k passengers", lambda d: d["passengers"] >= 50_000),
    (">= 100k passengers", lambda d: d["passengers"] >= 100_000),
    (">= 250k passengers", lambda d: d["passengers"] >= 250_000),
    (">= 500k passengers", lambda d: d["passengers"] >= 500_000),
    (">= 6 months published", lambda d: d["months_active"] >= 6),
    ("12 months published", lambda d: d["months_active"] == 12),
]


def filtered(G: nx.Graph, keep) -> nx.Graph:
    H = G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if keep(d)]).copy()
    H.graph.update(G.graph)
    return H


def metrics(H: nx.Graph, base_btw: dict) -> dict:
    lcc = largest_component(H)
    btw = nx.betweenness_centrality(H)
    ranking = sorted(btw, key=btw.get, reverse=True)
    common = [n for n in base_btw if n in btw]
    rho = pd.Series({n: base_btw[n] for n in common}).corr(
        pd.Series({n: btw[n] for n in common}), method="spearman")
    return {
        "nodes": H.number_of_nodes(),
        "edges": H.number_of_edges(),
        "passengers_m": sum(p for _, _, p in H.edges(data="passengers")) / 1e6,
        "components": nx.number_connected_components(H),
        "lcc_share": lcc.number_of_nodes() / H.number_of_nodes(),
        "diameter_lcc": nx.diameter(lcc),
        "top_airport": ranking[0],
        "cdg_betweenness": btw.get("LFPG", float("nan")),
        "orly_betweenness": btw.get("LFPO", float("nan")),
        "orly_rank": ranking.index("LFPO") + 1 if "LFPO" in btw else None,
        "betweenness_centralization": freeman_centralization(H)["betweenness_centralization"],
        "spearman_vs_baseline": rho,
    }


def run(year: int = 2025) -> pd.DataFrame:
    G = build_graph(year)
    rows = []
    for view, make in (("full network", lambda g: g), ("domestic", domestic_graph)):
        base = make(filtered(G, VARIANTS[0][1]))
        base_btw = nx.betweenness_centrality(base)
        for label, keep in VARIANTS:
            H = make(filtered(G, keep))
            H.remove_nodes_from(list(nx.isolates(H)))
            if H.number_of_edges() == 0:
                continue
            rows.append({"view": view, "variant": label, **metrics(H, base_btw)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    df = run(year)
    RESULTS_DIR.mkdir(exist_ok=True)
    pd.set_option("display.width", 250, "display.float_format", "{:.3f}".format)
    print(df.to_string(index=False))
    df.to_csv(RESULTS_DIR / f"sensitivity_{year}.csv", index=False)
    print(f"\nSaved results/sensitivity_{year}.csv")
