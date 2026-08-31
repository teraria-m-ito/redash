import json
import logging
import re
from string import Template

from redash.ai_client import MessageRole, call_ai_chat
from redash.models import AiInstruction, AiSqlPair
from redash.query_runner import NotSupported

logger = logging.getLogger(__name__)

SCHEMA_MAX_CHARS = 80000
MAX_SQL_CORRECTION_RETRIES = 3
MAX_SQL_PAIRS_IN_PROMPT = 5
MAX_INSTRUCTIONS_IN_PROMPT = 10

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

REASONING_SYSTEM_PROMPT = """あなたはSQLアナリストです。与えられたスキーマ、ビジネスルール、SQL例だけを根拠に、
質問に答えるためのSQL作成方針を日本語で簡潔に記述してください。
使用するテーブル、JOIN、フィルタ、集計方法を箇条書きで示してください。
存在しないテーブルやカラムは使わないでください。"""


def extract_query_payload(content):
    text = (content or "").strip()
    if not text:
        return "", ""

    candidates = [text]
    fenced_json = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced_json:
        candidates.insert(0, fenced_json.group(1).strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "query" in parsed:
                return (parsed.get("query") or "").strip(), (parsed.get("message") or "").strip()
        except (TypeError, ValueError):
            continue

    sql_block = re.search(r"```(?:sql|SQL)\s*(.*?)```", text, re.DOTALL)
    if sql_block:
        explanation = re.sub(r"```(?:sql|SQL)\s*.*?```", "", text, flags=re.DOTALL).strip()
        return sql_block.group(1).strip(), explanation

    generic_block = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if generic_block:
        explanation = re.sub(r"```\s*.*?```", "", text, flags=re.DOTALL).strip()
        return generic_block.group(1).strip(), explanation

    return text, ""


def load_data_source_schema(data_source, fallback_schema):
    schema = data_source.get_cached_schema()
    if schema:
        return schema
    try:
        return data_source.get_schema()
    except NotSupported:
        return fallback_schema or []
    except Exception:
        logger.exception("Failed to load schema for data_source %s", data_source.id)
        return fallback_schema or []


def build_correction_message(error, sql, prompt):
    return CORRECTION_USER_TEMPLATE.safe_substitute(
        error=error or "",
        sql=sql or "",
        prompt=prompt or "",
    )


def prompt_tokens(prompt):
    return set(
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\u3040-\u30ff\u4e00-\u9fff]+", prompt or "")
        if len(token) >= 2
    )


def score_text_match(text, tokens):
    if not tokens:
        return 0
    lowered = (text or "").lower()
    return sum(2 if token in lowered else 0 for token in tokens)


def score_sql_pair(pair, tokens):
    return score_text_match(pair.question, tokens) + score_text_match(pair.query, tokens)


def score_instruction(instruction, tokens):
    return score_text_match(instruction.title, tokens) + score_text_match(instruction.content, tokens)


def score_table_relevance(table, tokens):
    if not tokens:
        return 0

    score = score_text_match(table.get("name"), tokens) * 2
    score += score_text_match(table.get("description"), tokens)

    for col in table.get("columns") or []:
        if isinstance(col, dict):
            score += score_text_match(col.get("name"), tokens)
            score += score_text_match(col.get("description"), tokens)
        else:
            score += score_text_match(str(col), tokens)
    return score


def format_column(col):
    if isinstance(col, dict):
        name = col.get("name") or ""
        col_type = col.get("type") or ""
        description = (col.get("description") or "").strip()
        label = "{} {}".format(name, col_type).strip() if col_type else name
        if description:
            return "{} -- {}".format(label, description)
        return label
    return str(col)


def format_table_for_prompt(table):
    name = table.get("name") or ""
    lines = [name]
    table_description = (table.get("description") or "").strip()
    if table_description:
        lines.append("  説明: {}".format(table_description))

    columns = table.get("columns") or []
    if columns:
        lines.append("  カラム:")
        for col in columns:
            lines.append("    - {}".format(format_column(col)))
    return "\n".join(lines)


