# QVM Manufacturing Dashboard

A Streamlit dashboard for analyzing PCB Quality Vision Machine (QVM) text logs:
it parses registration measurements, flags alignment errors, tool wear and
lamination distortion, and exports Excel workbooks with embedded charts.

> Built by Prince Khurana — process/quality engineering tooling in Python.

## Screenshots

Example outputs (synthetic data — the app renders interactive Plotly versions
of the same charts):

![SC distribution box plot](qvm_dashboard/assets/screenshots/box-plot.png)
![Registration bullseye](qvm_dashboard/assets/screenshots/bullseye.png)
![Per-site SC bars](qvm_dashboard/assets/screenshots/site-bars.png)

## Features

- Parses three machine formats: Pad-to-Via, Via-to-Pad, and Core Shrinkage logs
- Unified parser: content-based format detection, geometry-resolved site identity
- Interactive charts: bullseye DX/DY scatter, SC box plot by quarter, per-site
  bars, distortion/quiver map, shrinkage panels
- Quality Control table + one-click Excel export with embedded charts
- Config-driven tolerances and limits (`qvm_dashboard/config/settings.yaml`)
- Runs locally or in Docker (non-root, includes browser for chart export)

## Quick start

Requires Python 3.10+.

```bash
pip install -r qvm_dashboard/requirements.txt
cd qvm_dashboard && streamlit run app.py
```

Open `http://localhost:8501`, then upload a sample log to see it working:

- `qvm_dashboard/sample_data/C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt`

Or with Docker (no local Python needed):

```bash
docker build -t qvm-dashboard .
docker run --rm -p 8501:8501 qvm-dashboard
```

## Tech stack

Python, Streamlit, Plotly, pandas, NumPy, openpyxl, kaleido, PyYAML — pytest
for tests, Docker for deployment.

## Project layout

```text
QVM/
├── Dockerfile                    # runnable without local Python
├── pyproject.toml                # pytest configuration
└── qvm_dashboard/
    ├── app.py                    # entry point
    ├── README.md                 # full docs: formats, views, config, columns
    ├── ARCHITECTURE.md           # module graph, data flow, where-to-change-what
    ├── SHRINKAGE_METHODS.md      # method comparison and rationale
    ├── config/settings.yaml      # tolerances, limits, mappings
    ├── sample_data/              # example logs to try
    └── tests/                    # pytest suite
```

Full documentation: [qvm_dashboard/README.md](qvm_dashboard/README.md) |
[ARCHITECTURE.md](qvm_dashboard/ARCHITECTURE.md) |
[SHRINKAGE_METHODS.md](qvm_dashboard/SHRINKAGE_METHODS.md)

## Tests

```bash
.venv/bin/pytest -q
```

## Limitations / roadmap

- Chart PNG export needs a local Chrome via kaleido; without it, workbooks
  fall back to placeholder graphics.
- Sample data is synthetic; validated against real machine-log shapes only.

## License

MIT — see [LICENSE](LICENSE).
