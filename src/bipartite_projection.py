"""Option 2 (explored, rejected): bipartite projection of French airports.

Model:
- Bipartite graph B: French airports on one side, foreign airports on the
  other, an edge when a published route links them. Domestic (French-French)
  routes are dropped; foreign-foreign routes do not exist in the data.
- Projection P onto French airports: two French airports are linked when they
  serve at least one common foreign destination.
    * "shared":  weight = number of common foreign destinations
    * "jaccard": weight = common / union of their foreign destinations,
                 which removes the size effect of large airports
- Communities on P with Louvain (weight="weight", seed=42), and modularity.

Question it was meant to answer: which French airports compete for the same
international markets? Each variant is also run without Paris (CDG + Orly) to
test whether Paris alone hides the structure.

Usage:
    python src/bipartite_projection.py             # 2019 and 2025, writes results/
    python src/bipartite_projection.py 2025
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd
from networkx.algorithms import bipartite
from networkx.algorithms.community import louvain_communities, modularity

from build_graph import build_graph

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
PARIS = ("LFPG", "LFPO")
SEED = 42


def bipartite_graph(G: nx.Graph) -> nx.Graph:
    """French-foreign edges of G as a bipartite graph (bipartite=0 French, 1 foreign)."""
    B = nx.Graph(year=G.graph.get("year"))
    for u, v, d in G.edges(data=True):
        if G.nodes[u]["french"] != G.nodes[v]["french"]:
            B.add_edge(u, v, **d)
    for n in B:
        B.nodes[n].update(G.nodes[n])
        B.nodes[n]["bipartite"] = 0 if G.nodes[n]["french"] else 1
    assert bipartite.is_bipartite(B)
    return B


def french_side(B: nx.Graph) -> set[str]:
    return {n for n, side in B.nodes(data="bipartite") if side == 0}


def project(B: nx.Graph, method: str = "shared") -> nx.Graph:
    """Project B onto French airports. method: "shared" or "jaccard"."""
    # sorted: a set of codes iterates in a different order on each run (string
    # hashing), which changes the projection's node order and hence Louvain
    top = sorted(french_side(B))
    if method == "shared":
        P = bipartite.weighted_projected_graph(B, top)
    elif method == "jaccard":
        P = bipartite.overlap_weighted_projected_graph(B, top, jaccard=True)
    else:
        raise ValueError(f"unknown method {method!r}")
    for n in P:
        P.nodes[n]["foreign_destinations"] = B.degree(n)
    C = nx.Graph()  # same graph, nodes and edges in sorted order
    C.add_nodes_from(sorted(P.nodes(data=True)))
    C.add_edges_from(sorted((min(u, v), max(u, v), d) for u, v, d in P.edges(data=True)))
    return C


def evaluate(P: nx.Graph, label: str = "") -> dict:
    """Size, density, components, Louvain communities and modularity of P."""
    comms = louvain_communities(P, weight="weight", seed=SEED)
    comms = sorted(comms, key=lambda c: (-len(c), sorted(c)[0]))
    return {
        "variant": label,
        "nodes": P.number_of_nodes(),
        "edges": P.number_of_edges(),
        "density": round(nx.density(P), 3),
        "components": nx.number_connected_components(P),
        "communities": len(comms),
        "community_sizes": [len(c) for c in comms],
        "largest_community_share": round(len(comms[0]) / P.number_of_nodes(), 2),
        "modularity": round(modularity(P, comms, weight="weight"), 3),
        "largest_community": sorted(comms[0]),
    }


def run(year: int) -> tuple[pd.DataFrame, nx.Graph]:
    """All four variants for one year. Returns the table and the bipartite graph."""
    B = bipartite_graph(build_graph(year))
    rows = []
    for method in ("shared", "jaccard"):
        P = project(B, method)
        rows.append({"year": year, **evaluate(P, f"{method}, with Paris")})
        P.remove_nodes_from(PARIS)
        rows.append({"year": year, **evaluate(P, f"{method}, without Paris")})
    return pd.DataFrame(rows), B


def destinations_table(B: nx.Graph) -> pd.DataFrame:
    """Number of foreign destinations per French airport (explains the result)."""
    return (
        pd.DataFrame(
            [(n, B.nodes[n]["name"], B.degree(n)) for n in french_side(B)],
            columns=["icao", "name", "foreign_destinations"],
        )
        .sort_values("foreign_destinations", ascending=False)
        .reset_index(drop=True)
    )


def top_overlaps(B: nx.Graph, k: int = 10, exclude=PARIS) -> pd.DataFrame:
    """Pairs of French airports sharing the most foreign destinations."""
    P = project(B, "jaccard")
    S = project(B, "shared")
    rows = [
        (u, v, S[u][v]["weight"], round(d["weight"], 2))
        for u, v, d in P.edges(data=True)
        if u not in exclude and v not in exclude
    ]
    df = pd.DataFrame(rows, columns=["airport_1", "airport_2", "shared", "jaccard"])
    return df.sort_values("shared", ascending=False).head(k).reset_index(drop=True)


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or [2019, 2025]
    RESULTS_DIR.mkdir(exist_ok=True)
    pd.set_option("display.width", 200, "display.max_colwidth", 60)
    tables = []
    for y in years:
        table, B = run(y)
        tables.append(table)
        print(f"\n=== {y}: {len(french_side(B))} French airports with foreign routes ===")
        print(table.drop(columns="largest_community").to_string(index=False))
        print("\nForeign destinations per French airport:")
        print(destinations_table(B).to_string(index=False))
        print("\nLargest overlaps outside Paris:")
        print(top_overlaps(B).to_string(index=False))
    out = RESULTS_DIR / "bipartite_projection.csv"
    pd.concat(tables).to_csv(out, index=False)
    print(f"\nSaved {out}")
