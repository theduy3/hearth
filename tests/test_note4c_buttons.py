import subprocess
import tempfile
import unittest
from pathlib import Path


class Note4CButtonTests(unittest.TestCase):
    def test_tap_hold_bounce_and_boot_held_release(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "buttons-test"
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I" + str(root / "firmware/components/zectrix_board/include"),
                            str(root / "tests/note4c_buttons_test.cc"), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
            self.assertIn("NOTE4C_BUTTONS_OK", result.stdout)
