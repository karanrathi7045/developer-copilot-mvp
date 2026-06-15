import csv
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from developer_copilot.ai import answer_question, generate_action
from developer_copilot.ai import _format_long_answer
from developer_copilot.briefings import create_daily_briefing
from developer_copilot.chat_history import append_chat_messages, load_chat_history
from developer_copilot.charts import create_question_chart
from developer_copilot.config import Settings
from developer_copilot.data_sources import (
    load_project_data,
    select_developer_data,
    select_developer_data_by_phone,
)
from developer_copilot.transcripts import load_voice_transcript, save_voice_transcript
from developer_copilot.transcription import TranscriptionResult
from developer_copilot.twilio_webhook import (
    answer_transcript_button,
    answer_whatsapp_question,
    send_whatsapp_followup_response,
    twiml_empty,
    twiml_message,
)
from developer_copilot.voice import VoiceResult
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

    def test_long_answers_are_formatted_as_bullets(self):
        answer = (
            "Last week had three important highlights. "
            "Bookings improved across 2 BHK demand. "
            "Budget remained the strongest buyer objection. "
            "Inactive channel partners need reactivation. "
            "Inventory push should focus on available 1 BHK units."
        )

        formatted = _format_long_answer(answer)

        self.assertIn("\n- Bookings improved", formatted)
        self.assertIn("\n- Budget remained", formatted)
        self.assertIn("\n- Inactive channel partners", formatted)

    def test_highlight_questions_force_bullets(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = answer_question(settings, project_data, "Give me the highlights of last week")

        self.assertIn("\n- ", result.payload["answer"])

    def test_project_performance_lists_each_project_status(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = answer_question(settings, project_data, "How is my project performing this week?")

        self.assertIn("Here are your project statuses:", result.payload["answer"])
        self.assertIn("- Ambrosia Heights Andheri West: Under Construction", result.payload["answer"])
        self.assertIn("- Orchid Residences Dadar: Pre-Launch", result.payload["answer"])
        self.assertNotIn("Planning: 5", result.payload["answer"])

    def test_project_performance_bypasses_llm_when_openai_is_configured(self):
        settings = Settings(openai_api_key="test-key", scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        with patch("developer_copilot.ai._call_openai_json") as openai_call:
            result = answer_question(settings, project_data, "How is my project performing this week?")

        openai_call.assert_not_called()
        self.assertEqual(result.model, "deterministic-project-status")
        self.assertIn("- Ambrosia Heights Andheri West: Under Construction", result.payload["answer"])

    def test_sv_to_booking_conversion_returns_visit_conversion(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = answer_question(settings, project_data, "What's my current SV to booking conversion rate?")

        self.assertEqual(result.model, "deterministic-sv-booking-conversion")
        self.assertIn("Site Visit to Booking conversion is 35%", result.payload["answer"])
        self.assertIn("7 of 20 completed site visits", result.payload["answer"])
        self.assertNotIn("agreement value", result.payload["answer"])

    def test_sv_to_booking_conversion_bypasses_llm_when_openai_is_configured(self):
        settings = Settings(openai_api_key="test-key", scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        with patch("developer_copilot.ai._call_openai_json") as openai_call:
            result = answer_question(settings, project_data, "How many visits turned into booking?")

        openai_call.assert_not_called()
        self.assertEqual(result.model, "deterministic-sv-booking-conversion")
        self.assertIn("7 of 20 completed site visits", result.payload["answer"])

    def test_fastest_bhk_configuration_uses_booking_velocity(self):
        settings = Settings(scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        result = answer_question(settings, project_data, "Which BHK configuration is moving fastest?")

        self.assertEqual(result.model, "deterministic-configuration-movement")
        self.assertIn("2 BHK is moving fastest", result.payload["answer"])
        self.assertIn("2 bookings", result.payload["answer"])
        self.assertIn("INR 2.96 Cr booked value", result.payload["answer"])
        self.assertIn("leads the tied group", result.payload["answer"])
        self.assertNotIn("Inventory to push", result.payload["answer"])

    def test_fastest_bhk_configuration_bypasses_llm_when_openai_is_configured(self):
        settings = Settings(openai_api_key="test-key", scheduler_enabled=False)
        project_data = select_developer_data(load_project_data(settings), 101)

        with patch("developer_copilot.ai._call_openai_json") as openai_call:
            result = answer_question(settings, project_data, "Which BHK configuration is moving fastest?")

        openai_call.assert_not_called()
        self.assertEqual(result.model, "deterministic-configuration-movement")
        self.assertIn("2 BHK is moving fastest", result.payload["answer"])

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

    def test_chat_history_persists_buildr_messages(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                chat_history_path=Path(tmpdir) / "chat_history.json",
                scheduler_enabled=False,
            )

            append_chat_messages(
                settings,
                [
                    {"role": "user", "content": "What is the top objection today?"},
                    {"role": "assistant", "content": "The top objection is budget."},
                ],
            )
            history = load_chat_history(settings)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["content"], "The top objection is budget.")

    def test_mock_tables_have_expected_row_counts(self):
        expected_counts = {
            Path("data/developers.csv"): 100,
            Path("data/leads.csv"): 1000,
            Path("data/projects.csv"): 100,
            Path("data/inventory.csv"): 100,
            Path("data/bookings.csv"): 100,
            Path("data/site_visits.csv"): 414,
            Path("data/channel_partner.csv"): 100,
        }
        for path, expected_count in expected_counts.items():
            with self.subTest(path=path):
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), expected_count)

    def test_leads_have_allowed_statuses_and_failed_objections_only(self):
        allowed_statuses = {
            "Claimed",
            "In CC",
            "Interested",
            "Meeting Done",
            "Visit Done",
            "Final Negotiation",
            "Booking Done",
            "Failed",
            "Junk",
        }

        with Path("data/leads.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(set(rows[0]), {"id", "name", "status", "project_id", "objection"})
        self.assertEqual({row["status"] for row in rows} - allowed_statuses, set())
        self.assertFalse([row for row in rows if row["status"] == "Failed" and not row["objection"]])
        self.assertFalse([row for row in rows if row["status"] != "Failed" and row["objection"]])

    def test_site_visits_cover_visit_done_negotiation_and_booking_leads(self):
        required_lead_statuses = {"Visit Done", "Final Negotiation", "Booking Done"}
        allowed_visit_statuses = {"scheduled", "done", "cancelled"}

        with Path("data/leads.csv").open(newline="", encoding="utf-8") as handle:
            leads = list(csv.DictReader(handle))
        with Path("data/bookings.csv").open(newline="", encoding="utf-8") as handle:
            bookings = list(csv.DictReader(handle))
        with Path("data/site_visits.csv").open(newline="", encoding="utf-8") as handle:
            site_visits = list(csv.DictReader(handle))

        self.assertEqual(set(site_visits[0]), {"id", "lead_id", "visit_date_time", "status", "visit_note"})
        self.assertEqual({row["status"] for row in site_visits} - allowed_visit_statuses, set())

        lead_ids = {row["id"] for row in leads}
        visit_lead_ids = {row["lead_id"] for row in site_visits}
        required_lead_ids = {
            row["id"] for row in leads
            if row["status"] in required_lead_statuses
        }
        booking_lead_ids = {row["lead_id"] for row in bookings}

        self.assertEqual(visit_lead_ids - lead_ids, set())
        self.assertEqual(required_lead_ids - visit_lead_ids, set())
        self.assertGreaterEqual(len(booking_lead_ids & visit_lead_ids) / len(booking_lead_ids), 0.9)

    def test_projects_have_distinct_names_and_allowed_stages(self):
        allowed_stages = {"Under Construction", "Pre-Launch", "Ready to Move In"}
        with Path("data/projects.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        names = [row["name"] for row in rows]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual({row["stage"] for row in rows} - allowed_stages, set())
        self.assertFalse([name for name in names if re.search(r"\s\d+$", name)])

    def test_snowflake_seed_contains_table_loads(self):
        statements = split_sql(Path("data/snowflake_seed.sql").read_text(encoding="utf-8"))

        self.assertEqual(len([item for item in statements if item.startswith("CREATE OR REPLACE TABLE")]), 7)
        self.assertEqual(len([item for item in statements if item.startswith("INSERT INTO")]), 7)

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

    def test_twiml_message_can_return_voice_media_only(self):
        xml = twiml_message(
            "This text is used only as a fallback.",
            "https://demo.loca.lt/audio/reply.mp3",
        )

        self.assertIn("<Response><Message><Media>", xml)
        self.assertIn("https://demo.loca.lt/audio/reply.mp3", xml)
        self.assertNotIn("This text is used only as a fallback.", xml)

    def test_twiml_message_can_return_text_with_chart_media(self):
        xml = twiml_message(
            "Here is the inventory analysis.",
            media_urls=["https://demo.loca.lt/charts/inventory.png"],
            include_body=True,
        )

        self.assertIn("Here is the inventory analysis.", xml)
        self.assertIn("<Media>https://demo.loca.lt/charts/inventory.png</Media>", xml)

    def test_twiml_message_splits_voice_and_chart_media(self):
        xml = twiml_message(
            "Spoken answer",
            media_urls=[
                "https://demo.loca.lt/audio/reply.mp3",
                "https://demo.loca.lt/charts/bookings.png",
            ],
            include_body=False,
        )

        self.assertEqual(xml.count("<Message>"), 2)
        self.assertIn("<Media>https://demo.loca.lt/audio/reply.mp3</Media>", xml)
        self.assertIn("<Media>https://demo.loca.lt/charts/bookings.png</Media>", xml)
        self.assertNotIn("Spoken answer", xml)

    def test_twiml_empty_acknowledges_voice_webhook_fast(self):
        self.assertEqual(twiml_empty(), '<?xml version="1.0" encoding="UTF-8"?><Response></Response>')

    def test_followup_sends_voice_and_chart_as_separate_messages(self):
        settings = Settings(
            twilio_enabled=True,
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_whatsapp_from="whatsapp:+14155238886",
            twilio_transcript_button_content_sid="HX123",
            scheduler_enabled=False,
        )
        project_data = load_project_data(Settings(scheduler_enabled=False))

        with (
            patch(
                "developer_copilot.twilio_webhook.answer_whatsapp_question",
                return_value={
                    "reply": "Booking analysis",
                    "reply_mode": "voice",
                    "reply_media_url": "https://demo.loca.lt/audio/reply.mp3",
                    "chart_media_url": "https://demo.loca.lt/charts/bookings.png",
                },
            ),
            patch(
                "developer_copilot.twilio_webhook._send_twilio_reply",
                side_effect=[
                    {"provider": "twilio", "sent": True, "message_sid": "audio"},
                    {"provider": "twilio", "sent": True, "message_sid": "chart"},
                    {"provider": "twilio", "sent": True, "message_sid": "transcript"},
                ],
            ) as send_reply,
        ):
            status = send_whatsapp_followup_response(
                settings,
                project_data,
                "whatsapp:+917045706453",
                "",
                media_url="https://api.twilio.com/fake-media",
                media_content_type="audio/ogg",
            )

        self.assertEqual(status["reply_mode"], "voice")
        self.assertTrue(status["chart_attached"])
        self.assertTrue(status["transcript_button_sent"])
        self.assertEqual(send_reply.call_count, 3)
        self.assertEqual(send_reply.call_args_list[0].kwargs["media_url"], "https://demo.loca.lt/audio/reply.mp3")
        self.assertEqual(send_reply.call_args_list[1].kwargs["media_url"], "https://demo.loca.lt/charts/bookings.png")
        self.assertEqual(send_reply.call_args_list[2].kwargs["content_sid"], "HX123")

    def test_followup_sends_transcript_button_for_voice_question(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                base_url="https://demo.loca.lt",
                generated_transcript_dir=Path(tmpdir),
                twilio_enabled=True,
                twilio_account_sid="AC123",
                twilio_auth_token="token",
                twilio_whatsapp_from="whatsapp:+14155238886",
                twilio_transcript_button_content_sid="HX123",
                scheduler_enabled=False,
            )
            project_data = load_project_data(Settings(scheduler_enabled=False))

            with (
                patch(
                    "developer_copilot.twilio_webhook.answer_whatsapp_question",
                    return_value={
                        "reply": "Inventory to push today is the 1 BHK stock at Sky Heights.",
                        "reply_mode": "voice",
                        "reply_media_url": "https://demo.loca.lt/audio/reply.mp3",
                        "developer": {"developer_name": "Karan Rathi", "id": 101},
                        "transcribed_question": "What inventory should I push today?",
                    },
                ),
                patch(
                    "developer_copilot.twilio_webhook._send_twilio_reply",
                    side_effect=[
                        {"provider": "twilio", "sent": True, "message_sid": "audio"},
                        {"provider": "twilio", "sent": True, "message_sid": "transcript"},
                    ],
                ) as send_reply,
            ):
                status = send_whatsapp_followup_response(
                    settings,
                    project_data,
                    "whatsapp:+917045706453",
                    "",
                    media_url="https://api.twilio.com/fake-media",
                    media_content_type="audio/ogg",
                )

            transcript_variables = send_reply.call_args_list[1].kwargs["content_variables"]
            transcript_payload = transcript_variables["1"]
            transcript_id = transcript_payload.removeprefix("show_transcript:")
            saved = load_voice_transcript(settings, transcript_id)

        self.assertEqual(status["reply_mode"], "voice")
        self.assertTrue(status["transcript_button_sent"])
        self.assertEqual(send_reply.call_count, 2)
        self.assertEqual(send_reply.call_args_list[1].kwargs["content_sid"], "HX123")
        self.assertTrue(transcript_payload.startswith("show_transcript:"))
        self.assertEqual(saved["source"], "buildr_voice_reply")
        self.assertEqual(saved["transcript"], "Inventory to push today is the 1 BHK stock at Sky Heights.")

    def test_transcript_button_click_returns_transcript_in_chat(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                generated_transcript_dir=Path(tmpdir),
                scheduler_enabled=False,
            )
            link = save_voice_transcript(
                settings,
                "Give me booking analysis",
                {"developer_name": "Karan Rathi", "id": 101},
                whatsapp_from="whatsapp:+917045706453",
            )

            reply = answer_transcript_button(
                settings,
                "whatsapp:+917045706453",
                button_payload=f"show_transcript:{link['id']}",
                button_text="Show Transcript",
            )
            fallback_reply = answer_transcript_button(
                settings,
                "whatsapp:+917045706453",
                button_payload=None,
                button_text="Show Transcript",
            )

        self.assertEqual(reply, "Transcript:\nGive me booking analysis")
        self.assertEqual(fallback_reply, "Transcript:\nGive me booking analysis")

    def test_voice_transcript_round_trip(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                base_url="https://demo.loca.lt",
                generated_transcript_dir=Path(tmpdir),
                scheduler_enabled=False,
            )

            link = save_voice_transcript(
                settings,
                "Give me booking analysis",
                {"developer_name": "Karan Rathi", "id": 101},
            )
            saved = load_voice_transcript(settings, link["id"])

        self.assertTrue(link["url"].startswith("https://demo.loca.lt/transcripts/"))
        self.assertEqual(saved["developer"]["name"], "Karan Rathi")
        self.assertEqual(saved["transcript"], "Give me booking analysis")

    def test_inventory_question_generates_chart_png(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(generated_chart_dir=Path(tmpdir), scheduler_enabled=False)
            project_data = select_developer_data(load_project_data(settings), 101)

            chart = create_question_chart(settings, project_data, "Show me inventory analysis")

            self.assertIsNotNone(chart)
            self.assertEqual(chart.mime_type, "image/png")
            self.assertEqual(chart.chart_type, "inventory")
            self.assertTrue(chart.chart_path.exists())
            self.assertGreater(chart.chart_path.stat().st_size, 1024)

    def test_simple_topic_question_does_not_generate_chart(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(generated_chart_dir=Path(tmpdir), scheduler_enabled=False)
            project_data = select_developer_data(load_project_data(settings), 101)

            chart = create_question_chart(settings, project_data, "What is the top objection today?")

        self.assertIsNone(chart)

    def test_whatsapp_text_analysis_can_attach_chart(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                base_url="https://demo.loca.lt",
                generated_chart_dir=Path(tmpdir),
                scheduler_enabled=False,
            )
            project_data = load_project_data(settings)

            result = answer_whatsapp_question(
                settings,
                project_data,
                "whatsapp:+917045706453",
                "Show me inventory analysis",
            )

        self.assertEqual(result["reply_mode"], "text")
        self.assertIn("chart", result)
        self.assertEqual(result["chart"]["type"], "inventory")
        self.assertEqual(result["chart_media_url"].split("/charts/", 1)[0], "https://demo.loca.lt")

    def test_whatsapp_simple_question_does_not_attach_chart(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(
                base_url="https://demo.loca.lt",
                generated_chart_dir=Path(tmpdir),
                scheduler_enabled=False,
            )
            project_data = load_project_data(settings)

            result = answer_whatsapp_question(
                settings,
                project_data,
                "whatsapp:+917045706453",
                "What is the top objection today?",
            )

        self.assertEqual(result["reply_mode"], "text")
        self.assertNotIn("chart", result)
        self.assertNotIn("chart_media_url", result)

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

    def test_voice_question_gets_voice_reply_when_audio_is_public(self):
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "reply.mp3"
            audio_path.write_bytes(b"fake audio")
            settings = Settings(
                base_url="https://demo.loca.lt",
                generated_audio_dir=Path(tmpdir),
                scheduler_enabled=False,
            )
            project_data = load_project_data(settings)

            with (
                patch(
                    "developer_copilot.twilio_webhook.transcribe_twilio_media",
                    return_value=TranscriptionResult(
                        text="What inventory should I push today?",
                        ok=True,
                        detail="Voice note transcribed in test",
                    ),
                ),
                patch(
                    "developer_copilot.twilio_webhook.create_voice_note",
                    return_value=VoiceResult(
                        audio_path=audio_path,
                        audio_url="/audio/reply.mp3",
                        mime_type="audio/mpeg",
                        status={"provider": "test", "ok": True},
                    ),
                ),
            ):
                result = answer_whatsapp_question(
                    settings,
                    project_data,
                    "whatsapp:+917045706453",
                    "",
                    media_url="https://api.twilio.com/fake-media",
                    media_content_type="audio/ogg",
                )

        self.assertEqual(result["reply_mode"], "voice")
        self.assertEqual(result["reply_media_url"], "https://demo.loca.lt/audio/reply.mp3")
        self.assertEqual(result["transcribed_question"], "What inventory should I push today?")
        self.assertIn("Inventory to push", result["reply"])

    def test_voice_note_without_transcription_config_gets_friendly_reply(self):
        with TemporaryDirectory() as tmpdir:
            settings = Settings(generated_audio_dir=Path(tmpdir), scheduler_enabled=False)
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
        self.assertIn("could not understand", result["reply"])

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
