"""Camada de integração com a API do Gemini.

Migrado do SDK antigo (`google-generativeai`, oficialmente descontinuado)
para o SDK unificado atual (`google-genai`). Também adiciona:
- retries com backoff para falhas transitórias (rede, 5xx, limite de taxa);
- tratamento explícito de respostas bloqueadas por segurança;
- validação e extração robusta do JSON retornado pelo modelo.
"""

import json
import re
import time
from typing import Optional

from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2

# Trechos que indicam erro do cliente (chave inválida, payload malformado etc.)
# — nesses casos não adianta tentar de novo.
_NON_RETRYABLE_MARKERS = (
    "400",
    "401",
    "403",
    "API key not valid",
    "PERMISSION_DENIED",
    "INVALID_ARGUMENT",
    "UNAUTHENTICATED",
)


class GeminiAnalysisError(Exception):
    """Erro ao obter ou interpretar a análise da IA."""


def _extract_json(raw_text: str) -> dict:
    """Extrai e valida um objeto JSON a partir do texto bruto retornado pelo modelo."""
    text = (raw_text or "").strip()
    if not text:
        raise GeminiAnalysisError("A IA retornou uma resposta vazia.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise GeminiAnalysisError(
                "Não foi possível interpretar a resposta da IA como JSON. "
                f"Resposta recebida (truncada): {text[:300]!r}"
            )
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise GeminiAnalysisError(f"JSON malformado retornado pela IA: {exc}") from exc


def analyze_image(api_key: str, image_bytes: bytes, mime_type: str, prompt: str) -> dict:
    """Envia a imagem para o Gemini e retorna a análise já validada como dict.

    Levanta GeminiAnalysisError com uma mensagem clara em caso de falha —
    seja erro de rede/API, bloqueio de segurança, ou resposta que não é JSON válido.
    """
    if not api_key:
        raise ValueError("api_key não pode ser vazio.")
    if not image_bytes:
        raise ValueError("image_bytes não pode ser vazio.")

    client = genai.Client(api_key=api_key)

    response = None
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            break
        except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de transporte/API aqui
            last_error = exc
            message = str(exc)
            non_retryable = any(marker in message for marker in _NON_RETRYABLE_MARKERS)
            if non_retryable or attempt == MAX_RETRIES:
                raise GeminiAnalysisError(f"Erro ao chamar a API Gemini: {exc}") from exc
            time.sleep(RETRY_BASE_DELAY_SECONDS * attempt)

    if response is None:
        raise GeminiAnalysisError(f"Falha ao chamar a API Gemini: {last_error}")

    # response.text pode levantar exceção (ou vir vazio) se a resposta foi
    # bloqueada por segurança ou não teve candidatos — tratamos isso explicitamente
    # em vez de deixar a exceção genérica do SDK vazar para o usuário final.
    try:
        raw_text = response.text
    except Exception as exc:
        feedback = getattr(response, "prompt_feedback", None)
        raise GeminiAnalysisError(
            "Não foi possível ler a resposta da IA — a geração pode ter sido "
            f"bloqueada por segurança. Detalhes: {feedback}"
        ) from exc

    if not raw_text:
        feedback = getattr(response, "prompt_feedback", None)
        raise GeminiAnalysisError(
            f"A IA não retornou conteúdo. Possível bloqueio de segurança. Detalhes: {feedback}"
        )

    return _extract_json(raw_text)
