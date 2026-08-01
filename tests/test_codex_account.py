import unittest

from ai_credit_limit.codex_account import parse_rate_limits_response


class CodexAccountTest(unittest.TestCase):
    def test_parse_account_rate_limits_response(self):
        usage = parse_rate_limits_response(
            {
                "id": 2601,
                "result": {
                    "rateLimitsByLimitId": {
                        "codex": {
                            "planType": "plus",
                            "primary": {
                                "usedPercent": 69,
                                "windowDurationMins": 10080,
                                "resetsAt": 1784684460,
                            },
                            "secondary": None,
                        }
                    }
                },
            }
        )

        self.assertEqual(usage.plan_type, "plus")
        self.assertEqual(len(usage.windows), 1)
        self.assertEqual(usage.windows[0].used_percent, 69)
        self.assertEqual(usage.windows[0].window_minutes, 10080)


if __name__ == "__main__":
    unittest.main()
