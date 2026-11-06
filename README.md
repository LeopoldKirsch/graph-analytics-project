# French Air Traffic Network — Graph Analytics Project

**How centralised is France's air connectivity on Paris-CDG, and how fragile does that make the network?**

Graph analytics course project, Albert School (2026).
Authors: Léopold Kirsch, [teammate name]

## Overview

We build a graph of France's commercial air connections from official tabular data published by the French civil aviation authority (DGAC), then analyse it with NetworkX:

- **Centrality**: which airports hold the network together, and how far behind CDG are Orly, Nice and Lyon?
- **Resilience**: what happens to connectivity when CDG, or CDG and Orly, are removed?
- **Communities**: do airports form natural groups beyond "Paris vs the rest"?
- **Comparison over time**: how did the structure change between 2019 (pre-COVID), 2020 (COVID) and 2025?

## Data

Source: [Trafic aérien commercial mensuel français](https://www.data.gouv.fr/datasets/trafic-aerien-commercial-mensuel-francais-par-paire-daeroports-par-sens-depuis-1990), DGAC, data.gouv.fr. Licence Ouverte / Open Licence 2.0.

| Series | Content | Use |
| --- | --- | --- |
| `ASP_PAP_<year>.csv` | Monthly traffic per airport pair (passengers, flights, freight, distance) | Edges |
| `ASP_APT_<year>.csv` | Monthly traffic per airport (departing/arriving passengers, zone) | Node attributes |
| `ASP_CIE_<year>.csv` | Monthly national traffic per airline (2010-2025, no airport field) | Context only |

External data, used only to draw maps (`src/network_map.py`):

| File | Source | Licence |
| --- | --- | --- |
| `data/external/airport_coords.csv` | Airport positions from [OurAirports](https://ourairports.com/data/), filtered to the 272 airports in the DGAC series; 6 closed airports or city codes placed by hand (column `source`) | Public domain |
| `data/external/ne_50m_countries.geojson` | Country outlines, [Natural Earth](https://www.naturalearthdata.com) 1:50m | Public domain |

Known limitation: the PAP series only publishes routes with at least 10,000 passenger-equivalents in the month, served by at least 3 airlines with none above 85% of the traffic (statistical confidentiality). Routes served by one or two airlines are therefore missing, and only flights touching France are covered.

## Graph model

- **Nodes**: airports (ICAO codes), French and foreign
- **Edges**: one undirected edge per airport pair with published traffic in the year (monthly rows summed)
- **Edge weight**: annual passengers; flights (aircraft movements), freight, distance and months active kept as attributes
- **Node attributes**: name, French/foreign, zone (metro / overseas / foreign), ICAO world region, and annual passengers and movements from APT for French airports
- **Graph type**: undirected, simple, weighted (the source combines both directions of a route in one row)

Weight convention: use `weight="passengers"` for strength-type measures (weighted degree, Louvain) and `weight="cost"` (= 1/passengers) for shortest-path measures (weighted betweenness, closeness), since NetworkX treats weights as distances.

## Repository structure

```
data/raw/pap/      DGAC airport-pair series, one CSV per year (1990-2025)
data/raw/apt/      DGAC airport series, one CSV per year (1990-2025)
data/raw/cie/      DGAC airline series, one CSV per year (2010-2025), context only
data/external/     airport coordinates and country outlines, for maps only
src/build_graph.py builds one graph per year (python src/build_graph.py 2019 2020 2025)
src/               graph building and analysis scripts
notebooks/         main analysis notebook
results/           figures and tables used in the report
requirements.txt   Python dependencies
```

## How to reproduce

```bash
pip install -r requirements.txt
jupyter notebook notebooks/analysis.ipynb
```

Requires Python 3.10+, pandas and NetworkX. Community detection uses Louvain (`networkx.community.louvain_communities`) with `seed=42` for reproducibility.

## Team workflow

**One branch per task, one pull request per branch, reviewed by the other teammate.**

1. Start from an up-to-date `main`:
   ```bash
   git switch main && git pull
   git switch <task-branch>        # or: git switch -c <type>/<name> for a new task
   git merge main                  # if the branch already exists, bring it up to date
   ```
2. Work in small commits with clear messages ("Add weighted betweenness", not "update").
3. Push and open a pull request into `main` on GitHub.
4. **Peer review**: the other teammate reviews before anything is merged. The reviewer:
   - runs the code from a clean checkout and checks it gives the same numbers;
   - checks the method matches what the report says (weights, parameters, `seed=42`, which component);
   - reads the interpretation and asks questions now, since the oral will ask them too.
5. The reviewer approves, the author merges and deletes the branch.

Rules:
- Nobody commits directly to `main`; `main` always runs end to end.
- Branch names: `feature/` for required analysis, `explore/` for the exploratory options, `fix/` and `docs/` otherwise.
- Load data only through `src/build_graph.py`; do not copy loading code into other files.
- Each task puts its code in its own module `src/<task>.py`. The notebook only calls these functions, which avoids merge conflicts in `.ipynb` files. Only the owner of `feature/analysis-notebook` edits `notebooks/analysis.ipynb`.
- Figures and tables for the report go in `results/`, named after the task (e.g. `results/resilience_components.png`).
- Code freeze: **6 November, evening**. After that, only `fix/` and `docs/` branches.

### Tasks and branches

| Branch | Owner | Deliverable |
| --- | --- | --- |
| `feature/core-metrics` | Léopold | `src/core_metrics.py`: nodes and edges, graph type, connectivity and components, diameter and radius on the largest component |
| `feature/centrality` | Léopold | `src/centrality.py`: degree, weighted degree, betweenness, PageRank or closeness; CDG vs Orly / Nice / Lyon table |
| `feature/analysis-notebook` | Léopold | `notebooks/analysis.ipynb` calling every module, in report order |
| `feature/communities` | [teammate] | `src/communities.py`: Louvain weighted vs unweighted (`seed=42`), modularity, interpretation of clusters |
| `feature/resilience` | [teammate] | `src/resilience.py`: remove CDG, CDG + Orly, compared with random removals |
| `feature/year-comparison` | [teammate] | `src/comparison.py`: same metrics for 2019 / 2020 / 2025 |
| `feature/network-map` | Léopold | `src/network_map.py`: world map of the full network and map of French airports only, for the report and the defence |
| `feature/figures` | [teammate] | `src/figures.py`: network map, centrality chart, resilience chart, saved to `results/` |
| `explore/bipartite-projection` | Léopold | Option 2, tested and rejected: projection of French airports via shared foreign destinations |
| `explore/time-series` | [teammate] | Option 3: edges and nodes per year 1990-2025, with the 3-airline filter caveat |
| `explore/passenger-metrics` | Léopold | Exploratory: passengers lost under airport removal, two definitions side by side (`passengers_kept` = routes still flying, `passengers_connected` = routes in the largest component) |
| `docs/final-readme` | both | Final README and disclosures, after the code freeze |

## Disclosures

- **Code reuse**: [state whether any existing code for this dataset was reused, and cite it]
- **AI tools**: [state whether AI tools were used and for what purpose]
