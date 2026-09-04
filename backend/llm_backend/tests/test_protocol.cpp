// Framing tests. No model required -- these run in milliseconds and are the
// ones that catch wire-format regressions between Python and C++.

#include "protocol.hpp"

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "test_util.hpp"

namespace {

// Round-trips messages through a real temporary file so we exercise the same
// fread/fwrite paths the process uses on a pipe.
std::vector<std::string> RoundTrip(const std::vector<std::string>& msgs,
                                   bool* all_written) {
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);

  llm::Protocol writer(nullptr, f);
  *all_written = true;
  for (const auto& m : msgs) {
    if (!writer.WriteMessage(m)) *all_written = false;
  }
  std::rewind(f);

  llm::Protocol reader(f, nullptr);
  std::vector<std::string> out;
  std::string got;
  while (reader.ReadMessage(got)) out.push_back(got);
  std::fclose(f);
  return out;
}

void TestRoundTripSimple() {
  bool ok = false;
  const std::vector<std::string> in = {"hello", "second message"};
  const auto out = RoundTrip(in, &ok);
  CHECK(ok);
  CHECK_EQ(out.size(), in.size());
  CHECK_EQ(out[0], in[0]);
  CHECK_EQ(out[1], in[1]);
}

void TestEmptyMessage() {
  bool ok = false;
  const auto out = RoundTrip({""}, &ok);
  CHECK(ok);
  CHECK_EQ(out.size(), size_t{1});
  CHECK(out[0].empty());
}

void TestBinarySafeAndUtf8() {
  bool ok = false;
  // Embedded NUL must survive: the frame is length-prefixed, not NUL-terminated.
  std::string tricky = "prefix";
  tricky.push_back('\0');
  tricky += "suffix \xE2\x9C\x93 \xF0\x9F\x9A\x80";  // check mark + rocket
  const auto out = RoundTrip({tricky}, &ok);
  CHECK(ok);
  CHECK_EQ(out.size(), size_t{1});
  CHECK_EQ(out[0].size(), tricky.size());
  CHECK(out[0] == tricky);
}

void TestLargeMessage() {
  bool ok = false;
  const std::string big(1u << 20, 'x');  // 1 MiB
  const auto out = RoundTrip({big}, &ok);
  CHECK(ok);
  CHECK_EQ(out.size(), size_t{1});
  CHECK_EQ(out[0].size(), big.size());
}

void TestTruncatedPayloadIsRejected() {
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);
  // Claim 100 bytes, supply 4.
  const uint32_t len = 100;
  std::fwrite(&len, sizeof(len), 1, f);
  std::fwrite("abcd", 1, 4, f);
  std::rewind(f);

  llm::Protocol reader(f, nullptr);
  std::string got = "untouched";
  CHECK(!reader.ReadMessage(got));
  // Failure must leave the caller's buffer alone.
  CHECK_EQ(got, std::string("untouched"));
  std::fclose(f);
}

void TestTruncatedHeaderIsRejected() {
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);
  std::fwrite("ab", 1, 2, f);  // 2 of the 4 header bytes
  std::rewind(f);
  llm::Protocol reader(f, nullptr);
  std::string got;
  CHECK(!reader.ReadMessage(got));
  std::fclose(f);
}

void TestOversizedLengthIsRejected() {
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);
  // A hostile prefix must be refused without attempting a huge allocation.
  const uint32_t len = llm::kMaxMessageBytes + 1;
  std::fwrite(&len, sizeof(len), 1, f);
  std::rewind(f);
  llm::Protocol reader(f, nullptr);
  std::string got;
  CHECK(!reader.ReadMessage(got));
  std::fclose(f);
}

void TestErrorFrameHasExpectedPrefix() {
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);
  llm::Protocol writer(nullptr, f);
  CHECK(writer.WriteError("prompt too long"));
  std::rewind(f);

  llm::Protocol reader(f, nullptr);
  std::string got;
  CHECK(reader.ReadMessage(got));
  // MmapGenerator keys off exactly this prefix.
  CHECK_EQ(got.rfind("ERROR: ", 0), size_t{0});
  CHECK(got.find("prompt too long") != std::string::npos);
  std::fclose(f);
}

void TestLittleEndianWireFormat() {
  // Python packs the header with struct.pack("<I", n). Verify the bytes match
  // so the two sides cannot silently drift on a big-endian build.
  std::FILE* f = std::tmpfile();
  REQUIRE(f != nullptr);
  llm::Protocol writer(nullptr, f);
  CHECK(writer.WriteMessage("AB"));
  std::rewind(f);

  unsigned char hdr[4] = {0, 0, 0, 0};
  CHECK_EQ(std::fread(hdr, 1, 4, f), size_t{4});
  CHECK_EQ(int{hdr[0]}, 2);
  CHECK_EQ(int{hdr[1]}, 0);
  CHECK_EQ(int{hdr[2]}, 0);
  CHECK_EQ(int{hdr[3]}, 0);
  std::fclose(f);
}

}  // namespace

int main() {
  RUN(TestRoundTripSimple);
  RUN(TestEmptyMessage);
  RUN(TestBinarySafeAndUtf8);
  RUN(TestLargeMessage);
  RUN(TestTruncatedPayloadIsRejected);
  RUN(TestTruncatedHeaderIsRejected);
  RUN(TestOversizedLengthIsRejected);
  RUN(TestErrorFrameHasExpectedPrefix);
  RUN(TestLittleEndianWireFormat);
  return llm::test::Summary("protocol");
}
