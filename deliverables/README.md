# Beyond Interoperability — Workshop Materials

Everything you need for the workshop: the slides and the hands-on notebooks.

## Contents

- `report/Beyond_Interoperability_Slides.pptx` — the workshop slides
- `notebooks/` — run these in order, `00` through `07`
- `src/fedconformal/` — the toolkit the notebooks import (no install needed)
- `data/` — the four site data files the notebooks load
- `scripts/compare_prediction_tasks.py` — used by notebook `07`

## Setup

```bash
pip install -r requirements.txt
jupyter notebook notebooks/
```

Each notebook is self-contained: run its cells top to bottom. The first
code cell in every notebook adds `../src` to the Python path, so no
package installation is required — just keep this folder's structure
intact (`notebooks/`, `src/`, and `data/` as siblings).
