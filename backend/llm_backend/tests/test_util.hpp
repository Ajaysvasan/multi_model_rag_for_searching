// Minimal assertion harness. Deliberately dependency-free: pulling GoogleTest
// into this build would mean another submodule and a longer first compile for
// a handful of tests.

#pragma once

#include <cstdio>
#include <cstdlib>
#include <string>

namespace llm {
namespace test {

inline int& Failures() {
  static int n = 0;
  return n;
}

inline void Fail(const char* file, int line, const std::string& what) {
  std::fprintf(stderr, "  FAIL %s:%d: %s\n", file, line, what.c_str());
  ++Failures();
}

inline int Summary(const char* suite) {
  if (Failures() == 0) {
    std::fprintf(stderr, "[%s] all checks passed\n", suite);
    return 0;
  }
  std::fprintf(stderr, "[%s] %d check(s) FAILED\n", suite, Failures());
  return 1;
}

}  // namespace test
}  // namespace llm

#define CHECK(cond)                                                        \
  do {                                                                     \
    if (!(cond)) ::llm::test::Fail(__FILE__, __LINE__, "CHECK(" #cond ")"); \
  } while (0)

#define CHECK_EQ(a, b)                                                     \
  do {                                                                     \
    auto _a = (a);                                                         \
    auto _b = (b);                                                         \
    if (!(_a == _b))                                                       \
      ::llm::test::Fail(__FILE__, __LINE__, #a " == " #b);                 \
  } while (0)

// Aborts the suite: the rest of the test cannot run meaningfully.
#define REQUIRE(cond)                                                      \
  do {                                                                     \
    if (!(cond)) {                                                         \
      ::llm::test::Fail(__FILE__, __LINE__, "REQUIRE(" #cond ")");         \
      std::exit(1);                                                        \
    }                                                                      \
  } while (0)

#define RUN(fn)                                     \
  do {                                              \
    std::fprintf(stderr, "  - %s\n", #fn);          \
    fn();                                           \
  } while (0)
