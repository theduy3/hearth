"""Reject truncated and ambiguous audio before speech models see it."""
import struct
import unittest

from hub.wavutil import parse_wav, wrap_pcm16


class AudioValidationTests(unittest.TestCase):
    def test_truncated_data_chunk_is_rejected(self):
        valid = wrap_pcm16(b"\0\0" * 800)
        with self.assertRaises(ValueError):
            parse_wav(valid[:-2])

    def test_truncated_format_chunk_is_rejected_as_validation_error(self):
        invalid = b"RIFF" + struct.pack("<I", 30) + b"WAVEfmt " + struct.pack("<I", 2) + b"\x01\x00data" + struct.pack("<I", 8) + b"\0" * 8
        with self.assertRaises(ValueError):
            parse_wav(invalid)

    def test_odd_pcm_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_wav(wrap_pcm16(b"\0" * 401))


if __name__ == "__main__":
    unittest.main()
