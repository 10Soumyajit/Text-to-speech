import unittest
import json
import os
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from app import app, SHEETAL_VOICE_ID, VOICE_NAME, AUDIO_CACHE

class TestTTSApplication(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_index_page_title_and_elements(self):
        """Verify the web page loads with title 'Text To Speech (Sheetal\'s Voice)' and necessary IDs."""
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        # 1. Title verification
        self.assertIn("<title>Text To Speech (Sheetal's Voice)</title>", html)
        self.assertIn("Text To Speech (Sheetal's Voice)", html)

        # 2. Key Interactive Elements & Unique IDs verification
        self.assertIn('id="input-text"', html)
        self.assertIn('id="btn-generate"', html)
        self.assertIn('id="btn-regenerate"', html)
        self.assertIn('id="btn-download"', html)
        self.assertIn('id="audio-preview"', html)
        self.assertIn('id="error-banner"', html)
        self.assertIn('id="credit-banner"', html)
        self.assertIn(SHEETAL_VOICE_ID, html)
        self.assertIn(VOICE_NAME, html)

    def test_02_voice_info_endpoint(self):
        """Verify the voice-info API returns Sheetal's voice details and ID."""
        response = self.app.get("/api/voice-info")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["voice_name"], "Sheetal")
        self.assertEqual(data["voice_id"], "b219f9f8d8e6455e85e470949d680229")
        self.assertTrue(data["has_api_key"])

    def test_03_empty_text_validation(self):
        """Verify empty input fails with specific 400 error message."""
        response = self.app.post("/api/generate", json={"text": ""})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "VALIDATION_EMPTY")
        self.assertIn("Text input is required", data["error"])

    def test_04_whitespace_only_validation(self):
        """Verify whitespace-only input fails with specific 400 error message."""
        response = self.app.post("/api/generate", json={"text": "   \n\t   "})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "VALIDATION_WHITESPACE")
        self.assertIn("cannot consist only of spaces", data["error"])

    def test_05_character_limit_validation(self):
        """Verify inputs exceeding character limit fail with specific 400 error message."""
        long_text = "A" * 3001
        response = self.app.post("/api/generate", json={"text": long_text})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "VALIDATION_LENGTH")

    def test_06_credit_exhaustion_error_notification(self):
        """Verify that when HeyGen returns credit exhaustion message, the user is specifically notified."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "HTTP status: 402\nHeyGen response: {'message': 'insufficient credits'}"
        mock_proc.stderr = ""

        with patch("subprocess.run", return_value=mock_proc):
            response = self.app.post("/api/generate", json={"text": "Test speech."})
            self.assertEqual(response.status_code, 402)
            data = json.loads(response.data)
            self.assertFalse(data["success"])
            self.assertEqual(data["error_type"], "CREDITS_EXHAUSTED")
            self.assertIn("credits are exhausted", data["error"].lower())

    def test_07_audio_preview_and_download_flow(self):
        """Verify audio streaming for preview and separate attachment download header."""
        test_audio_bytes = b"RIFF....WAVEfmt ....data...."

        def side_effect(cmd, **kwargs):
            # Write fake audio to output path
            output_idx = cmd.index("--output") + 1
            out_path = Path(cmd[output_idx])
            out_path.write_bytes(test_audio_bytes)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "HTTP status: 200\nDuration: 2.5 seconds\nSuccess: saved " + str(out_path)
            mock_res.stderr = ""
            return mock_res

        with patch("subprocess.run", side_effect=side_effect):
            # Standard generation
            res = self.app.post("/api/generate", json={"text": "Hello Sheetal"})
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertTrue(data["success"])
            audio_id = data["audio_id"]

            # Preview endpoint: stream only, no attachment header, anti-cache headers present
            preview_res = self.app.get(f"/api/audio/{audio_id}")
            self.assertEqual(preview_res.status_code, 200)
            self.assertEqual(preview_res.mimetype, "audio/wav")
            self.assertNotIn("attachment", preview_res.headers.get("Content-Disposition", ""))
            self.assertIn("no-store", preview_res.headers.get("Cache-Control", ""))

            # Download endpoint: provides Content-Disposition attachment header
            dl_res = self.app.get(f"/api/download/{audio_id}")
            self.assertEqual(dl_res.status_code, 200)
            self.assertIn("attachment", dl_res.headers.get("Content-Disposition", ""))
            self.assertIn(f"sheetal_tts_{audio_id[:8]}.wav", dl_res.headers.get("Content-Disposition", ""))

    def test_08_regenerate_force_new_argument(self):
        """Verify regenerate passes --force-new flag in the CLI command."""
        test_audio_bytes = b"RIFF....WAVEfmt ....data_regenerated...."

        executed_cmds = []
        def side_effect(cmd, **kwargs):
            executed_cmds.append(list(cmd))
            output_idx = cmd.index("--output") + 1
            out_path = Path(cmd[output_idx])
            out_path.write_bytes(test_audio_bytes)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = "Force new: True\nDuration: 2.8 seconds\nSuccess: saved " + str(out_path)
            mock_res.stderr = ""
            return mock_res

        with patch("subprocess.run", side_effect=side_effect):
            res = self.app.post("/api/generate", json={"text": "Hello Sheetal", "force_new": True})
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertTrue(data["force_new"])

            # Verify --force-new was passed in the subprocess command
            last_cmd = executed_cmds[-1]
            self.assertIn("--force-new", last_cmd)

if __name__ == "__main__":
    unittest.main()
