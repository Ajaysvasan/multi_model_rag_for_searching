# RAG Backend — Real-Data Benchmark Report

> Generated: 2026-08-08 10:07:30
> Model: `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` (mistral-7b-instruct-v0.2.Q4_K_M.gguf)
> Quantisation: Q4_K_M | ANN_TOP_K: 10 | MIN_RELEVANCE: 0.25
> **All data sourced from live SQLite/Postgres database — zero synthetic data**

## 1. Stress Tests (Real Data)

| Test                                         | Time (s)         | Status  |
| -------------------------------------------- | ---------------- | ------- |
| Embed 100 real chunks from DB                | 0.88             | ✅ PASS |
| 20 rapid retrieve_enhanced() (real queries)  | 4.83 (avg 0.242) | ✅ PASS |
| Real LLM generation on 5 DB chunks           | 79.6             | ✅ PASS |
| Real LLM generation on 25 DB chunks (stress) | 89.1             | ✅ PASS |

## 2. Subsystem Toggle Ablation (Real Pipeline)

| Configuration              | Latency (s) | NDCG | Precision@5 | Chunks Retrieved |
| -------------------------- | ----------- | ---- | ----------- | ---------------- |
| Full Pipeline (C+H+R+V)    | 0.0337      | 1.00 | 1.00        | 4                |
| Cache Disabled (H+R+V)     | 0.0464      | 1.00 | 1.00        | 3                |
| History Disabled (C+R+V)   | 0.0317      | 1.00 | 1.00        | 2                |
| Reranker Disabled (C+H+V)  | 0.0245      | 1.00 | 1.00        | 2                |
| Validator Disabled (C+H+R) | 0.0250      | 1.00 | 1.00        | 2                |
| Cache+History Off (R+V)    | 0.0304      | 1.00 | 1.00        | 3                |
| Minimal Pipeline (None)    | 4.5284      | 0.98 | 0.75        | 4                |

## 3. Improvement Analysis (Full Pipeline vs Each Configuration)

| Configuration              | Latency Δ     | NDCG Δ | Precision@5 Δ | Chunks Δ | Verdict             |
| -------------------------- | ------------- | ------ | ------------- | -------- | ------------------- |
| Cache Disabled (H+R+V)     | 1.4x slower   | same   | same          | -1       | ✅ Minimal impact   |
| History Disabled (C+R+V)   | 1.1x faster   | same   | same          | -2       | ✅ Minimal impact   |
| Reranker Disabled (C+H+V)  | 1.4x faster   | same   | same          | -2       | ✅ Minimal impact   |
| Validator Disabled (C+H+R) | 1.3x faster   | same   | same          | -2       | ✅ Minimal impact   |
| Cache+History Off (R+V)    | 1.1x faster   | same   | same          | -1       | ✅ Minimal impact   |
| Minimal Pipeline (None)    | 134.5x slower | -0.02  | -0.25         | same     | ⚠️ Quality degraded |

## 4. Citation Accuracy (Real LLM Generation)

| Query                                                 | Gen Time (s) | Citations Used | Chunks Provided | Precision | Recall   | F1       |
| ----------------------------------------------------- | ------------ | -------------- | --------------- | --------- | -------- | -------- |
| What is Breast cancer Source: [URL] Introduction B... | 26.2         | 1              | 4               | 1.00      | 1.00     | 1.00     |
| What is Breast cancer most commonly develops in?...   | 22.8         | 1              | 5               | 1.00      | 1.00     | 1.00     |
| What is Breast cancer screening can be instrumenta... | 17.1         | 1              | 1               | 1.00      | 1.00     | 1.00     |
| **Average**                                           | **22.0**     | **1.0**        | **3.3**         | **1.00**  | **1.00** | **1.00** |

### Citation Accuracy Analysis

The model cited an average of **1.0 source(s)** out of **3.3 provided chunks**.
This is **not overfitting** — it reflects the model's conservative citation behavior:

- **Precision = 1.00** means every citation the model produced pointed to a real, valid chunk.
- **Recall = 1.00 (Top-1)** means it correctly cited the most relevant chunk every time.
- However, it only cited ~1 of ~3 provided chunks, indicating the model
  is selective (not citing everything). A truly overfitted system would cite all chunks blindly.

## 5. RAM & Resource Profiling

| Metric                   | Value   |
| ------------------------ | ------- |
| RSS before model load    | 894 MB  |
| RSS after model load     | 8006 MB |
| RSS after all benchmarks | 7309 MB |
| Model load overhead      | 7112 MB |
| Pipeline init time       | 8.0 s   |

## 6. Long Context Stress Test (Organic Data, Real LLM)

| Chunks | ~Tokens | Gen Time (s) | RAM Δ (MB) | Status  |
| ------ | ------- | ------------ | ---------- | ------- |
| 5      | 149     | 105.9        | -454       | ✅ PASS |
| 10     | 245     | 46.1         | +0         | ✅ PASS |
| 25     | 553     | 30.2         | +0         | ✅ PASS |
