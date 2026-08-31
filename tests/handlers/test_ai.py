from unittest import TestCase
from unittest.mock import Mock, patch

from redash.ai_query import (
    extract_query_payload,
    format_instructions_for_prompt,
    format_sql_pairs_for_prompt,
    retrieve_instructions,
    retrieve_sql_pairs,
    schema_to_prompt_text,
    score_table_relevance,
)
from redash.ai_client import AiApiKind, chat_completions_url, resolve_ai_endpoint
from redash.handlers.ai import AiGenerateQueryResource
from redash.models import AiInstruction, AiSqlPair, DataSource, db
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
    def test_includes_table_and_column_descriptions(self):
        text = schema_to_prompt_text(
            [
                {
                    "name": "public.orders",
                    "description": "注文テーブル",
                    "columns": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "numeric", "description": "税込金額"},
                    ],
                }
            ]
        )
        self.assertIn("public.orders", text)
        self.assertIn("注文テーブル", text)
        self.assertIn("税込金額", text)

    def test_prioritizes_relevant_tables_when_truncated(self):
        schema = [
            {
                "name": "public.customers",
                "columns": [{"name": "id", "type": "integer"}],
            },
            {
                "name": "public.orders",
                "description": "売上テーブル",
                "columns": [{"name": "amount", "type": "numeric"}],
            },
        ]
        text = schema_to_prompt_text(schema, "売上を集計", max_chars=300)
        self.assertIn("public.orders", text)
        self.assertGreater(score_table_relevance(schema[1], {"売上"}), score_table_relevance(schema[0], {"売上"}))


class TestSqlPairs(TestCase):
    def test_format_sql_pairs_for_prompt(self):
        pair = Mock(question="件数", query="SELECT COUNT(*) FROM orders")
        text = format_sql_pairs_for_prompt([pair])
        self.assertIn("件数", text)
        self.assertIn("SELECT COUNT(*) FROM orders", text)

    def test_format_instructions_for_prompt(self):
        instruction = Mock(title="売上定義", content="orders.amount の合計")
        text = format_instructions_for_prompt([instruction])
        self.assertIn("売上定義", text)
        self.assertIn("orders.amount", text)


class TestAiGenerateQuery(BaseTestCase):
    def test_requires_prompt(self):
        rv = self.make_request("post", "/api/ai/generate_query", data={})
        self.assertEqual(rv.status_code, 400)

    def test_requires_ai_settings(self):
        rv = self.make_request("post", "/api/ai/generate_query", data={"prompt": "売上を出して"})
        self.assertEqual(rv.status_code, 400)
        self.assertIn("AI Setting", rv.json["message"])

    @patch("redash.handlers.ai.generate_query")
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
        mock_generate.return_value = {
            "query": "SELECT COUNT(*) FROM public.orders",
            "message": "件数です",
            "validated": True,
            "reasoning": "orders を使う",
        }

        rv = self.make_request(
            "post",
            "/api/ai/generate_query",
            data={"prompt": "件数を出して", "data_source_id": self.factory.data_source.id},
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["query"], "SELECT COUNT(*) FROM public.orders")
        self.assertEqual(rv.json["message"], "件数です")
        self.assertTrue(rv.json["validated"])
        self.assertEqual(rv.json["reasoning"], "orders を使う")

    @patch("redash.handlers.ai.generate_query")
    @patch.object(DataSource, "get_cached_schema")
    def test_includes_sql_pairs_and_instructions_in_context(self, mock_schema, mock_generate):
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
        instruction = AiInstruction(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            title="売上定義",
            content="売上は orders.amount の合計",
        )
        db.session.add_all([pair, instruction])
        db.session.commit()

        mock_schema.return_value = [
            {
                "name": "public.orders",
                "columns": [{"name": "amount", "type": "numeric"}, {"name": "created_at", "type": "timestamp"}],
            }
        ]
        mock_generate.return_value = {
            "query": "SELECT 1",
            "message": "ok",
            "validated": True,
            "reasoning": "plan",
        }

        rv = self.make_request(
            "post",
            "/api/ai/generate_query",
            data={"prompt": "月別売上を出して", "data_source_id": self.factory.data_source.id},
        )
        self.assertEqual(rv.status_code, 200)
        context = mock_generate.call_args[1]["context"]
        self.assertIn("月別売上", context)
        self.assertIn("売上定義", context)


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


class TestAiInstructionApi(BaseTestCase):
    def test_create_and_list_instructions(self):
        rv = self.make_request(
            "post",
            "/api/ai/instructions",
            data={
                "data_source_id": self.factory.data_source.id,
                "title": "売上定義",
                "content": "売上は orders.amount の合計",
            },
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["title"], "売上定義")

        rv = self.make_request(
            "get",
            "/api/ai/instructions?data_source_id={}".format(self.factory.data_source.id),
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(len(rv.json), 1)

    def test_retrieve_instructions_ranks_by_prompt(self):
        instruction1 = AiInstruction(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            title="顧客",
            content="customers テーブルを使う",
        )
        instruction2 = AiInstruction(
            org=self.factory.org,
            data_source=self.factory.data_source,
            user=self.factory.user,
            title="売上",
            content="orders.amount を集計する",
        )
        db.session.add_all([instruction1, instruction2])
        db.session.commit()

        instructions = retrieve_instructions(self.factory.data_source.id, self.factory.org.id, "月別売上")
        self.assertEqual(instructions[0].title, "売上")


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
