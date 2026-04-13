# QVM Manufacturing Dashboard

A modular, highly scalable Streamlit application for analyzing Quality Vision Machine (QVM) text logs for PCB Registration Alignment.

## Architecture

This application is built with a strict separation of concerns to ensure testability and scalability:

*   **`app.py`**: Contains *only* the Streamlit UI presentation logic.
*   **`src/parser.py`**: Contains robust regex logic for extracting text blocks and metadata from filenames.
*   **`src/calculations.py`**: Houses mathematical formulas like Annular Ring computation and CAM scaling.
*   **`src/visuals.py`**: Isolates Plotly chart rendering.
*   **`config/settings.yaml`**: The single source of truth for all column names, labels, thresholds, and machine quadrant mappings. No hardcoding exists in the Python source code.

## Configuration & Mappings

The QVM text format outputs locations like `UL_1` (Upper Left) or `LR_4` (Lower Right). For heatmap and vector generation, these strings are mapped to a matrix grid index.

If the factory quadrant labeling changes, simply update the `GRID_MAPPING` block in `config/settings.yaml`:

```yaml
GRID_MAPPING:
  # 1st Quadrant: Upper Left (UL)
  UL_1: 11
  # ...
  # 3rd Quadrant: Lower Right (LR)
  LR_1: 31
  # ...
```

## Running the Application

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch Streamlit:
   ```bash
   streamlit run app.py
   ```

## Running Tests

Unit tests are written in `pytest` to ensure mathematical logic and regex stability.
```bash
PYTHONPATH=. pytest tests/
```
