from unittest import TestCase
from unittest.mock import Mock, patch

from redash.ai_query import (
    format_sql_pairs_for_prompt,
    retrieve_sql_pairs,
    score_sql_pair,
)
from redash.handlers.ai import (
    AiApiKind,
    chat_completions_url,
    extract_query_payload,
    resolve_ai_endpoint,
    schema_to_prompt_text,
)
from redash.models import AiSqlPair, DataSource, db
from tests import BaseTestCase


class TestChatCompletionsUrl(TestCase):
    def test_appends_chat_completions_to_v1_base(self):
        self.assertEqual(chat_completions_url("https://api.openai.com/v1"), "https://api.openai.com/v1/chat/completions")

    def test_keeps_full_endpoint(self):
        url = "https://example.com/v1/chat/completions"
        self.assertEqual(chat_completions_url(url), url)

    def test_appends_v1_when_missing(self):
        self.assertEqual(chat_completions_url("http://ollama:11434"), "http://ollama:11434/v1/chat/completions")

    def test_keeps_ollama_native_chat_url(self):
        url, kind = resolve_ai_endpoint("http://192.168.2.79:11434/api/chat")
        self.assertEqual(url, "http://192.168.2.79:11434/api/chat")
        self.assertEqual(kind, AiApiKind.OLLAMA)


class TestExtractQueryPayload(TestCase):
    def test_parses_json_object(self):
        query, message = extract_query_payload('{"query": "SELECT 1", "message": "件数"}')
        self.assertEqual(query, "SELECT 1")
        self.assertEqual(message, "件数")

    def test_parses_fenced_sql(self):
        query, message = extract_query_payload("説明です\n```sql\nSELECT 2\n```")
        self.assertEqual(query, "SELECT 2")
        self.assertEqual(message, "説明です")


class TestSchemaToPromptText(TestCase):
    def test_formats_table_and_column_types(self):
        text = schema_to_prompt_text(
            [
                {
                    "name": "public.orders",
                    "columns": [{"name": "id", "type": "integer"}, {"name": "amount", "type": "numeric"}],
                }
            ]
        )
        self.assertIn("public.orders", text)
        self.assertIn("id integer", text)
        self.assertIn("amount numeric", text)


class TestSqlPairs(TestCase):
    def test_score_sql_pair_prefers_question_match(self):
        pair = Mock(question="月別売上", query="SELECT 1")
        tokens = {"月別", "売上"}
        self.assertGreater(score_sql_pair(pair, tokens), 0)

    def test_format_sql_pairs_for_prompt(self):
        pair = Mock(question="件数", query="SELECT COUNT(*) FROM orders")
        text = format_sql_pairs_for_prompt([pair])
        self.assertIn("件数", text)
        self.assertIn("SELECT COUNT(*) FROM orders", text)


class TestAiGenerateQuery(BaseTestCase):
    def test_requires_prompt(self):
        rv = self.make_request("post", "/api/ai/generate_query", data={})
        self.assertEqual(rv.status_code, 400)

    def test_requires_ai_settings(self):
        rv = self.make_request("post", "/api/ai/generate_query", data={"prompt": "売上を出して"})
        self.assertEqual(rv.status_code, 400)
        self.assertIn("AI Setting", rv.json["message"])

    @patch("redash.handlers.ai.generate_with_validation")
    @patch.object(DataSource, "get_cached_schema")
    def test_returns_generated_query(self, mock_schema, mock_generate):
        self.factory.org.set_setting("ai_api_url", "https://api.openai.com/v1")
        self.factory.org.set_setting("ai_api_key", "sk-test")
        self.factory.org.set_setting("ai_model", "gpt-4o-mini")
        db.session.add(self.factory.org)
        db.session.commit()

        mock_schema.return_value = [
            {
                "name": "public.orders",
                "columns": [{"name": "id", "type": "integer"}, {"name": "amount", "type": "numeric"}],
            }
        ]
        mock_generate.return_value = ("SELECT COUNT(*) FROM public.orders", "件数です", True)

        rv = self.make_request(
            "post",
            "/api/ai/generate_query",
            data={"prompt": "件数を出して", "data_source_id": self.factory.data_source.id},
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["query"], "SELECT COUNT(*) FROM public.orders")
        self.assertEqual(rv.json["message"], "件数です")
        self.assertTrue(rv.json["validated"])

    @patch("redash.ai_client.requests.post")
    @patch.object(DataSource, "get_cached_schema")
    def test_includes_sql_pairs_in_system_prompt(self, mock_schema, mock_post):
        self.factory.org.set_setting("ai_api_url", "https://api.openai.com/v1")
        self.factory.org.set_setting("ai_api_key", "sk-test")
        self.factory.org.set_setting("ai_model", "gpt-4o-mini")
        db.session.add(self.factory.org)

        pair = AiSqlPair(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            question="月別売上",
            query="SELECT date_trunc('month', created_at), SUM(amount) FROM public.orders GROUP BY 1",
        )
        db.session.add(pair)
        db.session.commit()

        mock_schema.return_value = [
            {
                "name": "public.orders",
                "columns": [{"name": "amount", "type": "numeric"}, {"name": "created_at", "type": "timestamp"}],
            }
        ]
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"query": "SELECT 1", "message": "ok"}'
                            }
                        }
                    ]
                }
            ),
        )

        with patch("redash.handlers.ai.generate_with_validation") as mock_generate:
            mock_generate.side_effect = lambda **kwargs: (
                "SELECT 1",
                "ok",
                True,
            )
            rv = self.make_request(
                "post",
                "/api/ai/generate_query",
                data={"prompt": "月別売上を出して", "data_source_id": self.factory.data_source.id},
            )
        self.assertEqual(rv.status_code, 200)
        system_prompt = mock_generate.call_args[1]["messages"][0]["content"]
        self.assertIn("月別売上", system_prompt)


class TestAiSqlPairApi(BaseTestCase):
    def test_create_and_list_sql_pairs(self):
        rv = self.make_request(
            "post",
            "/api/ai/sql_pairs",
            data={
                "data_source_id": self.factory.data_source.id,
                "question": "件数",
                "query": "SELECT COUNT(*) FROM public.orders",
            },
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["question"], "件数")

        rv = self.make_request(
            "get",
            "/api/ai/sql_pairs?data_source_id={}".format(self.factory.data_source.id),
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(len(rv.json), 1)

    def test_retrieve_sql_pairs_ranks_by_prompt(self):
        pair1 = AiSqlPair(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            question="顧客一覧",
            query="SELECT * FROM customers",
        )
        pair2 = AiSqlPair(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            question="月別売上",
            query="SELECT 1 FROM orders",
        )
        db.session.add_all([pair1, pair2])
        db.session.commit()

        pairs = retrieve_sql_pairs(self.factory.data_source.id, self.factory.org.id, "月別の売上")
        self.assertEqual(pairs[0].question, "月別売上")


class TestAiOrganizationSettings(BaseTestCase):
    def test_admin_can_save_ai_settings(self):
        admin = self.factory.create_admin()
        rv = self.make_request(
            "post",
            "/api/settings/organization",
            data={
                "ai_api_url": "https://api.openai.com/v1",
                "ai_api_key": "sk-secret",
                "ai_model": "gpt-4o-mini",
            },
            user=admin,
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["settings"]["ai_api_url"], "https://api.openai.com/v1")
        self.assertEqual(rv.json["settings"]["ai_model"], "gpt-4o-mini")
        self.assertEqual(self.factory.org.get_setting("ai_api_key"), "sk-secret")
