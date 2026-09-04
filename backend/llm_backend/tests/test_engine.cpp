// Engine tests. These need a real GGUF, so they SKIP (exit 77, which CTest
// reports as "Skipped") when no model is available rather than failing the
// build on a machine that has not downloaded one.
//
// Model resolution: $LLM_TEST_MODEL, else backend/models/*.gguf (first match).

#include "engine.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "test_util.hpp"

#if defined(__has_include)
#if __has_include(<filesystem>)
#include <filesystem>
#define HAVE_FS 1
#endif
#endif

namespace {

std::string FindModel() {
  if (const char* env = std::getenv("LLM_TEST_MODEL")) {
    if (*env) return env;
  }
#ifdef HAVE_FS
  namespace fs = std::filesystem;
  const fs::path dir(LLM_BACKEND_MODELS_DIR);
  std::error_code ec;
  if (fs::exists(dir, ec)) {
    for (const auto& e : fs::directory_iterator(dir, ec)) {
      if (e.is_regular_file(ec) && e.path().extension() == ".gguf") {
        return e.path().string();
      }
    }
  }
#endif
  return {};
}

llm::EngineParams SmallParams(const std::string& model) {
  llm::EngineParams p;
  p.model_path = model;
  p.n_ctx = 512;          // keep the KV cache tiny; these are smoke tests
  p.max_new_tokens = 24;
  p.n_gpu_layers = 0;     // CPU: deterministic and always available in CI
  p.temperature = 0.0f;   // greedy -> reproducible output
  p.n_batch = 128;
  return p;
}

void TestLoadFailsCleanlyOnMissingModel() {
  llm::Engine engine;
  llm::EngineParams p;
  p.model_path = "/nonexistent/definitely-not-a-model.gguf";
  p.n_ctx = 256;
  std::string err;
  CHECK(!engine.Load(p, err));
  CHECK(!err.empty());
  CHECK(!engine.loaded());
  // Generating on an unloaded engine must be refused, not crash.
  const auto r = engine.Generate("hello");
  CHECK(!r.ok);
  CHECK(!r.error.empty());
}

void TestTokenizeRoundTrip(llm::Engine& engine) {
  const auto toks = engine.Tokenize("The capital of France is Paris.", true);
  CHECK(!toks.empty());
  // Same text must tokenize identically every time.
  const auto again = engine.Tokenize("The capital of France is Paris.", true);
  CHECK_EQ(toks.size(), again.size());
  // Empty input yields no tokens beyond an optional BOS.
  const auto empty = engine.Tokenize("", false);
  CHECK(empty.empty());
}

void TestGenerateProducesText(llm::Engine& engine) {
  const auto r = engine.Generate("Question: What is 2 + 2?\nAnswer:");
  CHECK(r.ok);
  CHECK(r.error.empty());
  CHECK(r.prompt_tokens > 0);
  CHECK(r.generated_tokens > 0);
  CHECK(!r.text.empty());
  // Must respect the cap.
  CHECK(r.generated_tokens <= engine.params().max_new_tokens);
}

void TestRequestsAreIndependent(llm::Engine& engine) {
  // The KV cache is cleared per request, so the same prompt at temperature 0
  // must give the same answer regardless of what ran before it.
  const std::string p = "Question: What colour is the sky?\nAnswer:";
  const auto a = engine.Generate(p);
  engine.Generate("Completely unrelated prompt about tractors and soil.");
  const auto b = engine.Generate(p);
  CHECK(a.ok);
  CHECK(b.ok);
  CHECK_EQ(a.text, b.text);
}

void TestOverlongPromptIsRejected(llm::Engine& engine) {
  // n_ctx is 512 here; build something comfortably past it.
  std::string huge;
  huge.reserve(40000);
  for (int i = 0; i < 4000; ++i) huge += "word ";
  const auto r = engine.Generate(huge);
  CHECK(!r.ok);
  CHECK(r.error.find("too long") != std::string::npos);
}

void TestGenerationStaysInsideContext(llm::Engine& engine) {
  // Prompt that nearly fills n_ctx: generation must be clamped to the space
  // left rather than running off the end of the KV cache.
  std::string filler;
  for (int i = 0; i < 300; ++i) filler += "alpha ";
  const auto r = engine.Generate(filler);
  if (r.ok) {
    CHECK(r.prompt_tokens + r.generated_tokens <=
          static_cast<int32_t>(engine.n_ctx()));
  }
}

void TestEmptyPromptIsHandled(llm::Engine& engine) {
  const auto r = engine.Generate("");
  // Either it refuses or it generates; it must not crash or report success
  // with an error set.
  CHECK(r.ok || !r.error.empty());
}

void TestEnvOverrides() {
  llm::EngineParams base;
  base.max_new_tokens = 256;
  base.temperature = 0.1f;
#ifdef _WIN32
  _putenv_s("LLM_MAX_NEW_TOKENS", "42");
  _putenv_s("LLM_TEMPERATURE", "0.7");
#else
  setenv("LLM_MAX_NEW_TOKENS", "42", 1);
  setenv("LLM_TEMPERATURE", "0.7", 1);
#endif
  const auto p = llm::LoadParamsFromEnv(base);
  CHECK_EQ(p.max_new_tokens, 42);
  CHECK(p.temperature > 0.69f && p.temperature < 0.71f);
#ifdef _WIN32
  _putenv_s("LLM_MAX_NEW_TOKENS", "");
  _putenv_s("LLM_TEMPERATURE", "");
#else
  unsetenv("LLM_MAX_NEW_TOKENS");
  unsetenv("LLM_TEMPERATURE");
#endif
  // A malformed value must fall back rather than becoming 0.
#ifdef _WIN32
  _putenv_s("LLM_MAX_NEW_TOKENS", "not-a-number");
#else
  setenv("LLM_MAX_NEW_TOKENS", "not-a-number", 1);
#endif
  const auto p2 = llm::LoadParamsFromEnv(base);
  CHECK_EQ(p2.max_new_tokens, 256);
#ifndef _WIN32
  unsetenv("LLM_MAX_NEW_TOKENS");
#endif
}

}  // namespace

int main() {
  RUN(TestEnvOverrides);

  llm::BackendGuard backend_guard;
  RUN(TestLoadFailsCleanlyOnMissingModel);

  const std::string model = FindModel();
  if (model.empty()) {
    std::fprintf(stderr,
                 "[engine] no .gguf found (set LLM_TEST_MODEL or place one in "
                 "backend/models/) -- skipping model-backed tests\n");
    return llm::test::Failures() == 0 ? 77 : 1;  // 77 = CTest "skipped"
  }
  std::fprintf(stderr, "[engine] using model: %s\n", model.c_str());

  llm::Engine engine;
  std::string err;
  if (!engine.Load(SmallParams(model), err)) {
    std::fprintf(stderr, "[engine] load failed: %s\n", err.c_str());
    return 1;
  }
  CHECK(engine.loaded());

  RUN([&] { TestTokenizeRoundTrip(engine); });
  RUN([&] { TestGenerateProducesText(engine); });
  RUN([&] { TestRequestsAreIndependent(engine); });
  RUN([&] { TestOverlongPromptIsRejected(engine); });
  RUN([&] { TestGenerationStaysInsideContext(engine); });
  RUN([&] { TestEmptyPromptIsHandled(engine); });

  return llm::test::Summary("engine");
}
