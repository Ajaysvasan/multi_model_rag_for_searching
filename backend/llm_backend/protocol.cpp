#include "protocol.hpp"

#include <cstring>

namespace llm {

bool Protocol::ReadExact(void* buf, size_t n) {
  size_t off = 0;
  while (off < n) {
    const size_t r = std::fread(static_cast<char*>(buf) + off, 1, n - off, in_);
    if (r == 0) {
      // Distinguishes EOF from a transient error only for logging; either way
      // the frame is incomplete and the caller must treat it as a failure.
      return false;
    }
    off += r;
  }
  return true;
}

bool Protocol::WriteExact(const void* buf, size_t n) {
  size_t off = 0;
  while (off < n) {
    const size_t w =
        std::fwrite(static_cast<const char*>(buf) + off, 1, n - off, out_);
    if (w == 0) {
      return false;
    }
    off += w;
  }
  return true;
}

bool Protocol::ReadMessage(std::string& out_msg) {
  uint32_t len = 0;
  if (!ReadExact(&len, sizeof(len))) {
    return false;  // clean EOF or truncated header
  }
  if (len > kMaxMessageBytes) {
    // Refuse rather than attempt a huge allocation from a bad prefix.
    return false;
  }

  std::string buf;
  buf.resize(len);
  if (len > 0 && !ReadExact(buf.data(), len)) {
    return false;
  }

  out_msg.swap(buf);
  return true;
}

bool Protocol::WriteMessage(const std::string& msg) {
  if (msg.size() > kMaxMessageBytes) {
    return false;
  }
  const uint32_t len = static_cast<uint32_t>(msg.size());
  if (!WriteExact(&len, sizeof(len))) {
    return false;
  }
  if (len > 0 && !WriteExact(msg.data(), len)) {
    return false;
  }
  // The client blocks on this frame, so flush every time rather than waiting
  // for the stdio buffer to fill.
  return std::fflush(out_) == 0;
}

bool Protocol::WriteError(const std::string& text) {
  return WriteMessage("ERROR: " + text);
}

}  // namespace llm
