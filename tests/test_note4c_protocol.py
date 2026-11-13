import subprocess
import tempfile
import unittest
from pathlib import Path


class Note4CProtocolTests(unittest.TestCase):
    def test_fragmented_wav_validation_completion_cancel_and_opaque_ids(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "protocol-test"
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I" + str(root / "firmware/main"),
                            str(root / "firmware/main/hearth_protocol.cc"),
                            str(root / "tests/note4c_protocol_test.cc"), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NOTE4C_PROTOCOL_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
