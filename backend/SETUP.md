# Multi-Modal RAG Backend Setup Guide

## Section 1: Project Overview

This is the backend system for a Multi-Modal Retrieval-Augmented Generation (RAG) search application. It integrates text, images, and other formats to provide accurate, source-backed answers to user queries.

**Model Information:**
- **Model:** Mistral-7B-Instruct-v0.2
- **Format:** GGUF Q4_K_M quantization
- **Size:** ~4.4GB

**Key Components:**
- **Data Ingestion:** Processing varied document formats (PDFs, images, etc.).
- **Vector Indexing:** Utilizing FAISS or HNSW for high-performance similarity search.
- **Cache System:** A 3-tier caching mechanism to reduce latency and API usage.
- **Conversation History:** Retaining context across multi-turn interactions.
- **Cross-Encoder Reranking:** Reordering retrieved documents to improve relevance.
- **Validation & Fact-Checking:** Ensuring the generated output strictly relies on retrieved documents.
- **LLM Generation:** Mistral-based text synthesis via local execution (llama.cpp).

## Section 2: Prerequisites

Before setting up the project, ensure your system meets the following requirements:
- Python 3.11+
- Docker (if using Docker deployment)
- ~10GB free disk space (minimum, for the model + dependencies + data)
- 8GB+ RAM recommended (more is beneficial for local LLM inference)

## Section 3: Local Development Setup (without Docker)

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd multi_model_rag_for_searching/backend
   ```

2. **Create a virtual environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration values
   ```

5. **Download the model:**
   Run the download script to fetch the Mistral-7B GGUF file:
   ```bash
   python download_model.py
   ```

6. **Run the server:**
   You can start the server using the custom entry script:
   ```bash
   python main.py bot
   # or
   python main.py fsearch
   ```
   Alternatively, run it directly with Uvicorn:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Section 4: Docker Setup

*(Assuming Docker is already installed)*

1. **Build the image:**
   ```bash
   docker build -t rag-backend .
   ```

2. **Download the model locally first:**
   The model is excluded from the Docker build to keep the image lightweight. Download it to the host machine first:
   ```bash
   python download_model.py
   ```

3. **Run with model volume mount:**
   Map port 8000, attach the `models` directory, and pass the `.env` file:
   ```bash
   docker run -d --name rag_api \
     -p 8000:8000 \
     -v $(pwd)/models:/app/models \
     -v $(pwd)/.env:/app/.env \
     rag-backend
   ```

4. **Verify the deployment:**
   Check if the API is responsive:
   ```bash
   curl http://localhost:8000/docs
   ```

5. **Docker Compose (Optional):**
   You can also manage the setup via `docker-compose.yml`:
   ```yaml
   version: '3.8'
   services:
     api:
       build: .
       ports:
         - "8000:8000"
       volumes:
         - ./models:/app/models
         - ./.env:/app/.env
       environment:
         - PYTHONUNBUFFERED=1
   ```
   Run with: `docker-compose up -d`

## Section 5: Environment Variables

Configure these values in your `.env` file (see `settings.py` for defaults):

- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host address
- `DB_PORT`: Database port
- `JWT_SECRET_KEY`: Secret key for JWT signing
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access tokens
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`: Expiration time for refresh tokens
- `JWT_ALGORITHM`: Algorithm used for JWT (e.g., HS256)

## Section 6: Running Tests

The test suite relies on `pytest`.

- **Run all tests:**
  ```bash
  pytest test/ -v
  ```

- **Run project-specific tests (integration, stress):**
  ```bash
  pytest test/project_testing/ -v
  ```

## Section 7: Running Benchmarks

Performance profiling and benchmarking tools.

- **Run all benchmarks:**
  ```bash
  pytest bench_marking/ -v -s
  ```

## Section 8: API Endpoints

A quick overview of key REST endpoints exposed by the service:

- `POST /auth/register/` - Register a new user
- `POST /auth/login/` - Login and receive JWT tokens
- `POST /auth/refresh/` - Refresh an expired access token
- `POST /upload` - Upload documents/files for ingestion into the RAG system
- `POST /query` - Query the RAG system and receive a generated answer

## Section 9: Troubleshooting

- **Server crashes on startup with MemoryError:**
  Ensure your machine has at least 8GB of free RAM. Close other memory-intensive applications.
- **Model not found:**
  Make sure you ran `python download_model.py` and the GGUF file is physically present in the `models/` directory before starting the app (or mapping the volume in Docker).
- **llama.cpp build failures during pip install:**
  Ensure you have `build-essential` and `cmake` installed on your host system.
- **No response from Docker container:**
  Check the container logs: `docker logs rag_api`. Verify that the `.env` file is properly mounted and contains the required database credentials.
