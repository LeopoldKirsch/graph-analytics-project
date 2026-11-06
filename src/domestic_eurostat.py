"""Exploratory: completing the domestic network with Eurostat route data.

Problem: the DGAC airport-pair series only publishes a route-month with at
least 3 airlines and none above 85 % of the traffic. Most French domestic
routes are run by a single airline, so the published domestic network is
very incomplete (about 40 routes; Lyon-CDG, Toulouse-CDG or Marseille-Orly
are missing).

Second source: Eurostat, "Air passenger transport routes between partner
airports and main airports in France" (dataset avia_par_fr, passengers
carried, annual). Eurostat publishes every route of the main airports
(airports above 150,000 passengers a year report to Eurostat), without the
3-airline rule. Limits: annual data stop at 2024 (no 2025 yet), and routes
between two small non-reporting airports are not covered.

Method:
- Domestic routes = pairs of French airports (metro and overseas) with
  passengers > 0. Each route is reported by both of its airports when both
  report: the two reports are averaged (they agree closely); a route
  reported by one airport only keeps that report. Aggregate codes (e.g.
  "LF90", other airports) are dropped.
- The same measures are computed on the Eurostat domestic graph and on the
  DGAC published domestic graph of the same year (2019, 2020, 2024):
  size, passengers, betweenness centralisation, top airports by
  betweenness / routes / passengers, and the share of domestic passengers
  kept in the largest component when CDG or Orly is removed.

Question: do the domestic conclusions drawn from the DGAC data (Orly is the
domestic hub, the domestic network is not centralised) survive once the
hidden routes are added back?

Data: data/external/eurostat_domestic_routes.csv, extracted from the
Eurostat API by fetch() (source: Eurostat, avia_par_fr, CC BY 4.0).

Usage:
    python src/domestic_eurostat.py            # 2019, 2020, 2024 -> results/domestic_eurostat_*
    python src/domestic_eurostat.py --fetch    # re-download the Eurostat extract first
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from build_graph import build_graph, node_table
from views import domestic_graph

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
DATA_FILE = ROOT / "data" / "external" / "eurostat_domestic_routes.csv"
YEARS = (2019, 2020, 2024)
CDG, ORLY = "LFPG", "LFPO"
API = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/avia_par_fr"
       "?format=JSON&lang=EN&freq=A&unit=PAS&tra_meas=PAS_CRD")
COLORS = {"Eurostat (all routes)": "#2a78d6", "DGAC (published routes)": "#eb6834"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def fetch(years=YEARS, path: Path = DATA_FILE) -> pd.DataFrame:
    """Download the French domestic routes from the Eurostat API and save them."""
    url = API + "".join(f"&time={y}" for y in years)
    with urllib.request.urlopen(url, timeout=180) as r:
        d = json.load(r)
    pairs = {i: p for p, i in d["dimension"]["airp_pr"]["category"]["index"].items()}
    times = {i: t for t, i in d["dimension"]["time"]["category"]["index"].items()}
    nt = d["size"][-1]
    rows = []
    for k, v in d["value"].items():
        p, t = pairs[int(k) // nt], times[int(k) % nt]
        m = re.fullmatch(r"FR_([A-Z]{4})_FR_([A-Z]{4})", p)  # drops aggregates such as LF90
        if m and v:
            rows.append({"year": int(t), "reporting": m[1], "partner": m[2], "passengers": int(v)})
    df = pd.DataFrame(rows).sort_values(["year", "reporting", "partner"], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def routes(year: int, path: Path = DATA_FILE) -> pd.DataFrame:
    """One row per undirected domestic route: mean of the available reports."""
    raw = pd.read_csv(path)
    raw = raw[raw["year"] == year].copy()
    raw["a"] = raw[["reporting", "partner"]].min(axis=1)
    raw["b"] = raw[["reporting", "partner"]].max(axis=1)
    return (raw.groupby(["a", "b"])["passengers"]
            .agg(passengers="mean", reports="count").reset_index())


def eurostat_graph(year: int) -> nx.Graph:
    names = node_table(year)["apt_name"].to_dict()
    E = nx.Graph(year=year, source="Eurostat")
    for r in routes(year).itertuples():
        E.add_edge(r.a, r.b, passengers=float(r.passengers))
    for n in E:
        E.nodes[n]["name"] = names.get(n, n)
    return E


def dgac_graph(year: int) -> nx.Graph:
    D = domestic_graph(build_graph(year))
    D.remove_nodes_from(list(nx.isolates(D)))  # airports with only international routes
    return D


def _kept_without(H: nx.Graph, removed: list[str]) -> float:
    """Share of domestic passengers on routes in the largest component after removal."""
    total = sum(p for *_, p in H.edges(data="passengers"))
    K = H.copy()
    K.remove_nodes_from(removed)
    if K.number_of_nodes() == 0:
        return 0.0
    lcc = K.subgraph(max(nx.connected_components(K), key=len))
    return sum(p for *_, p in lcc.edges(data="passengers")) / total


def _top(scores: dict, k: int = 4, fmt="{:.2f}") -> str:
    best = sorted(scores, key=lambda n: (-scores[n], n))[:k]
    return ", ".join(f"{n} {fmt.format(scores[n])}" for n in best)


def describe(H: nx.Graph, label: str) -> dict:
    bc = nx.betweenness_centrality(H)  # unweighted hops
    bmax = max(bc.values())
    strength = dict(H.degree(weight="passengers"))
    degree = dict(H.degree())
    rank = sorted(H, key=lambda n: (-bc[n], n))
    return {
        "year": H.graph["year"], "source": label,
        "airports": H.number_of_nodes(), "routes": H.number_of_edges(),
        "passengers_m": sum(p for *_, p in H.edges(data="passengers")) / 1e6,
        "components": nx.number_connected_components(H),
        # rounded: the last float digits depend on node order (set order of subgraph())
        "betweenness_centralization": round(sum(bmax - b for b in bc.values()) / (len(H) - 1), 12),
        "top_betweenness": _top(bc),
        "top_routes": _top(degree, fmt="{:d}"),
        "top_passengers_m": _top({n: s / 1e6 for n, s in strength.items()}, fmt="{:.1f}"),
        "cdg_routes": degree.get(CDG, 0), "orly_routes": degree.get(ORLY, 0),
        "cdg_betweenness_rank": rank.index(CDG) + 1 if CDG in H else None,
        "orly_betweenness_rank": rank.index(ORLY) + 1 if ORLY in H else None,
        "cdg_passengers_m": strength.get(CDG, 0) / 1e6,
        "orly_passengers_m": strength.get(ORLY, 0) / 1e6,
        "kept_without_cdg": _kept_without(H, [CDG]),
        "kept_without_orly": _kept_without(H, [ORLY]),
    }


def hidden_routes(E: nx.Graph, D: nx.Graph) -> pd.DataFrame:
    """Eurostat routes absent from the DGAC published domestic network."""
    pub = {frozenset(e) for e in D.edges()}
    rows = [{"a": u, "b": v, "route": f"{E.nodes[u]['name']} - {E.nodes[v]['name']}",
             "passengers": p}
            for u, v, p in E.edges(data="passengers") if frozenset((u, v)) not in pub]
    return pd.DataFrame(rows).sort_values("passengers", ascending=False, ignore_index=True)


def compare(year: int) -> tuple[pd.DataFrame, pd.DataFrame, nx.Graph, nx.Graph]:
    E, D = eurostat_graph(year), dgac_graph(year)
    summary = pd.DataFrame([describe(E, "Eurostat (all routes)"),
                            describe(D, "DGAC (published routes)")])
    hidden = hidden_routes(E, D).assign(year=year)
    return summary, hidden, E, D


def plot(E: nx.Graph, D: nx.Graph, path: Path, top: int = 12) -> None:
    """Domestic passengers per airport, Eurostat vs DGAC (top airports)."""
    sE = dict(E.degree(weight="passengers"))
    sD = dict(D.degree(weight="passengers"))
    order = sorted(sE, key=lambda n: (-sE[n], n))[:top][::-1]
    labels = [E.nodes[n]["name"].title() for n in order]
    y = range(len(order))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    h = 0.38
    ax.barh([i + h / 2 for i in y], [sE[n] / 1e6 for n in order], height=h,
            color=COLORS["Eurostat (all routes)"], label="Eurostat (all routes)")
    ax.barh([i - h / 2 for i in y], [sD.get(n, 0) / 1e6 for n in order], height=h,
            color=COLORS["DGAC (published routes)"], label="DGAC (published routes)")
    ax.set_yticks(list(y), labels, fontsize=8.5, color=INK)
    ax.set_xlabel("Domestic passengers (millions)", fontsize=8.5, color=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#d6d5d0")
    ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=INK)
    ax.set_title(f"Domestic passengers per airport, {E.graph['year']}: "
                 "all routes (Eurostat) vs published routes (DGAC)",
                 loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def run(years=YEARS) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts = [compare(y) for y in years]
    if years:
        _, _, E, D = parts[-1]
        RESULTS_DIR.mkdir(exist_ok=True)
        plot(E, D, RESULTS_DIR / f"domestic_eurostat_{years[-1]}.png")
    return (pd.concat([p[0] for p in parts], ignore_index=True),
            pd.concat([p[1] for p in parts], ignore_index=True))


if __name__ == "__main__":
    if "--fetch" in sys.argv or not DATA_FILE.exists():
        df = fetch()
        print(f"Saved {len(df)} rows to {DATA_FILE.relative_to(ROOT)}")
    summary, hidden = run()
    RESULTS_DIR.mkdir(exist_ok=True)
    summary.to_csv(RESULTS_DIR / "domestic_eurostat_summary.csv", index=False)
    hidden.to_csv(RESULTS_DIR / "domestic_eurostat_hidden_routes.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 60)
    print(summary.round(3).T.to_string())
    print("\nBiggest hidden routes, last year:")
    last = hidden[hidden["year"] == hidden["year"].max()]
    print(last.head(12)[["route", "passengers"]].round(0).to_string(index=False))
    print("\nSaved results/domestic_eurostat_summary.csv, _hidden_routes.csv and .png")
