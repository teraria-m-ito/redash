import logging
import re
from string import Template

from redash.ai_client import MessageRole, call_ai_chat
from redash.models import AiSqlPair

logger = logging.getLogger(__name__)

MAX_SQL_CORRECTION_RETRIES = 3
MAX_SQL_PAIRS_IN_PROMPT = 5

CORRECTION_USER_TEMPLATE = Template(
    """次のSQLはデータベースで実行できませんでした。スキーマに従って修正してください。

エラー:
$error

失敗したSQL:
$sql

元の要求:
$prompt

回答は次のJSONのみ。前後に文章を付けない:
{"query": "修正後のクエリ", "message": "日本語の短い説明"}"""
)


def build_correction_message(error, sql, prompt):
    return CORRECTION_USER_TEMPLATE.safe_substitute(
        error=error or "",
        sql=sql or "",
        prompt=prompt or "",
    )


def prompt_tokens(prompt):
    return set(token.lower() for token in re.findall(r"[A-Za-z0-9_\u3040-\u30ff\u4e00-\u9fff]+", prompt or "") if len(token) >= 2)


def score_sql_pair(pair, tokens):
    if not tokens:
        return 0
    question = (pair.question or "").lower()
    query = (pair.query or "").lower()
    score = 0
    for token in tokens:
        if token in question:
            score += 2
        if token in query:
            score += 1
    return score


def retrieve_sql_pairs(data_source_id, org_id, prompt, limit=MAX_SQL_PAIRS_IN_PROMPT):
    try:
        pairs = (
            AiSqlPair.query.filter(
                AiSqlPair.data_source_id == data_source_id,
                AiSqlPair.org_id == org_id,
            )
            .order_by(AiSqlPair.updated_at.desc())
            .all()
        )
    except Exception:
        logger.exception("Failed to load AI SQL pairs for data_source %s", data_source_id)
        return []
    if not pairs:
        return []

    tokens = prompt_tokens(prompt)
    if not tokens:
        return pairs[:limit]

    ranked = sorted(pairs, key=lambda pair: (-score_sql_pair(pair, tokens), -pair.updated_at.timestamp()))
    return ranked[:limit]


def format_sql_pairs_for_prompt(pairs):
    if not pairs:
        return ""
    lines = ["### SQL例（このデータソースで使われた質問とクエリ）###"]
    for index, pair in enumerate(pairs, start=1):
        lines.append("例{}:".format(index))
        lines.append("質問: {}".format(pair.question))
        lines.append("SQL:")
        lines.append(pair.query)
        lines.append("")
    return "\n".join(lines).strip()


def dry_run_query(data_source, query_text, user):
    query_text = (query_text or "").strip()
    if not query_text:
        return "クエリが空です。"

    try:
        runner = data_source.query_runner
        test_sql = query_text
        if runner.supports_auto_limit:
            test_sql = runner.apply_auto_limit(test_sql, True)
        _, error = runner.run_query(test_sql, user)
        if error:
            return str(error)
        return None
    except Exception as error:
        logger.exception("AI query validation failed for data_source %s", data_source.id)
        return str(error)


def generate_with_validation(
    *,
    api_url,
    api_key,
    model,
    messages,
    data_source,
    user,
    prompt,
    extract_query_payload,
    max_retries=MAX_SQL_CORRECTION_RETRIES,
):
    content = call_ai_chat(api_url, api_key, model, messages, temperature=0.1, timeout=180)
    query_text, message = extract_query_payload(content)

    if not data_source or not query_text:
        return query_text, message, False

    validated = False
    for attempt in range(max_retries + 1):
        error = dry_run_query(data_source, query_text, user)
        if not error:
            validated = True
            break
        if attempt >= max_retries:
            warning = "生成したSQLは検証に失敗しました: {}".format(error)
            message = "{} ({})".format(message, warning) if message else warning
            break

        correction_messages = list(messages)
        correction_messages.append({"role": MessageRole.ASSISTANT, "content": content})
        correction_messages.append(
            {
                "role": MessageRole.USER,
                "content": build_correction_message(error, query_text, prompt),
            }
        )
        content = call_ai_chat(api_url, api_key, model, correction_messages, temperature=0.1, timeout=180)
        query_text, message = extract_query_payload(content)

    return query_text, message, validated
