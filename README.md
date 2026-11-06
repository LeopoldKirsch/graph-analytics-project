# French Air Traffic Network — Graph Analytics Project

**How centralised is France's air connectivity on Paris-CDG, and how fragile does that make the network?**

Graph analytics course project, Albert School (2026).
Authors: Léopold Kirsch, Léa Chapoton

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
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/analysis.ipynb      # the whole analysis, in defence order (~2 min)
```

Each module can also be run on its own and writes its tables to `results/`:

```bash
python src/core_metrics.py          # size, connectivity, diameter/radius, articulation points
python src/centrality.py            # degree, strength, betweenness, harmonic, PageRank
python src/views.py                 # international vs domestic network
python src/null_model.py            # degree-preserving null model (500 random graphs, ~45 s)
python src/resilience.py 2019 2020 2025
python src/communities.py 2019 2020 2025
python src/comparison.py            # 2019 / 2020 / 2025
python src/filter_sensitivity.py    # passenger and seasonality thresholds
python src/figures.py               # report figures
python src/network_map.py           # maps
python src/time_series.py           # exploratory: 1990-2025
python src/passenger_metrics.py     # exploratory: two passenger-loss metrics
python src/bipartite_projection.py  # explored and rejected
```

Requires Python 3.11+. The results in `results/` were produced in a clean virtual environment from `requirements.txt` with Python 3.12, NetworkX 3.7, pandas 3.1, SciPy and Matplotlib 3.11. Randomised steps use fixed seeds (Louvain `seed=42`, random removals seeds 0-99, null model seed 42), so a rerun gives the same tables. Louvain's implementation can change between NetworkX versions: with an older NetworkX the main partition is the same, but stability scores and small communities can differ slightly. Figures can differ cosmetically (fonts) from one machine to another.

## Main results (2025)

- **Centralised on CDG**: 99 of 289 routes (2 of them cargo), 53 % of published passengers, betweenness 0.71 (Nice and Orly: 0.14); the centre of the network. 49 foreign destinations are reachable only through CDG.
- **International, not domestic**: on French airports only, CDG ranks 5th and Orly is the hub (betweenness centralisation 0.14 vs 0.70 for the full network), on a published domestic network that is very incomplete (see limits).
- **Explained by its number of routes**: in degree-preserving random graphs CDG gets the same betweenness (0.69, p = 0.36); the real network is more disassortative than chance (hub-and-spoke).
- **Robust yet fragile**: removing CDG leaves 60 % of the airports in the main component and 47 % of the passengers on surviving routes (CDG + Orly: 48 % and 25 %), against 96 % and 99 % for one random removal.
- **Communities follow markets**: a CDG international group, an Orly-Lyon group (domestic, overseas, Mediterranean), a Nice-regional group, Marseille-Corsica-Maghreb and French Polynesia (modularity 0.36).
- **Stable over time**: CDG's betweenness stays between 0.69 (1990) and 0.86 (2002) from 1990 to 2025, above 0.80 in 1998 and most years from 2000 to 2008; COVID raised it in 2020 (0.78), and 2025 is below 2019 (0.71 vs 0.74). Passengers are not fully back (73.6 M vs 78.4 M in 2019).
- **Limits**: DGAC publication rule (routes with fewer than 3 airlines missing, no foreign-foreign routes); incomplete domestic network (published routes cover 54 % of CDG's traffic, 46 % of Orly's, 21 % of Toulouse's and 17 % of Bordeaux's; only 40 domestic routes, Lyon-CDG, Marseille-Orly and Bordeaux-Orly missing); a few cargo routes with (almost) no passengers (Leipzig, Liège, Cologne, Dubai World Central) counted as routes; annual undirected graph; the main resilience curves use static attack orders (the adaptive betweenness attack in `resilience.py` is more damaging: 3 % of airports left in the main component after 10 removals vs 17 %).

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
| `feature/communities` | Léa | `src/communities.py`: Louvain weighted vs unweighted (`seed=42`), modularity, interpretation of clusters |
| `feature/resilience` | Léa | `src/resilience.py`: remove CDG, CDG + Orly, compared with random removals |
| `feature/year-comparison` | Léa | `src/comparison.py`: same metrics for 2019 / 2020 / 2025 |
| `feature/network-views` | Léopold | `src/views.py`: international vs domestic network (centrality, resilience, destinations reachable only via CDG) |
| `feature/null-model` | Léopold | `src/null_model.py`: degree-preserving null model (no foreign-foreign swaps) |
| `feature/filter-sensitivity` | Léopold | `src/filter_sensitivity.py`: results under passenger and seasonality thresholds |
| `feature/network-map` | Léopold | `src/network_map.py`: world map of the full network and map of French airports only, for the report and the defence |
| `feature/figures` | Léa | `src/figures.py`: network map, centrality chart, resilience chart, saved to `results/` |
| `explore/bipartite-projection` | Léopold | Option 2, tested and rejected: projection of French airports via shared foreign destinations |
| `explore/time-series` | Léa | Option 3: edges and nodes per year 1990-2025, with the 3-airline filter caveat |
| `explore/passenger-metrics` | Léopold | Exploratory: passengers lost under airport removal, two definitions side by side (`passengers_kept` = routes still flying, `passengers_connected` = routes in the largest component) |
| `docs/final-readme` | both | Final README and disclosures, after the code freeze |

## Disclosures

- **Code reuse**: No already existing code was reused in this project
- **AI tools**: Claude (Anthropic), through Claude Code, was used as a coding assistant: debugging reviewing analysis code, checking that results reproduce on a clean install, and drafting documentation and parts of the notebook commentary. Commits where it contributed carry a `Co-Authored-By: Claude` line. All numbers in the report come from the code in this repository.
