import google.generativeai as genai
from PIL import Image
from io import BytesIO


def send_image_to_gemini(api_key: str, image_bytes: bytes, prompt: str) -> str:
    """Enviar imagem para o Gemini e retornar a análise em texto."""
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    image = Image.open(BytesIO(image_bytes))
    
    response = model.generate_content([prompt, image])
    
    return response.text
