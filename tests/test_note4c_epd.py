import subprocess
import tempfile
import unittest
from pathlib import Path


class Note4CEpdTests(unittest.TestCase):
    def test_real_driver_command_trace_palette_timeout_and_spi_failure(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "epd-test"
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I" + str(root / "tests/epd_stubs"),
                            "-I" + str(root / "firmware/components/zectrix_epd/include"),
                            str(root / "firmware/components/zectrix_epd/zectrix_epd.cc"),
                            str(root / "tests/note4c_epd_test.cc"), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
            self.assertIn("NOTE4C_EPD_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
