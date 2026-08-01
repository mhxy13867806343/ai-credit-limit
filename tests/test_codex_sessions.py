import json
import tempfile
import unittest
from pathlib import Path

from ai_credit_limit.codex_sessions import scan_codex_tokens


class CodexSessionsTest(unittest.TestCase):
    def test_scan_token_count_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "rollout.jsonl"
            first = {
                "timestamp": "2026-08-01T01:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 10,
                            "output_tokens": 5,
                        }
                    },
                },
            }
            second = {
                "timestamp": "2026-08-01T02:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 160,
                            "cached_input_tokens": 40,
                            "output_tokens": 9,
                        }
                    },
                },
            }
            session.write_text(
                json.dumps(first, separators=(",", ":")) + "\n"
                + json.dumps(second, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            _today, total, scanned_files = scan_codex_tokens(root, days=365)

        self.assertEqual(scanned_files, 1)
        self.assertEqual(total.input_tokens, 160)
        self.assertEqual(total.cached_input_tokens, 40)
        self.assertEqual(total.output_tokens, 9)


if __name__ == "__main__":
    unittest.main()
