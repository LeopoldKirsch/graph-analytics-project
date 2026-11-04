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

Known limitation: the PAP series only publishes routes with at least 10,000 passenger-equivalents in the month, served by at least 3 airlines with none above 85% of the traffic (statistical confidentiality). Routes served by one or two airlines are therefore missing, and only flights touching France are covered.

## Graph model

- **Nodes**: airports (ICAO codes), French and foreign
- **Edges**: one undirected edge per airport pair with published traffic in the year (monthly rows summed)
- **Edge weight**: annual passengers; flights and distance kept as attributes
- **Graph type**: undirected, simple, weighted (the source combines both directions of a route in one row)

## Repository structure

```
data/raw/pap/      DGAC airport-pair series, one CSV per year (1990-2025)
data/raw/apt/      DGAC airport series, one CSV per year (1990-2025)
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

## Disclosures

- **Code reuse**: [state whether any existing code for this dataset was reused, and cite it]
- **AI tools**: [state whether AI tools were used and for what purpose]
