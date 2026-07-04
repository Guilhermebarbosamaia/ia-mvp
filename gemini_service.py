import json
import re
from io import BytesIO

import google.generativeai as genai  # type: ignore[import]
from PIL import Image


def send_image_to_gemini(api_key: str, image_bytes: bytes, prompt: str) -> str:
    """Enviar imagem para o Gemini e retornar a análise em JSON como texto."""
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    image = Image.open(BytesIO(image_bytes))
    response = model.generate_content([prompt, image])

    raw_text = (response.text or "").strip()
    if not raw_text:
        return "{}"

    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.S)
        if match:
            raw_text = match.group(0)
        else:
            raw_text = "{}"

    return raw_text
