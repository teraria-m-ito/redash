from unittest import TestCase
from unittest.mock import Mock, patch

from redash.ai_client import AiChatError, call_ai_chat, get_org_ai_temperature
from redash.ai_query import (
    build_correction_message,
    dry_run_query,
    generate_query,
    generate_with_validation,
    prompt_tokens,
)


class TestPromptTokens(TestCase):
    def test_japanese_uses_bigrams(self):
        tokens = prompt_tokens("月別の売上")
        self.assertIn("月別", tokens)
        self.assertIn("売上", tokens)

    def test_skips_hiragana_only_bigrams(self):
        self.assertNotIn("して", prompt_tokens("売上を出して"))

    def test_ascii_words_are_lowercased(self):
        self.assertEqual(prompt_tokens("Orders の amount"), {"orders", "amount"})


class TestCallAiChatError(TestCase):
    def call_with_error_response(self, status_code, payload):
        response = Mock(status_code=status_code, text="")
        if isinstance(payload, Exception):
            response.json.side_effect = payload
        else:
            response.json.return_value = payload
        with patch("redash.ai_client.requests.post", return_value=response):
            with self.assertRaises(AiChatError) as context:
                call_ai_chat("https://api.openai.com/v1", "key", "gpt-4o-mini", [])
        return context.exception.message

    def test_appends_openai_error_message(self):
        message = self.call_with_error_response(400, {"error": {"message": "Unsupported value: 'temperature'"}})
        self.assertEqual(message, "AIサービスがエラーを返しました。（HTTP 400）\nUnsupported value: 'temperature'")

    def test_appends_ollama_error_message(self):
        message = self.call_with_error_response(404, {"error": "model 'llama3.2' not found"})
        self.assertEqual(message, "AIサービスがエラーを返しました。（HTTP 404）\nmodel 'llama3.2' not found")

    def test_status_only_when_body_is_not_json(self):
        message = self.call_with_error_response(500, ValueError("not json"))
        self.assertEqual(message, "AIサービスがエラーを返しました。（HTTP 500）")


class TestGetOrgAiTemperature(TestCase):
    def org_with(self, value):
        org = Mock()
        org.get_setting.return_value = value
        return org

    def test_uses_setting(self):
        self.assertEqual(get_org_ai_temperature(self.org_with(0.5)), 0.5)

    def test_parses_string(self):
        self.assertEqual(get_org_ai_temperature(self.org_with("0.3")), 0.3)

    def test_defaults_when_invalid(self):
        self.assertEqual(get_org_ai_temperature(self.org_with(None)), 0.1)
        self.assertEqual(get_org_ai_temperature(self.org_with("abc")), 0.1)

    def test_clamps_out_of_range(self):
        self.assertEqual(get_org_ai_temperature(self.org_with(-1)), 0.0)
        self.assertEqual(get_org_ai_temperature(self.org_with(5)), 2.0)


class TestGenerateWithValidation(TestCase):
    def test_build_correction_message_handles_braces_in_error(self):
        message = build_correction_message('invalid input syntax near "{"', "SELECT 1", "test")
        self.assertIn('invalid input syntax near "{"', message)
        self.assertIn("SELECT 1", message)

    @patch("redash.ai_query.call_ai_chat")
    @patch("redash.ai_query.dry_run_query")
    def test_returns_on_first_success(self, mock_dry_run, mock_chat):
        mock_chat.return_value = '{"query": "SELECT 1", "message": "ok"}'
        mock_dry_run.return_value = None
        data_source = Mock()

        query, message, validated = generate_with_validation(
            api_url="https://api.openai.com/v1",
            api_key="key",
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "test"}],
            data_source=data_source,
            user=None,
            prompt="test",
            extract_query_payload=lambda content: ("SELECT 1", "ok"),
        )

        self.assertEqual(query, "SELECT 1")
        self.assertTrue(validated)
        self.assertEqual(mock_chat.call_count, 1)
        self.assertEqual(mock_chat.call_args[1]["temperature"], 0.1)

    @patch("redash.ai_query.call_ai_chat")
    @patch("redash.ai_query.dry_run_query")
    def test_passes_temperature(self, mock_dry_run, mock_chat):
        mock_chat.return_value = '{"query": "SELECT 1", "message": "ok"}'
        mock_dry_run.return_value = None

        generate_with_validation(
            api_url="https://api.openai.com/v1",
            api_key="key",
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "test"}],
            data_source=Mock(),
            user=None,
            prompt="test",
            extract_query_payload=lambda content: ("SELECT 1", "ok"),
            temperature=0.8,
        )

        self.assertEqual(mock_chat.call_args[1]["temperature"], 0.8)

    @patch("redash.ai_query.call_ai_chat")
    @patch("redash.ai_query.dry_run_query")
    def test_retries_on_validation_error(self, mock_dry_run, mock_chat):
        mock_chat.side_effect = [
            '{"query": "SELECT bad", "message": "first"}',
            '{"query": "SELECT 1", "message": "fixed"}',
        ]
        mock_dry_run.side_effect = ["syntax error", None]
        data_source = Mock()

        query, message, validated = generate_with_validation(
            api_url="https://api.openai.com/v1",
            api_key="key",
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "test"}],
            data_source=data_source,
            user=None,
            prompt="test",
            extract_query_payload=lambda content: {
                '{"query": "SELECT bad", "message": "first"}': ("SELECT bad", "first"),
                '{"query": "SELECT 1", "message": "fixed"}': ("SELECT 1", "fixed"),
            }.get(content, ("", "")),
            max_retries=3,
        )

        self.assertEqual(query, "SELECT 1")
        self.assertTrue(validated)
        self.assertEqual(mock_chat.call_count, 2)

    @patch("redash.ai_query.dry_run_query")
    def test_dry_run_applies_auto_limit(self, mock_dry_run):
        data_source = Mock()
        runner = Mock()
        runner.supports_auto_limit = True
        runner.apply_auto_limit.return_value = "SELECT 1 LIMIT 1"
        runner.run_query.return_value = ({"rows": []}, None)
        data_source.query_runner = runner

        error = dry_run_query(data_source, "SELECT 1", None)
        self.assertIsNone(error)
        runner.apply_auto_limit.assert_called_once_with("SELECT 1", True)


class TestGenerateQuery(TestCase):
    @patch("redash.ai_query.generate_with_validation")
    @patch("redash.ai_query.generate_reasoning_plan")
    def test_generate_query_uses_reasoning(self, mock_reasoning, mock_validate):
        mock_reasoning.return_value = "orders を使う"
        mock_validate.return_value = ("SELECT 1", "ok", True)

        result = generate_query(
            api_url="https://api.openai.com/v1",
            api_key="key",
            model="gpt-4o-mini",
            system_prompt="system",
            context="context",
            prompt="売上",
            history=[],
            data_source=Mock(),
            user=None,
            validate=True,
            use_reasoning=True,
            extract_query_payload=lambda content: ("SELECT 1", "ok"),
        )

        self.assertEqual(result["query"], "SELECT 1")
        self.assertEqual(result["reasoning"], "orders を使う")
        user_message = mock_validate.call_args[1]["messages"][-1]["content"]
        self.assertIn("推論プラン", user_message)
        self.assertIn("orders を使う", user_message)

