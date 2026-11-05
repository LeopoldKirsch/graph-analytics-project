"""Comparison over time: 2019 (pre-COVID), 2020 (COVID) and 2025.

Question: did COVID change the structure of the network, and has it recovered?
In particular, did the network become more or less dependent on CDG?

The same graph model (build_graph) and the same measures are applied to each
year, so differences come from the data, not from the method:
- size and connectivity: nodes, edges, density, components, largest connected
  component (LCC), diameter and radius of the LCC (unweighted hops);
- concentration: CDG's share of routes and of published passengers, Paris
  (CDG + Orly) passenger share, Herfindahl-Hirschman index (HHI) of airport
  weighted degree (1 / HHI = "effective number of airports");
- centrality of the hubs: normalised betweenness (unweighted) of CDG, Orly,
  Nice and Lyon;
- communities: number and weighted modularity (communities.py, seed 42);
- resilience: LCC share and passengers kept once CDG is removed (resilience.py);
- route turnover between years: routes kept, lost and gained, Jaccard index.

The core metrics are computed here with plain NetworkX calls. When
src/core_metrics.py (feature/core-metrics) is merged, ``size_and_connectivity``
can call it instead so that both parts of the report use exactly one function.

Caveat: a route only appears when it passes the DGAC publication rule
(>= 10,000 passenger-equivalents in the month, >= 3 airlines, none above 85 %).
In 2020 many routes fell below the threshold, so part of the "lost" routes are
routes that still flew but were no longer published.

Usage:
    python src/comparison.py
Outputs: results/comparison_years.csv, results/comparison_routes.csv
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from build_graph import build_graphs
from communities import louvain, modularity
from resilience import evaluate

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
YEARS = (2019, 2020, 2025)
CDG, ORLY = "LFPG", "LFPO"
HUBS = {"LFPG": "CDG", "LFPO": "Orly", "LFMN": "Nice", "LFLL": "Lyon"}


def size_and_connectivity(G: nx.Graph) -> dict:
    lcc = G.subgraph(max(nx.connected_components(G), key=len))
    return {
        "nodes": G.number_of_nodes(),
        "french_nodes": sum(1 for _, f in G.nodes(data="french") if f),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "mean_degree": 2 * G.number_of_edges() / G.number_of_nodes(),
        "passengers_m": sum(p for _, _, p in G.edges(data="passengers")) / 1e6,
        "components": nx.number_connected_components(G),
        "lcc_nodes": lcc.number_of_nodes(),
        "lcc_diameter": nx.diameter(lcc),
        "lcc_radius": nx.radius(lcc),
        "lcc_avg_path": nx.average_shortest_path_length(lcc),
    }


def concentration(G: nx.Graph) -> dict:
    strength = dict(G.degree(weight="passengers"))
    total = sum(strength.values())
    shares = [s / total for s in strength.values()]
    hhi = sum(s * s for s in shares)
    total_pax = total / 2  # each passenger is counted at both ends
    paris = sum(p for u, v, p in G.edges(data="passengers") if u in (CDG, ORLY) or v in (CDG, ORLY))
    return {
        "cdg_routes": G.degree(CDG),
        "cdg_route_share": G.degree(CDG) / G.number_of_edges(),
        "cdg_passenger_share": strength[CDG] / total_pax,
        "paris_passenger_share": paris / total_pax,
        "strength_hhi": hhi,
        "effective_airports": 1 / hhi,
    }


def hub_betweenness(G: nx.Graph) -> dict:
    bc = nx.betweenness_centrality(G)  # unweighted, normalised
    return {f"betweenness_{name}": bc.get(code, 0.0) for code, name in HUBS.items()}


def communities_and_resilience(G: nx.Graph) -> dict:
    comms = louvain(G, weighted=True)
    no_cdg = evaluate(G, [CDG])
    return {
        "n_communities": len(comms),
        "modularity": modularity(G, comms, weighted=True),
        "lcc_share_without_cdg": no_cdg["lcc_share"],
        "passengers_kept_without_cdg": no_cdg["passengers_kept"],
        "isolated_without_cdg": no_cdg["isolated"],
    }


def year_table(graphs: dict[int, nx.Graph]) -> pd.DataFrame:
    rows = []
    for y, G in graphs.items():
        rows.append({"year": y, **size_and_connectivity(G), **concentration(G),
                     **hub_betweenness(G), **communities_and_resilience(G)})
    return pd.DataFrame(rows).set_index("year")


def route_turnover(graphs: dict[int, nx.Graph]) -> pd.DataFrame:
    """Routes kept / lost / gained between each pair of years."""
    edge_sets = {y: {frozenset(e) for e in G.edges()} for y, G in graphs.items()}
    years = sorted(graphs)
    rows = []
    for i, a in enumerate(years):
        for b in years[i + 1:]:
            ea, eb = edge_sets[a], edge_sets[b]
            rows.append({
                "from": a, "to": b,
                "kept": len(ea & eb), "lost": len(ea - eb), "gained": len(eb - ea),
                "jaccard": len(ea & eb) / len(ea | eb),
            })
    # 2019 routes lost in 2020 and published again in 2025 (recovery)
    if {2019, 2020, 2025} <= set(years):
        lost = edge_sets[2019] - edge_sets[2020]
        back = lost & edge_sets[2025]
        rows.append({"from": 2019, "to": 2025, "kept": len(back), "lost": len(lost - back),
                     "gained": float("nan"), "jaccard": float("nan"),
                     "note": "routes lost in 2020: back in 2025 (kept) / still missing (lost)"})
    return pd.DataFrame(rows)


def routes_lost_by_hub(graphs: dict[int, nx.Graph], a: int = 2019, b: int = 2020) -> pd.Series:
    """Which French airports lost the most published routes between two years."""
    Ga, Gb = graphs[a], graphs[b]
    lost = {}
    for n, f in Ga.nodes(data="french"):
        if f:
            before = set(Ga[n])
            after = set(Gb[n]) if n in Gb else set()
            lost[Ga.nodes[n]["name"]] = len(before - after)
    return pd.Series(lost).sort_values(ascending=False)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    graphs = build_graphs(YEARS)
    table = year_table(graphs)
    table.to_csv(RESULTS_DIR / "comparison_years.csv")
    turnover = route_turnover(graphs)
    turnover.to_csv(RESULTS_DIR / "comparison_routes.csv", index=False)
    pd.set_option("display.width", 200)
    print(table.T.round(3).to_string())
    print()
    print(turnover.round(3).to_string(index=False))
    print("\nRoutes lost 2019 -> 2020 by French airport (top 8):")
    print(routes_lost_by_hub(graphs).head(8).to_string())


if __name__ == "__main__":
    main()
