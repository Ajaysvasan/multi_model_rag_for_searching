// engine.hpp -- RAII wrapper around a llama.cpp model, context and sampler.
//
// Every llama.cpp handle here is owned by a unique_ptr with a matching
// deleter, and llama_batch is owned by a small scope guard, so there is no
// code path -- including early returns and exceptions -- that leaks. The
// previous single-file implementation freed the context inside the request
// loop and rebuilt it per request, which was both a performance bug and an
// easy place to leak a batch on the error paths.
//
// This class does no I/O. It is driven by main.cpp, which owns the protocol.

#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "llama.h"

namespace llm {

// Tunables, all overridable from the environment by LoadParamsFromEnv().
struct EngineParams {
  std::string model_path;

  int32_t n_gpu_layers = -1;  // -1 = offload every layer the backend accepts
  uint32_t n_ctx = 4096;
  int32_t n_threads = 0;  // 0 -> hardware_concurrency()
  int32_t n_batch = 512;

  int32_t max_new_tokens = 256;
  float temperature = 0.1f;
  float top_p = 0.9f;
  int32_t top_k = 20;
  float repeat_penalty = 1.1f;
  int32_t repeat_last_n = 64;
  uint32_t seed = LLAMA_DEFAULT_SEED;
};

// Reads LLM_* environment variables over the supplied defaults.
// Recognised: LLM_N_GPU_LAYERS, LLM_N_CTX, LLM_N_THREADS, LLM_N_BATCH,
// LLM_MAX_NEW_TOKENS, LLM_TEMPERATURE, LLM_TOP_P, LLM_TOP_K,
// LLM_REPEAT_PENALTY, LLM_SEED.
EngineParams LoadParamsFromEnv(EngineParams defaults);

// Outcome of one generation request.
struct GenerationResult {
  bool ok = false;
  std::string text;         // generated text (empty on failure)
  std::string error;        // human-readable reason when ok == false
  int32_t prompt_tokens = 0;
  int32_t generated_tokens = 0;
  bool hit_token_limit = false;  // stopped at max_new_tokens, not at EOG
};

// Call once per process before constructing any Engine, and Free once after
// the last Engine is destroyed. BackendGuard does both via RAII.
class BackendGuard {
 public:
  BackendGuard();
  ~BackendGuard();
  BackendGuard(const BackendGuard&) = delete;
  BackendGuard& operator=(const BackendGuard&) = delete;
};

class Engine {
 public:
  Engine() = default;
  ~Engine() = default;

  // Non-copyable, movable: the handles are unique owners.
  Engine(const Engine&) = delete;
  Engine& operator=(const Engine&) = delete;
  Engine(Engine&&) = default;
  Engine& operator=(Engine&&) = default;

  // Loads the model and builds the context and sampler chain.
  // Returns false and fills `error` if anything fails; the object stays unused.
  bool Load(const EngineParams& params, std::string& error);

  bool loaded() const { return model_ != nullptr && ctx_ != nullptr; }

  // Runs one prompt to completion. Clears the KV cache and resets the sampler
  // first, so requests are independent without tearing down the context.
  GenerationResult Generate(const std::string& prompt);

  // Tokenises without generating. Exposed for tests and for callers that want
  // to check a prompt against the context window up front.
  std::vector<llama_token> Tokenize(const std::string& text, bool add_bos) const;

  uint32_t n_ctx() const { return ctx_ ? llama_n_ctx(ctx_.get()) : 0; }
  const EngineParams& params() const { return params_; }

 private:
  struct ModelDeleter {
    void operator()(llama_model* m) const noexcept {
      if (m) llama_model_free(m);
    }
  };
  struct ContextDeleter {
    void operator()(llama_context* c) const noexcept {
      if (c) llama_free(c);
    }
  };
  struct SamplerDeleter {
    void operator()(llama_sampler* s) const noexcept {
      if (s) llama_sampler_free(s);
    }
  };

  bool BuildSampler(std::string& error);
  // Feeds `tokens` through llama_decode in n_batch-sized slices.
  bool DecodePrompt(const std::vector<llama_token>& tokens, std::string& error);

  EngineParams params_;
  std::unique_ptr<llama_model, ModelDeleter> model_;
  std::unique_ptr<llama_context, ContextDeleter> ctx_;
  std::unique_ptr<llama_sampler, SamplerDeleter> sampler_;
  const llama_vocab* vocab_ = nullptr;  // owned by model_
};

}  // namespace llm
