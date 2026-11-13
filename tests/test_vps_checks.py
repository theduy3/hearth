import unittest

from tools.verify_vps import speech_selection


class SpeechSelectionTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "whisper": "/opt/catthew-speech/models-joe/whisper",
            "voice": "/opt/catthew-speech/models-joe/voices/en/en_US/joe/medium/en_US-joe-medium.onnx",
            "repo": "Systran/faster-whisper-base.en",
            "pinned": True,
        }

    def test_exact_process_arguments_and_pinned_model_are_required(self):
        self.assertTrue(all(speech_selection(self.metadata).values()))
        for changes in ({"whisper": self.metadata["whisper"] + "-small"},
                        {"repo": "Systran/faster-whisper-small.en"},
                        {"pinned": False}, {"whisper": None}):
            with self.subTest(changes=changes):
                self.assertFalse(speech_selection({**self.metadata, **changes})["whisper_base_selected"])

    def test_voice_path_prefix_cannot_pass_as_selected_joe(self):
        self.metadata["voice"] += ".different"
        self.assertFalse(speech_selection(self.metadata)["male_voice_selected"])


if __name__ == "__main__":
    unittest.main()
