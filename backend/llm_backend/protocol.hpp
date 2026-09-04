// protocol.hpp -- length-prefixed message framing for the Python <-> C++ IPC.
//
// Wire format (unchanged, so existing MmapGenerator clients keep working):
//
//     [ uint32 little-endian length ][ length bytes of UTF-8 payload ]
//
// Deliberately free of any llama.cpp dependency so it can be unit-tested on
// its own, without loading a multi-gigabyte model.

#pragma once

#include <cstdint>
#include <cstdio>
#include <string>

namespace llm {

// Largest payload we will accept or emit. A corrupt or hostile length prefix
// would otherwise make us try to allocate up to 4 GiB from a single bad read.
inline constexpr uint32_t kMaxMessageBytes = 64u * 1024u * 1024u;  // 64 MiB

// A framed byte stream over two FILE* handles (stdin/stdout by default).
// Non-owning: the streams outlive this object and are not closed by it.
class Protocol {
 public:
  Protocol(std::FILE* in, std::FILE* out) : in_(in), out_(out) {}

  // Blocks until a whole message arrives.
  // Returns false on clean EOF, a short read, or a length exceeding
  // kMaxMessageBytes. `out_msg` is only modified on success.
  bool ReadMessage(std::string& out_msg);

  // Writes the frame and flushes. Returns false on write failure or if the
  // payload exceeds kMaxMessageBytes.
  bool WriteMessage(const std::string& msg);

  // Writes an "ERROR: <text>" frame. The Python side keys off this prefix.
  bool WriteError(const std::string& text);

 private:
  bool ReadExact(void* buf, size_t n);
  bool WriteExact(const void* buf, size_t n);

  std::FILE* in_;
  std::FILE* out_;
};

}  // namespace llm
