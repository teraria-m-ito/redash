import logging

import requests

logger = logging.getLogger(__name__)


class AiSettingKey:
    API_URL = "ai_api_url"
    API_KEY = "ai_api_key"
    MODEL = "ai_model"


class MessageRole:
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AiApiKind:
    OPENAI = "openai"
    OLLAMA = "ollama"


class AiChatError(Exception):
    def __init__(self, message, status_code=502):
        super(AiChatError, self).__init__(message)
        self.message = message
        self.status_code = status_code


def resolve_ai_endpoint(api_url):
    url = (api_url or "").strip().rstrip("/")
    if url.endswith("/api/chat") or url.endswith("/api"):
        if not url.endswith("/api/chat"):
            url = "{}/chat".format(url)
        return url, AiApiKind.OLLAMA
    if url.endswith("/chat/completions"):
        return url, AiApiKind.OPENAI
    if url.endswith("/v1"):
        return "{}/chat/completions".format(url), AiApiKind.OPENAI
    return "{}/v1/chat/completions".format(url), AiApiKind.OPENAI


def chat_completions_url(api_url):
    url, _kind = resolve_ai_endpoint(api_url)
    return url


def assistant_content_from_response(payload):
    if not isinstance(payload, dict):
        raise TypeError("payload is not an object")
    if payload.get("choices"):
        return payload["choices"][0]["message"]["content"]
    message = payload.get("message")
    if isinstance(message, dict) and "content" in message:
        return message.get("content")
    raise KeyError("content")


def get_org_ai_settings(org):
    api_url = (org.get_setting(AiSettingKey.API_URL, raise_on_missing=False) or "").strip()
    api_key = (org.get_setting(AiSettingKey.API_KEY, raise_on_missing=False) or "").strip()
    model = (org.get_setting(AiSettingKey.MODEL, raise_on_missing=False) or "").strip()
    return api_url, api_key, model


def call_ai_chat(api_url, api_key, model, messages, temperature=0.1, timeout=180):
    if not api_url or not model:
        raise AiChatError("AI設定が未設定です。設定の「AI Setting」タブで接続情報を保存してください。", status_code=400)

    endpoint, api_kind = resolve_ai_endpoint(api_url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)

    if api_kind == AiApiKind.OLLAMA:
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
    else:
        body = {"model": model, "messages": messages, "temperature": temperature}

    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
    except requests.RequestException:
        logger.exception("AI API request failed")
        raise AiChatError("AIサービスに接続できませんでした。")

    if response.status_code >= 400:
        logger.warning("AI API error status=%s body=%s", response.status_code, response.text[:500])
        raise AiChatError("AIサービスがエラーを返しました。（HTTP {}）".format(response.status_code))

    try:
        payload = response.json()
        return assistant_content_from_response(payload)
    except (ValueError, KeyError, IndexError, TypeError):
        raise AiChatError("AIサービスの応答を解釈できませんでした。")
