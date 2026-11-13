import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import prepare_parakeet


class ParakeetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.model = b"GGUF-test-model"
        self.size = patch.object(prepare_parakeet, "SIZE", len(self.model))
        self.digest = patch.object(prepare_parakeet, "SHA256", hashlib.sha256(self.model).hexdigest())
        self.size.start()
        self.digest.start()

    def tearDown(self):
        self.digest.stop()
        self.size.stop()
        self.temporary.cleanup()

    def response(self, url, **kwargs):
        name = url.rsplit("/", 1)[-1]
        return io.BytesIO(self.model if name == prepare_parakeet.MODEL else ("public " + name).encode())

    def test_pinned_artifacts_reverify_without_network_and_reject_corruption(self):
        with patch.object(prepare_parakeet, "urlopen", side_effect=self.response):
            prepare_parakeet.prepare(self.root)
        before = (self.root / "manifest.json").read_bytes()
        with patch.object(prepare_parakeet, "urlopen", side_effect=AssertionError("unexpected network")):
            prepare_parakeet.prepare(self.root)
        self.assertEqual((self.root / "manifest.json").read_bytes(), before)
        (self.root / prepare_parakeet.MODEL).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "refusing replacement"):
            prepare_parakeet.prepare(self.root)
        self.assertEqual((self.root / prepare_parakeet.MODEL).read_bytes(), b"corrupt")

    def test_bad_download_is_not_published_and_partial_file_is_removed(self):
        with patch.object(prepare_parakeet, "urlopen", return_value=io.BytesIO(b"bad")):
            with self.assertRaisesRegex(ValueError, "checksum/size"):
                prepare_parakeet.prepare(self.root)
        self.assertFalse((self.root / prepare_parakeet.MODEL).exists())
        self.assertFalse((self.root / (prepare_parakeet.MODEL + ".part")).exists())
        self.assertFalse((self.root / "manifest.json").exists())

    def test_license_changes_cannot_be_silently_reblessed(self):
        with patch.object(prepare_parakeet, "urlopen", side_effect=self.response):
            prepare_parakeet.prepare(self.root)
        original = json.loads((self.root / "manifest.json").read_text())
        (self.root / "LICENSE").write_text("changed")
        with self.assertRaisesRegex(ValueError, "provenance changed"):
            prepare_parakeet.prepare(self.root)
        self.assertEqual(json.loads((self.root / "manifest.json").read_text()), original)


if __name__ == "__main__":
    unittest.main()
