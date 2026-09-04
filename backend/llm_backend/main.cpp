// main.cpp -- thin driver for the llm_backend worker.
//
// Owns process concerns only: argument parsing, signal handling, and the
// read-generate-write loop. Framing lives in protocol.{hpp,cpp} and all
// llama.cpp interaction lives in engine.{hpp,cpp}.
//
// Protocol: the parent writes one length-prefixed UTF-8 prompt and reads one
// length-prefixed UTF-8 reply. A reply beginning "ERROR: " signals failure.
// The line "READY\n" is emitted on stdout once the model is loaded.

#include <atomic>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>

#include "engine.hpp"
#include "protocol.hpp"

namespace {

std::atomic<bool> g_shutdown{false};

extern "C" void HandleSignal(int) { g_shutdown.store(true); }

void PrintUsage(const char* argv0) {
  std::cerr
      << "Usage: " << argv0 << " <model.gguf>\n\n"
      << "Reads length-prefixed UTF-8 prompts on stdin, writes length-prefixed\n"
      << "UTF-8 replies on stdout. Prints READY once the model is loaded.\n\n"
      << "Environment overrides:\n"
      << "  LLM_N_GPU_LAYERS   layers to offload (-1 = all, 0 = CPU)\n"
      << "  LLM_N_CTX          context window size\n"
      << "  LLM_N_THREADS      CPU threads (0 = hardware concurrency)\n"
      << "  LLM_N_BATCH        prompt evaluation batch size\n"
      << "  LLM_MAX_NEW_TOKENS generation cap per request\n"
      << "  LLM_TEMPERATURE    0 or less selects greedy sampling\n"
      << "  LLM_TOP_P          nucleus sampling threshold\n"
      << "  LLM_TOP_K          top-k sampling cutoff\n"
      << "  LLM_REPEAT_PENALTY repetition penalty (1.0 disables)\n"
      << "  LLM_SEED           RNG seed\n";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    PrintUsage(argv[0]);
    return 1;
  }

  std::signal(SIGINT, HandleSignal);
  std::signal(SIGTERM, HandleSignal);
  // A dead parent should not kill us mid-write with an unhandled SIGPIPE; the
  // write simply fails and we leave the loop cleanly.
  std::signal(SIGPIPE, SIG_IGN);

  llm::EngineParams params;
  params.model_path = argv[1];
  params = llm::LoadParamsFromEnv(params);

  // Backend init/free is tied to this scope, so teardown runs after the engine
  // is destroyed no matter how we leave main.
  llm::BackendGuard backend_guard;

  llm::Engine engine;
  std::string error;
  if (!engine.Load(params, error)) {
    std::cerr << "Fatal: " << error << "\n";
    return 1;
  }

  std::cerr << "llm_backend ready: n_ctx=" << engine.n_ctx()
            << " n_gpu_layers=" << params.n_gpu_layers
            << " max_new_tokens=" << params.max_new_tokens << "\n";

  std::cout << "READY\n" << std::flush;

  llm::Protocol proto(stdin, stdout);

  while (!g_shutdown.load()) {
    std::string prompt;
    if (!proto.ReadMessage(prompt)) {
      break;  // clean EOF, closed pipe, or an oversized/corrupt frame
    }

    const llm::GenerationResult result = engine.Generate(prompt);

    const bool written = result.ok ? proto.WriteMessage(result.text)
                                   : proto.WriteError(result.error);
    if (!written) {
      break;  // parent went away
    }
  }

  return 0;
}
