# QVM Manufacturing Dashboard — runnable without a local Python setup.
# Build:  docker build -t qvm-dashboard .
# Run:    docker run --rm -p 8501:8501 qvm-dashboard
# Then open http://localhost:8501
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Chart embedding renders Plotly figures to PNG via kaleido, which needs a
# real browser binary: the libraries below let it launch, and `chromium`
# provides it (kaleido discovers `chromium` on PATH). Without the browser,
# every exported workbook silently degrades to placeholder graphics.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
 && rm -rf /var/lib/apt/lists/*

COPY qvm_dashboard/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY qvm_dashboard/ ./qvm_dashboard/
COPY pyproject.toml ./pyproject.toml

# Run as non-root: restricted pod-security policies (runAsNonRoot) refuse
# root containers, and a Streamlit/file-write flaw must not yield root.
# The user owns /app and gets a writable HOME so Streamlit and
# kaleido-Chrome first-run caches keep working, including under
# read-only root filesystems (with /tmp + $HOME/.cache mounted).
RUN useradd -m appuser && chown -R appuser:appuser /app
ENV HOME=/home/appuser
USER appuser

WORKDIR /app/qvm_dashboard
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
