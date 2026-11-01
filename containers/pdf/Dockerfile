FROM python:3.15-slim-bookworm@sha256:4e03260adeeebafccd084f3584e6b84823aba5651cfb53ef8a078ed441ddf9cd
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libgl1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.5
WORKDIR /opt/pdf
COPY containers/pdf/pyproject.toml containers/pdf/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src/eil /app/backend/src/eil
COPY containers/pdf/worker.py /app/worker.py
ENV PYTHONPATH=/app/backend/src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    HF_HOME=/tmp/huggingface HOME=/tmp PYTHONDONTWRITEBYTECODE=1 \
    EIL_DOCLING_ARTIFACTS=/models OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
USER 65532:65532
LABEL eil.purpose="isolated-pdf-worker-v1"
ENTRYPOINT ["timeout", "--signal=KILL", "110", "/opt/pdf/.venv/bin/python", "/app/worker.py"]
