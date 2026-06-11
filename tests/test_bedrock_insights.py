import json
from io import BytesIO
from unittest import TestCase, main

from lead_analytics.bedrock_insights import (
    BedrockInsightConfig,
    generate_project_insights,
)


class FakeBedrockClient:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        response = {"content": [{"type": "text", "text": self.text}]}
        return {"body": BytesIO(json.dumps(response).encode("utf-8"))}


class BedrockInsightsTest(TestCase):
    def test_generates_structured_insights_from_claude_json(self):
        client = FakeBedrockClient(
            json.dumps(
                {
                    "executive_summary": "Pipeline is improving, but partner activity is uneven.",
                    "risks": ["Inactive partners may reduce coverage."],
                    "opportunities": ["Budget objections can be addressed with ROI proof."],
                    "recommended_actions": ["Create a reactivation plan for inactive partners."],
                }
            )
        )

        result = generate_project_insights(
            {"metrics": {"overall_conversion_rate": 0.42}},
            config=BedrockInsightConfig(model_id="test-model", region_name="us-east-1"),
            client=client,
        )

        self.assertEqual(
            result["executive_summary"],
            "Pipeline is improving, but partner activity is uneven.",
        )
        self.assertEqual(result["risks"], ["Inactive partners may reduce coverage."])
        self.assertEqual(client.calls[0]["modelId"], "test-model")

        payload = json.loads(client.calls[0]["body"])
        self.assertEqual(payload["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_accepts_json_wrapped_in_code_fence(self):
        client = FakeBedrockClient(
            """```json
{
  "executive_summary": "Healthy trend.",
  "risks": [],
  "opportunities": ["Improve partner follow-up."],
  "recommended_actions": ["Review weekly conversion movement."]
}
```"""
        )

        result = generate_project_insights(
            {"conversion_trends": []},
            config=BedrockInsightConfig(model_id="test-model"),
            client=client,
        )

        self.assertEqual(result["opportunities"], ["Improve partner follow-up."])


if __name__ == "__main__":
    main()
