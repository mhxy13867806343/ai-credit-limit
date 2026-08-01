import unittest

from ai_credit_limit.antigravity_account import parse_models_usage_text


class AntigravityAccountTest(unittest.TestCase):
    def test_parse_models_usage_text(self):
        usage = parse_models_usage_text(
            """
            Models & Usage
            Plan
            Your Plan: Google AI Pro
            Gemini Models
            Weekly Limit
            You have used some of your weekly limit, it will fully refresh in 5 days, 9 hours.
            91%
            Five Hour Limit
            You have used some of your 5-hour limit, it will fully refresh in 2 hours, 22 minutes.
            82%
            Claude and GPT models
            Weekly Limit
            100%
            Five Hour Limit
            100%
            """
        )

        self.assertEqual(usage.plan_label, "GOOGLE AI PRO")
        self.assertEqual(len(usage.windows), 4)
        self.assertEqual(usage.windows[0].group, "Gemini 模型")
        self.assertEqual(usage.windows[0].label, "周额度")
        self.assertEqual(usage.windows[0].used_percent, 91)
        self.assertEqual(usage.windows[0].reset_label, "5天9小时后")


if __name__ == "__main__":
    unittest.main()
