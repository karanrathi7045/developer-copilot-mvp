from unittest import TestCase, main
from unittest.mock import patch

from lead_analytics.main import create_project_insights


class ProjectInsightsEndpointTest(TestCase):
    def test_accepts_direct_analytics_json(self):
        expected = {
            "executive_summary": "Conversion is improving.",
            "risks": ["Partner activity is uneven."],
            "opportunities": ["Address budget objections."],
            "recommended_actions": ["Create partner reactivation plan."],
        }

        with patch("lead_analytics.main.generate_project_insights", return_value=expected) as mocked:
            response = create_project_insights({"metrics": {"overall_conversion_rate": 0.42}})

        self.assertEqual(response, expected)
        mocked.assert_called_once()
        self.assertEqual(
            mocked.call_args.args[0],
            {"metrics": {"overall_conversion_rate": 0.42}},
        )

    def test_accepts_wrapped_analytics_json(self):
        expected = {
            "executive_summary": "Pipeline needs attention.",
            "risks": [],
            "opportunities": [],
            "recommended_actions": [],
        }

        with patch("lead_analytics.main.generate_project_insights", return_value=expected) as mocked:
            response = create_project_insights(
                {
                    "project_analytics": {"metrics": {"overall_conversion_rate": 0.25}},
                    "model_id": "test-model",
                    "aws_region": "us-west-2",
                }
            )

        self.assertEqual(response, expected)
        self.assertEqual(
            mocked.call_args.args[0],
            {"metrics": {"overall_conversion_rate": 0.25}},
        )
        self.assertEqual(mocked.call_args.kwargs["config"].model_id, "test-model")


if __name__ == "__main__":
    main()
