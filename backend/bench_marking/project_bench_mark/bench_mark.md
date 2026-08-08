# RAG Backend — Real-Data Benchmark Report

> Generated: 2026-08-08 09:44:48
> Model: `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` (mistral-7b-instruct-v0.2.Q4_K_M.gguf)
> Quantisation: Q4_K_M  |  ANN_TOP_K: 10  |  MIN_RELEVANCE: 0.25

## 1. Normal Tests

| # | Test | Status | Detail |
|---|------|--------|--------|
| 1 | Config.GENERATION_MODEL contains Mistral-7B | ✅ PASS | TheBloke/Mistral-7B-Instruct-v0.2-GGUF |
| 2 | Config.DEFAULT_MODEL == GENERATION_MODEL | ✅ PASS |  |
| 3 | Config.EMBED_MODEL_NAME set | ✅ PASS | sentence-transformers/all-MiniLM-L6-v2 |
| 4 | Config.RERANKER_MODEL set | ✅ PASS | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| 5 | Config.ANN_TOP_K >= 5 | ✅ PASS | 10 |
| 6 | Model GGUF file exists on disk | ✅ PASS | /home/ajay/Documents/multi_model_rag_for_searching/backend/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf |
| 7 | Model file > 3 GB | ✅ PASS | 4.07 GB |
| 8 | LlamaGenerator class importable | ✅ PASS |  |
| 9 | MmapGenerator class importable | ✅ PASS |  |
| 10 | AnswerGenerator alias importable | ✅ PASS |  |
| 11 | GenerationResult dataclass works | ✅ PASS |  |
| 12 | Citation dataclass works | ✅ PASS |  |
| 13 | _clean_response strips References: | ✅ PASS |  |
| 14 | _clean_response strips URLs | ✅ PASS |  |
| 15 | _is_refusal True for refusal text | ✅ PASS |  |
| 16 | _is_refusal False for normal text | ✅ PASS |  |
| 17 | _extract_cited_indices parses [1][3] | ✅ PASS |  |
| 18 | download_model.py importable | ✅ PASS |  |

**Result: 18/18 passed**

## 2. Stress Tests (Real Data)

| Test | Time (s) | Status |
|------|----------|--------|
| Embed 100 real chunks | 1.5135 | ✅ PASS |
| 20 rapid retrievals | 4.6474 | ✅ PASS |
| _clean_response 50 KB | 0.0010 | ✅ PASS |
| 100K _is_refusal | 0.0384 | ✅ PASS |

## 3. Subsystem Toggle Ablation (Real Pipeline)

| Configuration | Latency (s) | NDCG | Precision@5 | Chunks Retrieved |
|---------------|-------------|------|-------------|-----------------|
| Full Pipeline (C+H+R+V) | 0.016 | 1.00 | 1.00 | 4 |
| Cache Disabled (H+R+V) | 0.022 | 1.00 | 1.00 | 4 |
| History Disabled (C+R+V) | 0.029 | 1.00 | 1.00 | 2 |
| Reranker Disabled (C+H+V) | 0.018 | 1.00 | 1.00 | 2 |
| Validator Disabled (C+H+R) | 0.048 | 0.98 | 0.67 | 3 |
| Cache+History Off (R+V) | 0.024 | 1.00 | 1.00 | 4 |
| Minimal Pipeline (None) | 4.491 | 1.00 | 1.00 | 4 |

## 4. Citation Accuracy (Real LLM Generation)

| Query | Gen Time (s) | Citations | Provided Chunks | Precision | Recall | F1 |
|-------|-------------|-----------|-----------------|-----------|--------|-----|
| What is Breast cancer Source: [URL] Introduction B... | 26.8 | 1 | 4 | 1.00 | 1.00 | 1.00 |
| What is Breast cancer most commonly develops in?... | 25.5 | 1 | 5 | 1.00 | 1.00 | 1.00 |
| What is Breast cancer screening can be instrumenta... | 29.9 | 1 | 1 | 1.00 | 1.00 | 1.00 |
| **Average** | **27.4** | — | — | **1.00** | **1.00** | **1.00** |

## 5. RAM & Resource Profiling

| Metric | Value |
|--------|-------|
| RSS before model load | 897 MB |
| RSS after model load | 8327 MB |
| RSS after all benchmarks | 7052 MB |
| Model load overhead | 7430 MB |
| Pipeline init time | 8.1 s |

## 6. Long Context Stress Test (Organic Data)

| Chunks | ~Tokens | Gen Time (s) | RAM Δ (MB) | Status | Sample Output |
|--------|---------|-------------|-----------|--------|---------------|
| 5 | 149 | 60.3 | 6 | ✅ PASS | Breast cancer is a type of cancer that originates from breast tissue [1]. Signs and symptoms of brea... |
| 10 | 245 | 56.3 | -216 | ✅ PASS | Breast cancer is a type of cancer that originates from breast tissue [1]. Signs and symptoms of brea... |
| 25 | 553 | 84.9 | -344 | ✅ PASS | Breast cancer is a type of cancer that originates from breast tissue [1]. Signs and symptoms of brea... |

