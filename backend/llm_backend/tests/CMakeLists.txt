# Two suites:
#   protocol -- pure framing, no model, always runs (fast)
#   engine   -- needs a GGUF; reports "Skipped" when none is present

add_executable(test_protocol test_protocol.cpp)
target_link_libraries(test_protocol PRIVATE llm_backend_core)
add_test(NAME protocol COMMAND test_protocol)

add_executable(test_engine test_engine.cpp)
target_link_libraries(test_engine PRIVATE llm_backend_core)
# Absolute path to backend/models so the test finds a GGUF regardless of cwd.
target_compile_definitions(test_engine
  PRIVATE LLM_BACKEND_MODELS_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../../models")
add_test(NAME engine COMMAND test_engine)
set_tests_properties(engine PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 600)
