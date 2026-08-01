import unittest

from ai_credit_limit.parsers import parse_usage_json, parse_usage_text


class ParserTest(unittest.TestCase):
    def test_parse_screenshot_like_text(self):
        parsed = parse_usage_text("1 周\n升级至 Pro\n44%  8月7日\n1 次可用重置")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.percent_used, 44)
        self.assertEqual(parsed.period_label, "1 周")
        self.assertEqual(parsed.reset_label, "8月7日")

    def test_parse_structured_percent_json(self):
        parsed = parse_usage_json(
            '{"quota": {"usage_percent": 0.72, "period": "weekly", "resets_at": "2026-08-07T00:00:00"}}'
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.percent_used, 72)
        self.assertEqual(parsed.period_label, "1 周")
        self.assertEqual(parsed.reset_label, "2026-08-07")

    def test_parse_used_limit_json(self):
        parsed = parse_usage_json('{"credits": {"used": 22, "limit": 50, "window": "month"}}')

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.percent_used, 44)
        self.assertEqual(parsed.period_label, "1 月")


if __name__ == "__main__":
    unittest.main()
