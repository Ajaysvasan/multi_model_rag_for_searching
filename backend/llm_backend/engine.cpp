#include "engine.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <thread>

namespace llm {
namespace {

int32_t EnvInt(const char* name, int32_t fallback) {
  const char* v = std::getenv(name);
  if (v == nullptr || *v == '\0') return fallback;
  char* end = nullptr;
  const long parsed = std::strtol(v, &end, 10);
  return (end != nullptr && *end == '\0') ? static_cast<int32_t>(parsed)
                                          : fallback;
}

float EnvFloat(const char* name, float fallback) {
  const char* v = std::getenv(name);
  if (v == nullptr || *v == '\0') return fallback;
  char* end = nullptr;
  const float parsed = std::strtof(v, &end);
  return (end != nullptr && *end == '\0') ? parsed : fallback;
}

// Owns a llama_batch for the duration of a scope. llama_batch_init allocates
// several parallel arrays; without this guard every early return in the decode
// paths is a leak, which is exactly what the previous implementation had.
class BatchGuard {
 public:
  BatchGuard(int32_t n_tokens_alloc, int32_t embd, int32_t n_seq_max)
      : batch_(llama_batch_init(n_tokens_alloc, embd, n_seq_max)) {}
  ~BatchGuard() { llama_batch_free(batch_); }

  BatchGuard(const BatchGuard&) = delete;
  BatchGuard& operator=(const BatchGuard&) = delete;

  llama_batch& get() { return batch_; }

  // Fills the batch with one token at `pos`, requesting logits for it.
  void SetSingle(llama_token tok, llama_pos pos, bool want_logits) {
    batch_.n_tokens = 1;
    batch_.token[0] = tok;
    batch_.pos[0] = pos;
    batch_.n_seq_id[0] = 1;
    batch_.seq_id[0][0] = 0;
    batch_.logits[0] = want_logits ? 1 : 0;
  }

