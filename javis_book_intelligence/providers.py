"""OpenAI Responses API adapter. Credentials are read only from environment.

No implicit provider retry: the durable SQLite worker owns retry decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import json
import httpx
from .distillation import OUTPUT_SCHEMA, instructions, user_input, PROMPT_VERSION

ENDPOINT = 'https://api.openai.com/v1/responses'


class ProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class AIResponse:
    payload: dict
    response_id: str
    input_tokens: int
    output_tokens: int


class OpenAIResponsesProvider:
    """Uses official HTTPS Responses endpoint with strict structured output.

    Only known non-sensitive error strings leave this module; never persist API
    response error bodies, request payload, or authorization headers as logs.
    """

    def __init__(self, timeout_seconds: float = 90):
        self.timeout_seconds = min(max(timeout_seconds, 2), 120)

    def generate(self, *, model: str, mode: str, language: str, title: str,
                 href: str, source_body: str, max_output_tokens: int) -> AIResponse:
        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key:
            raise ProviderError('OPENAI_API_KEY is not set', retryable=False)
        body = {
            'model': model,
            'instructions': instructions(mode, language),
            'input': user_input(title, href, source_body),
            'max_output_tokens': max_output_tokens,
            'store': False,
            'text': {'format': {'type': 'json_schema', 'name': 'javis_distillation_m2',
                                'strict': True, 'schema': OUTPUT_SCHEMA}},
        }
        headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
        try:
            # No API key, source text, raw response, or headers are logged.
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                resp = client.post(ENDPOINT, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderError('OpenAI network error (' + type(exc).__name__ + ')', retryable=True) from exc
        if resp.status_code >= 400:
            retryable = resp.status_code in (408, 409, 429) or resp.status_code >= 500
            raise ProviderError(f'OpenAI API returned HTTP {resp.status_code}', retryable=retryable)
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError('OpenAI API returned invalid JSON', retryable=True) from exc
        if data.get('status') != 'completed':
            raise ProviderError('OpenAI response was not completed', retryable=True)
        outputs = []
        for item in data.get('output', []):
            if item.get('type') == 'message':
                for c in item.get('content', []):
                    if c.get('type') == 'refusal':
                        raise ProviderError('Model refused this unit', retryable=False)
                    if c.get('type') == 'output_text' and isinstance(c.get('text'), str):
                        outputs.append(c['text'])
        raw = ''.join(outputs) or data.get('output_text', '')
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ProviderError('OpenAI response did not contain parseable structured JSON', retryable=False) from exc
        usage = data.get('usage') or {}
        inp, out = usage.get('input_tokens'), usage.get('output_tokens')
        if not isinstance(inp, int) or isinstance(inp, bool) or inp < 0 or not isinstance(out, int) or isinstance(out, bool) or out < 0:
            raise ProviderError('OpenAI did not return reliable token usage', retryable=False)
        return AIResponse(payload=payload, response_id=str(data.get('id', '')),
                          input_tokens=inp, output_tokens=out)
