# llm_backend -- standalone llama.cpp worker process.
#
# Build (from backend/):
#   cmake -S llm_backend -B llm_backend/build -DCMAKE_BUILD_TYPE=Release
#   cmake --build llm_backend/build -j
#   ctest --test-dir llm_backend/build --output-on-failure
#
# The binary is copied to backend/bin/llm_backend, which is where
# Config.BIN_PATH expects it.
#
# llama.cpp is located in this order:
#   1. -DLLAMA_ROOT=<dir>        explicit override
#   2. third_party/llama.cpp     vendored source tree (built via add_subdirectory)
#   3. find_package(Llama)       system install
#
# GPU: pass the same flags you would pass to llama.cpp itself, e.g.
#   cmake -S llm_backend -B llm_backend/build -DGGML_CUDA=ON

cmake_minimum_required(VERSION 3.16)
project(llm_backend LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

option(LLM_BACKEND_BUILD_TESTS "Build llm_backend tests" ON)
option(LLM_BACKEND_ASAN "Build with AddressSanitizer + UBSan" OFF)

# --- locate llama.cpp --------------------------------------------------------
set(LLAMA_ROOT "" CACHE PATH "Path to a llama.cpp source tree or install prefix")

set(_vendored "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/llama.cpp")
set(_llama_target "")

if(LLAMA_ROOT AND EXISTS "${LLAMA_ROOT}/CMakeLists.txt")
  add_subdirectory("${LLAMA_ROOT}" "${CMAKE_BINARY_DIR}/llama.cpp" EXCLUDE_FROM_ALL)
  set(_llama_target llama)
elseif(EXISTS "${_vendored}/CMakeLists.txt")
  # Do not build llama.cpp's own tools/examples; we only need the library.
  set(LLAMA_BUILD_TESTS    OFF CACHE BOOL "" FORCE)
  set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(LLAMA_BUILD_TOOLS    OFF CACHE BOOL "" FORCE)
  set(LLAMA_BUILD_SERVER   OFF CACHE BOOL "" FORCE)
  add_subdirectory("${_vendored}" "${CMAKE_BINARY_DIR}/llama.cpp" EXCLUDE_FROM_ALL)
  set(_llama_target llama)
else()
  find_package(Llama QUIET)
  if(TARGET llama)
    set(_llama_target llama)
  else()
    message(FATAL_ERROR
      "llama.cpp not found.\n"
      "Clone it to backend/third_party/llama.cpp, or configure with "
      "-DLLAMA_ROOT=/path/to/llama.cpp")
  endif()
endif()

message(STATUS "llm_backend: linking llama target '${_llama_target}'")

# --- library -----------------------------------------------------------------
# Engine and protocol live in a library so the tests can link them without
# pulling in main().
add_library(llm_backend_core STATIC
  engine.cpp
  protocol.cpp
)
target_include_directories(llm_backend_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(llm_backend_core PUBLIC ${_llama_target})

if(LLM_BACKEND_ASAN)
  target_compile_options(llm_backend_core PUBLIC -fsanitize=address,undefined -fno-omit-frame-pointer -g)
  target_link_options(llm_backend_core PUBLIC -fsanitize=address,undefined)
endif()

if(MSVC)
  target_compile_options(llm_backend_core PRIVATE /W4)
else()
  target_compile_options(llm_backend_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

# --- executable --------------------------------------------------------------
add_executable(llm_backend main.cpp)
target_link_libraries(llm_backend PRIVATE llm_backend_core)

# Drop the binary where Config.BIN_PATH looks for it.
add_custom_command(TARGET llm_backend POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_CURRENT_SOURCE_DIR}/../bin"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "$<TARGET_FILE:llm_backend>"
          "${CMAKE_CURRENT_SOURCE_DIR}/../bin/llm_backend"
  COMMENT "Installing llm_backend to backend/bin/"
)

# --- tests -------------------------------------------------------------------
if(LLM_BACKEND_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()
