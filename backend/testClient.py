import os
import struct
import subprocess

os.environ["LD_LIBRARY_PATH"] = (
    os.path.abspath("third_party/llama.cpp/build/bin")
    + ":"
    + os.environ.get("LD_LIBRARY_PATH", "")
)


class CppLlmClient:
    def __init__(self, backend_path, model_path):
        self.proc = subprocess.Popen(
            [backend_path, model_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        # Wait for READY
        line = self.proc.stdout.readline().decode("utf-8").strip()
        if line != "READY":
            raise RuntimeError(f"Backend failed to start, got: {line}")

    def _write_msg(self, s: str):
        data = s.encode("utf-8")
        self.proc.stdin.write(struct.pack("<I", len(data)))
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def _read_msg(self) -> str:
        hdr = self.proc.stdout.read(4)
        if not hdr:
            raise RuntimeError("Backend closed")
        (n,) = struct.unpack("<I", hdr)
        data = self.proc.stdout.read(n)
        return data.decode("utf-8", errors="replace")

    def generate(self, prompt: str) -> str:
        self._write_msg(prompt)
        return self._read_msg()

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    client = CppLlmClient(
        "./bin/llm_backend", "./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    )
    # testing that , whether the consumption of ram is high or not to ensure whether the model is getting lazy loaded or not , if high then no , if low then yes
    test_input = input("Enter a promp for the model: ")
    out = client.generate(test_input)

    print("MODEL OUTPUT:\n", out)
    client.close()
