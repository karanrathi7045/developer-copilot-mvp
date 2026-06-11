import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from developer_copilot.ai import answer_question, generate_action
from developer_copilot.briefings import create_daily_briefing
from developer_copilot.config import Settings
from developer_copilot.data_sources import (
    load_project_data,
    select_developer_data,
    select_developer_data_by_phone,
)
from developer_copilot.twilio_webhook import answer_whatsapp_question, twiml_message
from developer_copilot.whatsapp import send_whatsapp_briefing, _twilio_form
from scripts.load_snowflake_seed import split_sql


class DeveloperCopilotTest(TestCase):
    def test_generates_mock_daily_briefing_with_audio(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                generated_audio_dir=Path(tmpdir) / "voice_notes",
                latest_briefing_path=Path(tmpdir) / "latest.json",
                scheduler_enabled=False,
            )

            briefing = create_daily_briefing(settings, send_whatsapp=False)

            self.assertIn("budget", briefing.summary_text.lower())
            self.assertEqual(briefing.data_source, "mock_csv")
            self.assertEqual(briefing.developer["developer_name"], "Karan Rathi")
            self.assertTrue(briefing.audio_path)
            self.assertTrue(Path(briefing.audio_path).exists())
            self.assertEqual(briefing.voice_status["provider"], "mock")

    def test_answers_questions_from_mock_project_data(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = answer_question(settings, project_data, "What is the top objection?")

        self.assertEqual(result.model, "mock-reasoner")
        self.assertIn("budget", result.payload["answer"].lower())
        self.assertTrue(result.payload["evidence"])

    def test_generates_action_from_mock_project_data(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = generate_action(
            settings,
            project_data,
            {"target": "NorthStar Realty", "tone": "confident", "action_type": "cp_message"},
        )

        self.assertIn("NorthStar Realty", result.payload["cp_message"])
        self.assertTrue(result.payload["sales_talking_points"])
        self.assertTrue(result.payload["next_steps"])

    def test_mock_tables_have_100_rows_each(self):
        for path in [
            Path("data/developers.csv"),
            Path("data/leads.csv"),
            Path("data/projects.csv"),
            Path("data/inventory.csv"),
            Path("data/bookings.csv"),
            Path("data/channel_partner.csv"),
        ]:
            with self.subTest(path=path):
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 100)

    def test_snowflake_seed_contains_table_loads(self):
        statements = split_sql(Path("data/snowflake_seed.sql").read_text(encoding="utf-8"))

        self.assertEqual(len([item for item in statements if item.startswith("CREATE OR REPLACE TABLE")]), 6)
        self.assertEqual(len([item for item in statements if item.startswith("INSERT INTO")]), 6)

    def test_twilio_mock_uses_developer_phone(self):
        status = send_whatsapp_briefing(
            settings=Settings(scheduler_enabled=False),
            summary_text="Demo briefing",
            developer={
                "developer_name": "Karan Rathi",
                "country_code": "91",
                "developer_phone": "7045706453",
            },
            audio_path=None,
            audio_url=None,
            audio_mime_type=None,
        )

        self.assertEqual(status["provider"], "twilio-mock")
        self.assertEqual(status["recipient"], "whatsapp:+917045706453")

    def test_selects_developer_by_whatsapp_phone(self):
        settings = Settings(scheduler_enabled=False)
        project_data = load_project_data(settings)

        selected = select_developer_data_by_phone(project_data, "whatsapp:+917045706453")

        self.assertEqual(selected.developer["developer_name"], "Karan Rathi")
        self.assertTrue(selected.projects)
        self.assertTrue(selected.leads)

    def test_answers_whatsapp_question_with_twiml_safe_text(self):
        settings = Settings(scheduler_enabled=False)
        project_data = load_project_data(settings)

        result = answer_whatsapp_question(
            settings,
            project_data,
            "whatsapp:+917045706453",
            "What is the top objection?",
        )
        xml = twiml_message(result["reply"])

        self.assertEqual(result["developer"]["developer_name"], "Karan Rathi")
        self.assertIn("budget", result["reply"].lower())
        self.assertNotIn("Evidence:", result["reply"])
        self.assertIn("<Response><Message>", xml)
        self.assertIn("</Message></Response>", xml)

    def test_whatsapp_questions_route_to_different_answers(self):
        settings = Settings(scheduler_enabled=False)
        project_data = load_project_data(settings)
        questions = [
            "Hi",
            "What inventory should I push today?",
            "How much brokerage is booked?",
            "What should I tell CPs today?",
        ]

        replies = [
            answer_whatsapp_question(
                settings,
                project_data,
                "whatsapp:+917045706453",
                question,
            )["reply"]
            for question in questions
        ]

        self.assertEqual(len(set(replies)), len(replies))
        self.assertIn("Ask me about", replies[0])
        self.assertIn("Inventory to push", replies[1])
        self.assertIn("Brokerage booked", replies[2])
        self.assertIn("Talking point", replies[3])

    def test_voice_note_without_transcription_config_gets_friendly_reply(self):
        settings = Settings(scheduler_enabled=False)
        project_data = load_project_data(settings)

        result = answer_whatsapp_question(
            settings,
            project_data,
            "whatsapp:+917045706453",
            "",
            media_url="https://api.twilio.com/fake-media",
            media_content_type="audio/ogg",
        )

        self.assertIn("voice note", result["reply"])
        self.assertIn("transcribe", result["reply"])

    def test_twilio_form_attaches_public_audio_url(self):
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "briefing.mp3"
            audio_path.write_bytes(b"fake")
            settings = Settings(
                base_url="https://demo.loca.lt",
                twilio_send_audio=True,
                twilio_whatsapp_from="whatsapp:+14155238886",
                scheduler_enabled=False,
            )

            form = _twilio_form(
                settings,
                "Briefing text",
                "whatsapp:+917045706453",
                "/audio/briefing.mp3",
                audio_path,
                "audio/mpeg",
            )

        self.assertEqual(form["MediaUrl"], "https://demo.loca.lt/audio/briefing.mp3")


if __name__ == "__main__":
    main()