def schema_to_prompt_text(schema, prompt="", max_chars=SCHEMA_MAX_CHARS):
    tables = list(schema or [])
    if not tables:
        return "(なし)"

    tokens = prompt_tokens(prompt)
    formatted_tables = [format_table_for_prompt(table) for table in tables]
    full_text = "\n\n".join(formatted_tables)
    if len(full_text) <= max_chars:
        return full_text

    ranked_tables = sorted(
        tables,
        key=lambda table: (-score_table_relevance(table, tokens), (table.get("name") or "").lower()),
    )
    all_names = [table.get("name") or "" for table in tables]
    text = "テーブル一覧 ({}件): {}\n\n関連テーブル定義:\n".format(len(all_names), ", ".join(all_names))

    for table in ranked_tables:
        block = format_table_for_prompt(table)
        if len(text) + len(block) + 2 > max_chars:
            break
        text += block + "\n\n"

    return text.strip()


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


def retrieve_instructions(data_source_id, org_id, prompt, limit=MAX_INSTRUCTIONS_IN_PROMPT):
    try:
        instructions = (
            AiInstruction.query.filter(
                AiInstruction.data_source_id == data_source_id,
                AiInstruction.org_id == org_id,
            )
            .order_by(AiInstruction.updated_at.desc())
            .all()
        )
    except Exception:
        logger.exception("Failed to load AI instructions for data_source %s", data_source_id)
        return []
    if not instructions:
        return []

    tokens = prompt_tokens(prompt)
    if not tokens:
        return instructions[:limit]

    ranked = sorted(
        instructions,
        key=lambda instruction: (-score_instruction(instruction, tokens), -instruction.updated_at.timestamp()),
    )
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


def format_instructions_for_prompt(instructions):
    if not instructions:
        return ""
    lines = ["### ビジネスルール（必ず厳守）###"]
    for index, instruction in enumerate(instructions, start=1):
        title = (instruction.title or "").strip()
        if title:
            lines.append("{}. {}".format(index, title))
        else:
            lines.append("{}. ルール".format(index))
        lines.append(instruction.content)
        lines.append("")
    return "\n".join(lines).strip()


def build_generation_context(
    *,
    data_source_name,
    data_source_type,
    syntax,
    current_query,
    schema_text,
    sql_pairs_text,
    instructions_text,
):
    parts = [
        "データソース: {} ({})".format(data_source_name or "(未選択)", data_source_type or "(不明)"),
        "構文: {}".format(syntax),
        "",
        "現在のクエリ:",
        current_query or "(空)",
        "",
        "テーブル定義:",
        schema_text,
    ]
    if instructions_text:
        parts.extend(["", instructions_text])
    if sql_pairs_text:
        parts.extend(["", sql_pairs_text])
    return "\n".join(parts)


def build_generation_user_message(prompt, reasoning_plan=None):
    parts = []
    if reasoning_plan:
        parts.extend(["### 推論プラン ###", reasoning_plan, ""])
    parts.extend(["### 質問 ###", prompt])
    return "\n".join(parts)


def generate_reasoning_plan(api_url, api_key, model, context, prompt):
    messages = [
        {"role": MessageRole.SYSTEM, "content": REASONING_SYSTEM_PROMPT},
        {"role": MessageRole.USER, "content": context + "\n\n### 質問 ###\n" + prompt},
    ]
    return call_ai_chat(api_url, api_key, model, messages, temperature=0.1, timeout=120).strip()


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


def generate_query(
    *,
    api_url,
    api_key,
    model,
    system_prompt,
    context,
    prompt,
    history,
    data_source,
    user,
    validate,
    use_reasoning,
    extract_query_payload,
    max_retries=MAX_SQL_CORRECTION_RETRIES,
):
    reasoning_plan = None
    if use_reasoning:
        reasoning_plan = generate_reasoning_plan(api_url, api_key, model, context, prompt)

    messages = [{"role": MessageRole.SYSTEM, "content": system_prompt + "\n\n" + context}]
    for item in history[-20:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in (MessageRole.USER, MessageRole.ASSISTANT) and content:
            messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": MessageRole.USER,
            "content": build_generation_user_message(prompt, reasoning_plan),
        }
    )

    if validate and data_source:
        query_text, message, validated = generate_with_validation(
            api_url=api_url,
            api_key=api_key,
            model=model,
            messages=messages,
            data_source=data_source,
            user=user,
            prompt=prompt,
            extract_query_payload=extract_query_payload,
            max_retries=max_retries,
        )
    else:
        content = call_ai_chat(api_url, api_key, model, messages, temperature=0.1, timeout=180)
        query_text, message = extract_query_payload(content)
        validated = False

    return {
        "query": query_text,
        "message": message,
        "validated": validated,
        "reasoning": reasoning_plan,
    }
