import json
import re

from redash import models, utils
from redash.ai_client import AiChatError, MessageRole, call_ai_chat, get_org_ai_settings
from redash.worker import get_job_logger, job

logger = get_job_logger(__name__)

MAX_ROWS = 200
MAX_PAYLOAD_CHARS = 60000

INSIGHT_SYSTEM_PROMPT = """あなたはクエリ結果から特異的な変化（インサイト）を検出するアナリストです。
Dimension は主に時系列、Category はユーザID・商品IDなどの対象、message_to は通知・表示対象（ユーザ名など）を表します。

検出の観点の例:
- Dimension（日時など）を重ねて急激な変化があった
- 他の Category と比較して大きな乖離が生じた

厳守事項:
- 特異的な変化がある場合のみ insights に含める。無い場合は空配列
- message には何が特異で、なぜそう判断したかを日本語で具体的に書く
- message_to には結果行の message_to 列の値を使う（無い場合は Category の値）
- 回答は次のJSONのみ。前後に文章を付けない
{"insights":[{"message_to":"対象","message":"特異変化の説明と理由"}]}"""


def _truncate_rows(rows):
    limited = list(rows or [])[:MAX_ROWS]
    text = json.dumps(limited, ensure_ascii=False, default=str)
    if len(text) <= MAX_PAYLOAD_CHARS:
        return limited
    # 文字数超過時は行数を段階的に減らす
    while limited and len(json.dumps(limited, ensure_ascii=False, default=str)) > MAX_PAYLOAD_CHARS:
        limited = limited[: max(1, len(limited) // 2)]
    return limited


def _parse_insight_payload(content):
    text = (content or "").strip()
    if not text:
        return []

    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        items = parsed.get("insights")
        if isinstance(items, list):
            return items
    return []


def evaluate_insight_definition(definition):
    query = definition.query_rel
    if not query or not query.latest_query_data:
        logger.info("Insight definition %d has no query result.", definition.id)
        return 0

    query_result = query.latest_query_data
    query_result_id = query_result.id

    if models.Insight.already_evaluated(definition.id, query_result_id):
        logger.info(
            "Insight definition %d already evaluated for query_result %d; skip.",
            definition.id,
            query_result_id,
        )
        return 0

    data = query_result.data or {}
    rows = data.get("rows") or []
    columns = [col.get("name") for col in (data.get("columns") or []) if col.get("name")]

    dimension_column = definition.dimension_column
    category_column = definition.category_column
    message_to_column = definition.message_to_column

    if not dimension_column or not category_column:
        logger.warning("Insight definition %d missing dimension/category column.", definition.id)
        return 0

    if dimension_column not in columns or category_column not in columns:
        logger.warning(
            "Insight definition %d columns not in result (dimension=%s category=%s).",
            definition.id,
            dimension_column,
            category_column,
        )
        return 0

    org = query.org
    api_url, api_key, model = get_org_ai_settings(org)
    if not api_url or not model:
        logger.warning("AI settings missing; skip insight definition %d.", definition.id)
        return 0

    truncated_rows = _truncate_rows(rows)
    user_prompt = (
        "Insight名: {}\n"
        "Dimension列: {}\n"
        "Category列: {}\n"
        "message_to列: {}\n"
        "カラム: {}\n"
        "行データ(JSON):\n{}"
    ).format(
        definition.name,
        dimension_column,
        category_column,
        message_to_column or "(未設定)",
        ", ".join(columns),
        json.dumps(truncated_rows, ensure_ascii=False, default=str),
    )

    messages = [
        {"role": MessageRole.SYSTEM, "content": INSIGHT_SYSTEM_PROMPT},
        {"role": MessageRole.USER, "content": user_prompt},
    ]

    try:
        content = call_ai_chat(api_url, api_key, model, messages, temperature=0.2, timeout=300)
    except AiChatError:
        logger.exception("AI insight evaluation failed for definition %d", definition.id)
        return 0

    items = _parse_insight_payload(content)
    if not items:
        logger.info("No insights detected for definition %d.", definition.id)
        return 0

    execute_at = utils.utcnow()
    created = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        message = (item.get("message") or "").strip()
        if not message:
            continue
        message_to = (item.get("message_to") or "").strip()
        if not message_to:
            message_to = category_column

        insight = models.Insight(
            insight_definition=definition,
            query_rel=query,
            query_result_id=query_result_id,
            execute_at=execute_at,
            dimension_column_name=dimension_column,
            category_column_name=category_column,
            message_to=message_to[:255],
            message=message,
        )
        models.db.session.add(insight)
        created += 1

    if created:
        models.db.session.commit()
        logger.info(
            "Created %d insight(s) for definition %d query_result %d.",
            created,
            definition.id,
            query_result_id,
        )

    return created


@job("default", timeout=600)
def check_insight_definition(insight_definition_id):
    definition = models.InsightDefinition.query.get(insight_definition_id)
    if not definition:
        logger.warning("Insight definition %s not found.", insight_definition_id)
        return
    evaluate_insight_definition(definition)


@job("default", timeout=600)
def check_insights_for_query(query_id, metadata=None):
    logger.debug("Checking query %d for insights", query_id)
    query = models.Query.query.get(query_id)
    if not query:
        return

    for definition in query.insight_definitions:
        logger.info("Evaluating insight definition (%d) of query %d.", definition.id, query_id)
        try:
            evaluate_insight_definition(definition)
        except Exception:
            logger.exception("Failed evaluating insight definition %d", definition.id)