 private:
  llama_batch batch_;
};

}  // namespace

EngineParams LoadParamsFromEnv(EngineParams d) {
  d.n_gpu_layers = EnvInt("LLM_N_GPU_LAYERS", d.n_gpu_layers);
  d.n_ctx = static_cast<uint32_t>(
      EnvInt("LLM_N_CTX", static_cast<int32_t>(d.n_ctx)));
  d.n_threads = EnvInt("LLM_N_THREADS", d.n_threads);
  d.n_batch = EnvInt("LLM_N_BATCH", d.n_batch);
  d.max_new_tokens = EnvInt("LLM_MAX_NEW_TOKENS", d.max_new_tokens);
  d.temperature = EnvFloat("LLM_TEMPERATURE", d.temperature);
  d.top_p = EnvFloat("LLM_TOP_P", d.top_p);
  d.top_k = EnvInt("LLM_TOP_K", d.top_k);
  d.repeat_penalty = EnvFloat("LLM_REPEAT_PENALTY", d.repeat_penalty);
  d.seed = static_cast<uint32_t>(
      EnvInt("LLM_SEED", static_cast<int32_t>(d.seed)));
  return d;
}

BackendGuard::BackendGuard() { llama_backend_init(); }
BackendGuard::~BackendGuard() { llama_backend_free(); }

bool Engine::Load(const EngineParams& params, std::string& error) {
  params_ = params;

  llama_model_params mparams = llama_model_default_params();
  mparams.use_mmap = true;    // page the GGUF in on demand, keeping RSS low
  mparams.use_mlock = false;
  // Previously left at the default 0, so the backend ran on CPU even when
  // built against a GPU-enabled ggml.
  mparams.n_gpu_layers = params_.n_gpu_layers;

  model_.reset(llama_model_load_from_file(params_.model_path.c_str(), mparams));
  if (!model_) {
    error = "failed to load model: " + params_.model_path;
    return false;
  }

  vocab_ = llama_model_get_vocab(model_.get());
  if (vocab_ == nullptr) {
    error = "failed to get vocab from model";
    model_.reset();
    return false;
  }

  int32_t threads = params_.n_threads;
  if (threads <= 0) {
    threads = static_cast<int32_t>(std::thread::hardware_concurrency());
    if (threads <= 0) threads = 4;
  }

  llama_context_params cparams = llama_context_default_params();
  cparams.n_ctx = params_.n_ctx;
  cparams.n_batch = static_cast<uint32_t>(std::max(params_.n_batch, 1));
  cparams.n_threads = threads;
  cparams.n_threads_batch = threads;

  ctx_.reset(llama_init_from_model(model_.get(), cparams));
  if (!ctx_) {
    error = "failed to create llama context";
    model_.reset();
    vocab_ = nullptr;
    return false;
  }

  if (!BuildSampler(error)) {
    ctx_.reset();
    model_.reset();
    vocab_ = nullptr;
    return false;
  }

  // Warm up so the first real request does not pay allocator and kernel
  // initialisation costs.
  const std::vector<llama_token> warm = Tokenize(" ", /*add_bos=*/true);
  if (!warm.empty()) {
    std::string ignored;
    DecodePrompt(warm, ignored);
    llama_memory_clear(llama_get_memory(ctx_.get()), true);
  }

  return true;
}

bool Engine::BuildSampler(std::string& error) {
  llama_sampler_chain_params sparams = llama_sampler_chain_default_params();
  sampler_.reset(llama_sampler_chain_init(sparams));
  if (!sampler_) {
    error = "failed to create sampler chain";
    return false;
  }

  // Sampling used to be a hand-rolled argmax over the full vocabulary, which
  // ignored every parameter the caller passed and could not stop on
  // end-of-generation tokens that are not literally EOS.
  llama_sampler_chain_add(
      sampler_.get(),
      llama_sampler_init_penalties(params_.repeat_last_n,
                                   params_.repeat_penalty,
                                   /*penalty_freq=*/0.0f,
                                   /*penalty_present=*/0.0f));

  if (params_.temperature <= 0.0f) {
    llama_sampler_chain_add(sampler_.get(), llama_sampler_init_greedy());
  } else {
    llama_sampler_chain_add(sampler_.get(),
                            llama_sampler_init_top_k(params_.top_k));
    llama_sampler_chain_add(sampler_.get(),
                            llama_sampler_init_top_p(params_.top_p, 1));
    llama_sampler_chain_add(sampler_.get(),
                            llama_sampler_init_temp(params_.temperature));
    llama_sampler_chain_add(sampler_.get(),
                            llama_sampler_init_dist(params_.seed));
  }
  return true;
}

std::vector<llama_token> Engine::Tokenize(const std::string& text,
                                          bool add_bos) const {
  if (vocab_ == nullptr) return {};

  // Two-pass: llama_tokenize returns the negated required size when the
  // supplied buffer is too small. The old code guessed prompt.size() + 8,
  // which over-allocated for ASCII and could still be wrong for other scripts.
  const int32_t needed =
      llama_tokenize(vocab_, text.c_str(), static_cast<int32_t>(text.size()),
                     nullptr, 0, add_bos, /*parse_special=*/true);
  const int32_t count = needed < 0 ? -needed : needed;
  if (count <= 0) return {};

  std::vector<llama_token> tokens(static_cast<size_t>(count));
  const int32_t written =
      llama_tokenize(vocab_, text.c_str(), static_cast<int32_t>(text.size()),
                     tokens.data(), static_cast<int32_t>(tokens.size()), add_bos,
                     /*parse_special=*/true);
  if (written < 0) return {};
  tokens.resize(static_cast<size_t>(written));
  return tokens;
}

bool Engine::DecodePrompt(const std::vector<llama_token>& tokens,
                          std::string& error) {
  const int32_t n_batch = std::max(params_.n_batch, 1);
  BatchGuard guard(n_batch, /*embd=*/0, /*n_seq_max=*/1);
  llama_batch& batch = guard.get();

  const int32_t total = static_cast<int32_t>(tokens.size());
  for (int32_t start = 0; start < total; start += n_batch) {
    const int32_t n = std::min(n_batch, total - start);
    batch.n_tokens = n;
    for (int32_t i = 0; i < n; ++i) {
      batch.token[i] = tokens[static_cast<size_t>(start + i)];
      batch.pos[i] = start + i;
      batch.n_seq_id[i] = 1;
      batch.seq_id[i][0] = 0;
      // Only the very last token of the whole prompt needs logits.
      batch.logits[i] = (start + i == total - 1) ? 1 : 0;
    }
    if (llama_decode(ctx_.get(), batch) != 0) {
      error = "decode failed during prompt evaluation";
      return false;
    }
  }
  return true;
}

GenerationResult Engine::Generate(const std::string& prompt) {
  GenerationResult result;

  if (!loaded()) {
    result.error = "engine not loaded";
    return result;
  }

  const std::vector<llama_token> tokens = Tokenize(prompt, /*add_bos=*/true);
  if (tokens.empty()) {
    result.error = "tokenization produced no tokens";
    return result;
  }

  const int32_t n_ctx = static_cast<int32_t>(llama_n_ctx(ctx_.get()));
  result.prompt_tokens = static_cast<int32_t>(tokens.size());
  if (result.prompt_tokens >= n_ctx) {
    result.error = "prompt too long for context window (" +
                   std::to_string(result.prompt_tokens) + " tokens, n_ctx " +
                   std::to_string(n_ctx) + ")";
    return result;
  }

  // Start each request from a clean slate without destroying the context.
  llama_memory_clear(llama_get_memory(ctx_.get()), true);
  llama_sampler_reset(sampler_.get());

  if (!DecodePrompt(tokens, result.error)) {
    return result;
  }

  // Never let generation run past the end of the context window.
  const int32_t room = n_ctx - result.prompt_tokens;
  const int32_t budget = std::min(params_.max_new_tokens, room);

  // One reusable single-token batch instead of llama_batch_init/free on every
  // generated token, which is what the previous implementation did.
  BatchGuard step(/*n_tokens_alloc=*/1, /*embd=*/0, /*n_seq_max=*/1);

  std::string text;
  char piece[512];
  int32_t generated = 0;

  for (int32_t i = 0; i < budget; ++i) {
    const llama_token tok = llama_sampler_sample(sampler_.get(), ctx_.get(), -1);
    if (llama_vocab_is_eog(vocab_, tok)) {
      break;
    }
    llama_sampler_accept(sampler_.get(), tok);

    const int32_t n = llama_token_to_piece(vocab_, tok, piece,
                                           static_cast<int32_t>(sizeof(piece)),
                                           /*lstrip=*/0, /*special=*/false);
    if (n > 0) {
      text.append(piece, static_cast<size_t>(n));
    }
    ++generated;

    step.SetSingle(tok, result.prompt_tokens + i, /*want_logits=*/true);
    if (llama_decode(ctx_.get(), step.get()) != 0) {
      // Keep what we have rather than discarding a partial answer.
      break;
    }
  }

  result.ok = true;
  result.text = std::move(text);
  result.generated_tokens = generated;
  result.hit_token_limit = (generated >= budget);
  return result;
}

}  // namespace llm
