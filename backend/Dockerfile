# Optional: host the backend so the Android app (or a remote desktop) can
# reach it without keeping a PC on. Starting point — tune for your host.
FROM python:3.11-slim

WORKDIR /app

# Build deps for any packages without prebuilt wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system .

EXPOSE 8000

# Provide your model API key at runtime, e.g. -e OPENROUTER_API_KEY=...
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
