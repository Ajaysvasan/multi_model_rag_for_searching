#include <algorithm>
#include <atomic>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "llama.h"

static std::atomic<bool> g_shutdown{false};

void handle_signal(int) { g_shutdown.store(true); }

// Read exactly n bytes from stdin
bool read_exact(void *buf, size_t n) {
  size_t off = 0;
  while (off < n) {
    size_t r = fread((char *)buf + off, 1, n - off, stdin);
    if (r == 0)
      return false;
    off += r;
  }
  return true;
}

// Write exactly n bytes to stdout
bool write_exact(const void *buf, size_t n) {
  size_t off = 0;
  while (off < n) {
    size_t w = fwrite((const char *)buf + off, 1, n - off, stdout);
    if (w == 0)
      return false;
    off += w;
  }
  fflush(stdout);
  return true;
}

// Read a length-prefixed UTF-8 string
bool read_message(std::string &out) {
  uint32_t len = 0;
  if (!read_exact(&len, sizeof(len)))
    return false;
  out.resize(len);
  if (len > 0 && !read_exact(out.data(), len))
    return false;
  return true;
}

// Write a length-prefixed UTF-8 string
bool write_message(const std::string &s) {
  uint32_t len = (uint32_t)s.size();
  if (!write_exact(&len, sizeof(len)))
    return false;
  if (len > 0 && !write_exact(s.data(), len))
    return false;
  return true;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    std::cerr << "Usage: llm_backend <model.gguf>\n";
    return 1;
  }
  const char *model_path = argv[1];

  std::signal(SIGINT, handle_signal);
  std::signal(SIGTERM, handle_signal);

  // ---- llama.cpp backend init ----
  llama_backend_init();

  llama_model_params mparams = llama_model_default_params();
  mparams.use_mmap = true;   // important: mmap GGUF
  mparams.use_mlock = false; // keep false for now

  llama_model *model = llama_model_load_from_file(model_path, mparams);
  if (!model) {
    std::cerr << "Failed to load model: " << model_path << "\n";
    return 1;
  }

  // ---- create context ----
  llama_context_params cparams = llama_context_default_params();
  cparams.n_ctx = 4096;
  unsigned hw = std::thread::hardware_concurrency();
  cparams.n_threads = std::max(1u, hw);
  cparams.n_threads_batch = cparams.n_threads;

  llama_context *ctx = llama_init_from_model(model, cparams);
  if (!ctx) {
    std::cerr << "Failed to create context\n";
    llama_model_free(model);
    return 1;
  }

  // ---- get vocab (new API) ----
  const llama_vocab *vocab = llama_model_get_vocab(model);
  if (!vocab) {
    std::cerr << "Failed to get vocab\n";
    llama_free(ctx);
    llama_model_free(model);
    return 1;
  }

  // ---- optional warmup ----
  {
    const char *warm = " ";
    std::vector<llama_token> toks(16);
    int n = llama_tokenize(vocab, warm, (int)std::strlen(warm), toks.data(),
                           (int)toks.size(),
                           /*add_bos=*/true, /*special=*/false);
    if (n > 0) {
      toks.resize(n);
      llama_batch batch = llama_batch_init(n, 0, 1);
      for (int i = 0; i < n; ++i) {
        batch.token[i] = toks[i];
        batch.pos[i] = i;
        batch.seq_id[i][0] = 0;
        batch.n_seq_id[i] = 1;
        batch.logits[i] = (i == n - 1);
      }
      batch.n_tokens = n;
      llama_decode(ctx, batch);
      llama_batch_free(batch);
    }
  }

  // Handshake for Python
  std::cout << "READY\n" << std::flush;

  // ---- request loop ----
  while (!g_shutdown.load()) {
    std::string prompt;
    if (!read_message(prompt)) {
      break; // stdin closed
    }

    // Tokenize prompt
    std::vector<llama_token> tokens(prompt.size() + 8);
    int n_tokens = llama_tokenize(vocab, prompt.c_str(), (int)prompt.size(),
                                  tokens.data(), (int)tokens.size(),
                                  /*add_bos=*/true, /*special=*/false);
    if (n_tokens < 0) {
      write_message("ERROR: tokenization failed");
      continue;
    }
    tokens.resize(n_tokens);

    // Evaluate prompt
    llama_batch batch = llama_batch_init(n_tokens, 0, 1);
    for (int i = 0; i < n_tokens; ++i) {
      batch.token[i] = tokens[i];
      batch.pos[i] = i;
      batch.seq_id[i][0] = 0;
      batch.n_seq_id[i] = 1;
      batch.logits[i] = (i == n_tokens - 1);
    }
    batch.n_tokens = n_tokens;

    if (llama_decode(ctx, batch) != 0) {
      llama_batch_free(batch);
      write_message("ERROR: decode failed");
      continue;
    }
    llama_batch_free(batch);

    // Greedy sampling (v1)
    std::string output;
    const int max_new = 256;
    const int vocab_size = llama_vocab_n_tokens(vocab);
    const llama_token eos = llama_vocab_eos(vocab);

    for (int i = 0; i < max_new; ++i) {
      const float *logits = llama_get_logits(ctx);

      int best = 0;
      float bestv = logits[0];
      for (int j = 1; j < vocab_size; ++j) {
        if (logits[j] > bestv) {
          bestv = logits[j];
          best = j;
        }
      }

      if (best == eos)
        break;

      // token -> text
      char buf[256];
      int n =
          llama_token_to_piece(vocab, (llama_token)best, buf, (int)sizeof(buf),
                               /*lstrip=*/0, /*special=*/true);
      if (n > 0)
        output.append(buf, n);

      // feed token back
      llama_batch b2 = llama_batch_init(1, 0, 1);
      b2.token[0] = (llama_token)best;
      b2.pos[0] = n_tokens + i;
      b2.seq_id[0][0] = 0;
      b2.n_seq_id[0] = 1;
      b2.logits[0] = true;
      b2.n_tokens = 1;

      if (llama_decode(ctx, b2) != 0) {
        llama_batch_free(b2);
        break;
      }
      llama_batch_free(b2);
    }

    if (!write_message(output)) {
      break;
    }
  }

  // ---- shutdown ----
  llama_free(ctx);
  llama_model_free(model);
  llama_backend_free();

  return 0;
}
