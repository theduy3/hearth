import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.flash_note4c import verify_artifact


class FirmwareArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            'board': 'Note4C', 'target': 'esp32s3', 'flash_bytes': 16777216,
            'source_commit': 'a' * 40,
            'flash_settings': {'flash_mode': 'dio', 'flash_size': '16MB', 'flash_freq': '80m'},
            'initial_nvs_erase': {'offset': '0x9000', 'bytes': '0x26000'}, 'files': {},
        }
        for offset, name in [('0x0', 'bootloader/bootloader.bin'), ('0x8000', 'partition_table/partition-table.bin'), ('0x30000', 'hearth.bin')]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'public build data')
            self.manifest['files'][offset] = {'file': name, 'bytes': 17, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.save()

    def save(self):
        (self.root / 'note4c-manifest.json').write_text(json.dumps(self.manifest))

    def test_exact_artifact_is_verified_without_hardware(self):
        self.assertEqual(verify_artifact(self.root, 'a' * 40)[::2], ['0x0', '0x8000', '0x30000'])

    def test_corruption_and_wrong_revision_refused(self):
        with self.assertRaises(ValueError):
            verify_artifact(self.root, 'b' * 40)
        (self.root / 'hearth.bin').write_bytes(b'changed build data')
        with self.assertRaises(ValueError):
            verify_artifact(self.root, 'a' * 40)

    def test_redirected_file_and_extra_region_refused(self):
        self.manifest['files']['0x30000']['file'] = '../secret'
        self.save()
        with self.assertRaises(ValueError):
            verify_artifact(self.root, 'a' * 40)
        self.manifest['files']['0x30000']['file'] = 'hearth.bin'
        self.manifest['files']['0x9000'] = dict(self.manifest['files']['0x30000'])
        self.save()
        with self.assertRaises(ValueError):
            verify_artifact(self.root, 'a' * 40)

    def test_symlink_refused_even_when_content_is_valid(self):
        (self.root / 'hearth.bin').unlink()
        (self.root / 'hearth.bin').symlink_to(self.root / 'bootloader/bootloader.bin')
        with self.assertRaises(ValueError):
            verify_artifact(self.root, 'a' * 40)
