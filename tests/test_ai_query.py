from unittest import TestCase
from unittest.mock import Mock, patch

from redash.ai_query import build_correction_message, dry_run_query, generate_with_validation


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
