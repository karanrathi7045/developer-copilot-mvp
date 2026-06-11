from datetime import datetime, timezone
from unittest import TestCase, main

from lead_analytics.analytics import (
    Dataset,
    conversion_trends,
    inactive_channel_partners,
    most_frequent_objections,
    structured_summary,
)


class AnalyticsTest(TestCase):
    def setUp(self):
        self.dataset = Dataset(
            leads=[
                {
                    "lead_id": "1",
                    "channel_partner": "Alpha",
                    "created_at": "2026-01-01",
                    "status": "converted",
                },
                {
                    "lead_id": "2",
                    "channel_partner": "Alpha",
                    "created_at": "2026-01-15",
                    "status": "lost",
                },
                {
                    "lead_id": "3",
                    "channel_partner": "Beta",
                    "created_at": "2026-02-01",
                    "converted_at": "2026-02-12",
                },
            ],
            conversations=[
                {
                    "lead_id": "1",
                    "channel_partner": "Alpha",
                    "last_activity_at": "2026-05-30",
                    "objection": "Budget",
                },
                {
                    "lead_id": "2",
                    "channel_partner": "Alpha",
                    "last_activity_at": "2026-05-31",
                    "message": "This is too expensive right now.",
                },
                {
                    "lead_id": "3",
                    "channel_partner": "Beta",
                    "last_activity_at": "2026-01-01",
                    "objection": "Timing",
                },
            ],
        )

    def test_counts_explicit_and_detected_objections(self):
        self.assertEqual(
            most_frequent_objections(self.dataset),
            [
                {"objection": "budget", "count": 2},
                {"objection": "timing", "count": 1},
            ],
        )

    def test_detects_inactive_partners(self):
        inactive = inactive_channel_partners(
            self.dataset,
            inactive_days=30,
            as_of=datetime(2026, 6, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]["channel_partner"], "Beta")

    def test_calculates_monthly_conversion_trends(self):
        self.assertEqual(
            conversion_trends(self.dataset, period="month"),
            [
                {"period": "2026-01", "leads": 2, "converted": 1, "conversion_rate": 0.5},
                {"period": "2026-02", "leads": 1, "converted": 1, "conversion_rate": 1.0},
            ],
        )

    def test_generates_structured_summary(self):
        summary = structured_summary(
            self.dataset,
            as_of=datetime(2026, 6, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(summary["metadata"]["lead_count"], 3)
        self.assertEqual(summary["metrics"]["overall_conversion_rate"], 0.6667)
        self.assertIn("most_frequent_objections", summary)


if __name__ == "__main__":
    main()
