"""Build the French air traffic network from DGAC open data.

Source: "Trafic aerien commercial mensuel francais par paire d'aeroports, par
sens, depuis 1990", DGAC, data.gouv.fr, Licence Ouverte 2.0.

Graph model (one graph per year):
- Nodes: airports (ICAO codes), French and foreign. Every airport that appears
  in at least one published pair of the year.
- Edges: one undirected edge per airport pair with published traffic in the
  year. The 12 monthly PAP rows of a pair are summed.
- Edge attributes: passengers, flights, freight_t, distance_km,
  months_active, cost.
- Node attributes: name, french (bool), zone ("metro" / "overseas" / "foreign"),
  icao_region, plus annual traffic from the APT series for French airports.

The graph is undirected because a PAP row already combines both directions of a
route, and simple because months are summed and airlines are not separated.

Usage:
    python src/build_graph.py            # summary of the 2025 graph
    python src/build_graph.py 2019 2020  # summaries of several years

    # from a notebook in notebooks/
    import sys; sys.path.append("../src")
    from build_graph import build_graph
    G = build_graph(2025)
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
YEARS = range(1990, 2026)

# APT rows that are national totals, not airports.
APT_AGGREGATES = {"ZZMT", "ZZOM"}

# First letter of an ICAO code -> broad world region (ICAO location indicator
# prefixes). Coarse on purpose: it is only used to help read communities.
ICAO_REGIONS = {
    "A": "South Pacific (west)",
    "B": "Iceland / Greenland",
    "C": "Canada",
    "D": "West & North Africa",
    "E": "Northern Europe",
    "F": "Southern & Indian Ocean Africa",
    "G": "West Africa & Morocco",
    "H": "East Africa & Egypt",
    "K": "United States",
    "L": "Southern Europe & Mediterranean",
    "M": "Central America & Mexico",
    "N": "South Pacific",
    "O": "Middle East",
    "P": "North Pacific",
    "R": "East Asia",
    "S": "South America",
    "T": "Caribbean",
    "U": "Russia & Central Asia",
    "V": "South & Southeast Asia",
    "W": "Maritime Southeast Asia",
    "Y": "Australia",
    "Z": "China",
}


def _read_csv(path: Path) -> pd.DataFrame:
    # DGAC files: semicolon-separated, decimal comma, UTF-8 with BOM.
    return pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")


def load_pap(year: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Monthly airport-pair rows for one year (raw DGAC columns)."""
    return _read_csv(data_dir / "pap" / f"ASP_PAP_{year}.csv")


def load_apt(year: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Monthly French-airport rows for one year, aggregates removed."""
    apt = _read_csv(data_dir / "apt" / f"ASP_APT_{year}.csv")
    return apt[~apt["APT"].isin(APT_AGGREGATES)]


def edge_table(year: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """One row per airport pair with annual totals.

    Pair codes are put in alphabetical order (u < v) so that the same route
    always has the same key, whatever order DGAC used.
    """
    pap = load_pap(year, data_dir)
    codes = pap["PAP"].str.split("_", expand=True)
    pap = pap.assign(
        u=codes.min(axis=1),
        v=codes.max(axis=1),
        # keep the labels aligned with u and v after reordering
        u_name=pap["PAP1_LABEL"].where(codes[0] <= codes[1], pap["PAP2_LABEL"]),
        v_name=pap["PAP2_LABEL"].where(codes[0] <= codes[1], pap["PAP1_LABEL"]),
    )
    edges = (
        pap.groupby(["u", "v"])
        .agg(
            u_name=("u_name", "first"),
            v_name=("v_name", "first"),
            passengers=("PAP_PAX", "sum"),
            flights=("PAP_MVT", "sum"),
            freight_t=("PAP_FRP", "sum"),
            distance_km=("PAP_DIST", "first"),
            months_active=("ANMOIS", "nunique"),
        )
        .reset_index()
    )
    return edges


def node_table(year: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Annual traffic of French airports from the APT series, indexed by ICAO."""
    apt = load_apt(year, data_dir)
    return apt.groupby("APT").agg(
        apt_name=("APT_NOM", "first"),
        apt_zone=("APT_ZON", "first"),
        apt_pax_dep=("APT_PAX_dep", "sum"),
        apt_pax_arr=("APT_PAX_arr", "sum"),
        apt_pax_transit=("APT_PAX_tr", "sum"),
        apt_movements=("APT_NMVT_mxt", "sum"),
    ).assign(
        apt_passengers=lambda d: d["apt_pax_dep"] + d["apt_pax_arr"] + d["apt_pax_transit"]
    )


def build_graph(year: int = 2025, data_dir: Path = DATA_DIR) -> nx.Graph:
    """Undirected, simple, weighted graph of published routes for one year.

    Edge weights: use ``weight="passengers"`` for strength-type measures
    (weighted degree, Louvain). For shortest-path measures (weighted
    betweenness, closeness, diameter) use ``weight="cost"`` (= 1/passengers),
    because NetworkX treats weights as distances: a busy route must be "short".
    """
    edges = edge_table(year, data_dir)
    apt = node_table(year, data_dir)

    G = nx.Graph(year=year, source="DGAC ASP_PAP / ASP_APT", weight="passengers")

    for row in edges.itertuples(index=False):
        G.add_edge(
            row.u,
            row.v,
            passengers=int(row.passengers),
            flights=int(row.flights),
            freight_t=float(row.freight_t),
            distance_km=int(row.distance_km),
            months_active=int(row.months_active),
            cost=1.0 / row.passengers if row.passengers > 0 else float("inf"),
        )
        G.nodes[row.u].setdefault("name", row.u_name)
        G.nodes[row.v].setdefault("name", row.v_name)

    for code, attrs in G.nodes(data=True):
        french = code in apt.index
        attrs["french"] = french
        attrs["icao_region"] = "France" if french else ICAO_REGIONS.get(code[0], "Other")
        if french:
            a = apt.loc[code]
            attrs["zone"] = "metro" if a["apt_zone"] == "MT" else "overseas"
            attrs["name"] = a["apt_name"]
            for col in ("apt_passengers", "apt_pax_dep", "apt_pax_arr",
                        "apt_pax_transit", "apt_movements"):
                attrs[col] = int(a[col])
        else:
            attrs["zone"] = "foreign"

    return G


def build_graphs(years=(2019, 2020, 2025), data_dir: Path = DATA_DIR) -> dict[int, nx.Graph]:
    """Graphs for several years, keyed by year (for the comparison over time)."""
    return {y: build_graph(y, data_dir) for y in years}


def summary(G: nx.Graph) -> dict:
    """Basic facts the report must state: size, type, connectivity."""
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    french = [n for n, f in G.nodes(data="french") if f]
    return {
        "year": G.graph.get("year"),
        "nodes": G.number_of_nodes(),
        "french_nodes": len(french),
        "foreign_nodes": G.number_of_nodes() - len(french),
        "edges": G.number_of_edges(),
        "directed": G.is_directed(),
        "multigraph": G.is_multigraph(),
        "connected": nx.is_connected(G),
        "components": len(comps),
        "component_sizes": [len(c) for c in comps],
        "total_passengers": sum(d for _, _, d in G.edges(data="passengers")),
    }


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or [2025]
    for y in years:
        print(summary(build_graph(y)))
