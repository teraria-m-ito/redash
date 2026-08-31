import logging

from flask import request
from flask_restful import abort

from redash.ai_client import AiChatError, get_org_ai_settings
from redash.ai_query import (
    build_generation_context,
    extract_query_payload,
    generate_query,
    format_instructions_for_prompt,
    format_sql_pairs_for_prompt,
    load_data_source_schema,
    retrieve_instructions,
    retrieve_sql_pairs,
    schema_to_prompt_text,
)
from redash.handlers.base import BaseResource, get_object_or_404
from redash.models import DataSource
from redash.permissions import require_access, require_permission, view_only

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

SYSTEM_PROMPT = """あなたは指定データソースのスキーマだけを使ってクエリを書くアシスタントです。
厳守事項:
- 与えられたスキーマに存在するテーブル名とカラム名だけを使う
- スキーマに無い名前は、一般的な名前（users, orders, sales など）でも絶対に作らない
- テーブル名はスキーマの表記をそのまま使う（schema.table 形式ならその通り）
- ビジネスルールがある場合は必ず厳守する
- SQL例がある場合は、書き方やテーブルの使い方の参考にする（ただし質問に合わせて適宜変更する）
- 推論プランがある場合は、その方針に沿ってSQLを書く
- スキーマが空、または該当テーブルが無い場合は query を空文字にし、message に理由を日本語で書く
- 回答は次のJSONのみ。前後に文章を付けない
{"query": "クエリ本文", "message": "日本語の短い説明"}"""


class AiGenerateQueryResource(BaseResource):
    @require_permission("create_query")
    def post(self):
        req = request.get_json(True) or {}
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            abort(400, message="要求を入力してください。")

        org = self.current_org
        api_url, api_key, model = get_org_ai_settings(org)

        if not api_url or not model:
            abort(400, message="AI設定が未設定です。設定の「AI Setting」タブで接続情報を保存してください。")

        history = req.get("messages") or []
        current_query = req.get("current_query") or ""
        fallback_schema = req.get("schema") if isinstance(req.get("schema"), list) else []
        syntax = req.get("syntax") or "sql"
        validate_query = req.get("validate", True)
        use_reasoning = req.get("use_reasoning", True)
        data_source_name = ""
        data_source_type = ""
        schema = fallback_schema
        data_source = None

        data_source_id = req.get("data_source_id")
        if data_source_id:
            data_source = get_object_or_404(DataSource.get_by_id_and_org, data_source_id, org)
            require_access(data_source, self.current_user, view_only)
            data_source_name = data_source.name
            data_source_type = data_source.type
            schema = load_data_source_schema(data_source, fallback_schema)
            try:
                syntax = getattr(data_source.query_runner, "syntax", None) or syntax
            except Exception:
                pass

        schema_text = schema_to_prompt_text(schema, prompt)
        sql_pairs_text = ""
        instructions_text = ""
        if data_source:
            pairs = retrieve_sql_pairs(data_source.id, org.id, prompt)
            sql_pairs_text = format_sql_pairs_for_prompt(pairs)
            instructions = retrieve_instructions(data_source.id, org.id, prompt)
            instructions_text = format_instructions_for_prompt(instructions)

        context = build_generation_context(
            data_source_name=data_source_name,
            data_source_type=data_source_type,
            syntax=syntax,
            current_query=current_query,
            schema_text=schema_text,
            sql_pairs_text=sql_pairs_text,
            instructions_text=instructions_text,
        )

        try:
            result = generate_query(
                api_url=api_url,
                api_key=api_key,
                model=model,
                system_prompt=SYSTEM_PROMPT,
                context=context,
                prompt=prompt,
                history=history,
                data_source=data_source,
                user=self.current_user,
                validate=validate_query,
                use_reasoning=use_reasoning,
                extract_query_payload=extract_query_payload,
                max_retries=MAX_VALIDATION_RETRIES,
            )
        except AiChatError as error:
            abort(error.status_code, message=error.message)
        except Exception as error:
            logger.exception("AI query generation failed")
            abort(500, message="クエリの生成中にエラーが発生しました: {}".format(error))

        query_text = result.get("query") or ""
        message = result.get("message") or ""
        if not query_text and not message:
            abort(502, message="AIがクエリを返せませんでした。")

        self.record_event({"action": "generate", "object_type": "ai_query"})
        return {
            "query": query_text,
            "message": message or "クエリを生成しました。",
            "validated": result.get("validated", False),
            "reasoning": result.get("reasoning"),
        }
