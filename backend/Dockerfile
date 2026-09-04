# syntax=docker/dockerfile:1
#
# Multi-stage build for the RAG backend.
#
#   Stage 1 (cpp-builder)  compiles llm_backend against a pinned llama.cpp
#   Stage 2 (runtime)      Python service + the compiled worker, no toolchain
#
# Build:
#   docker build -t rag-backend backend/
#
# The GGUF model is intentionally NOT baked into the image (it is 1.6-4.4 GB).
# Mount it at run time:
#   docker run -d --name rag_api -p 8000:8000 \
#     -v "$PWD/backend/models:/app/models" \
#     -v "$PWD/backend/.env:/app/.env:ro" \
#     rag-backend
#
# GPU: build with --build-arg GGML_CUDA=ON and run with --gpus all, using a
# CUDA base image for the runtime stage. See BACKEND.md.

# ---------------------------------------------------------------------------
# Stage 1: build the C++ worker
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS cpp-builder

ARG LLAMA_CPP_REF=b8057
ARG GGML_CUDA=OFF

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Pinned so an upstream change cannot silently alter the ABI the worker links
# against. Shallow clone: we only need one revision.
RUN git clone --depth 1 --branch "${LLAMA_CPP_REF}" \
      https://github.com/ggml-org/llama.cpp.git third_party/llama.cpp

COPY llm_backend/ ./llm_backend/

RUN cmake -S llm_backend -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_CUDA=${GGML_CUDA} \
      -DLLM_BACKEND_BUILD_TESTS=ON \
 && cmake --build build -j "$(nproc)" \
 && ctest --test-dir build --output-on-failure \
 && mkdir -p /out/lib \
 && cp build/llm_backend /out/ \
 && find build -name '*.so*' -exec cp -a {} /out/lib/ \;

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# tesseract: OCR for image ingestion
# ffmpeg:    audio decoding for Whisper transcription
# libgomp1:  OpenMP runtime that the compiled worker links against
# curl:      HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng \
      libgl1-mesa-glx libglib2.0-0 libgomp1 \
      ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements first so the (slow) dependency layer caches independently of
# application code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The compiled worker goes where Config.BIN_PATH looks for it.
COPY --from=cpp-builder /out/llm_backend /app/bin/llm_backend
COPY --from=cpp-builder /out/lib/ /app/third_party/llama.cpp/build/bin/

RUN mkdir -p models data/index data/users logs \
 && chmod +x /app/bin/llm_backend

# Run as a non-root user; mounted volumes must be writable by uid 1000.
RUN useradd --create-home --uid 1000 raguser \
 && chown -R raguser:raguser /app
USER raguser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HF_HUB_OFFLINE=1 \
    LD_LIBRARY_PATH=/app/third_party/llama.cpp/build/bin

EXPOSE 8000

# /docs is served by FastAPI once the app object is up. start-period covers
# model loading, which dominates startup.
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
  CMD curl -fsS http://localhost:8000/docs || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
