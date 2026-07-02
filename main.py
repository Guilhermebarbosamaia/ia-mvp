import os
import sys
from io import BytesIO
from PIL import Image

from prompts import AUDIT_PROMPT
import gemini_service

# Caminho da imagem (edite conforme necessário)
IMAGE_PATH = "images/preview.jpg"


def load_image(path: str) -> bytes:
	"""Carrega a imagem do disco e retorna bytes em PNG.

	Usamos PNG para preservar compatibilidade com APIs multimodais.
	"""
	try:
		with Image.open(path) as img:
			buf = BytesIO()
			# força conversão para RGB quando necessário
			if img.mode in ("RGBA", "P"):
				img = img.convert("RGB")
			img.save(buf, format="PNG")
			return buf.getvalue()
	except FileNotFoundError:
		raise
	except Exception as exc:
		raise RuntimeError(f"Erro ao carregar imagem: {exc}") from exc


def print_response(response: str) -> None:
	"""Imprime o relatório no formato exigido pelo usuário."""
	print("=========================")
	print("RELATÓRIO DA IA")
	print("=========================")
	print()
	print(response)


def main() -> None:
	api_key = os.getenv("GEMINI_API_KEY")
	if not api_key:
		print("Variável de ambiente GEMINI_API_KEY não encontrada. Defina-a e tente novamente.")
		sys.exit(1)

	try:
		image_bytes = load_image(IMAGE_PATH)
	except FileNotFoundError:
		print(f"Imagem não encontrada em: {IMAGE_PATH}")
		sys.exit(1)
	except Exception as exc:
		print(str(exc))
		sys.exit(1)

	try:
		response_text = gemini_service.send_image_to_gemini(api_key=api_key, image_bytes=image_bytes, prompt=AUDIT_PROMPT)
	except Exception as exc:
		print("Erro ao enviar imagem para o Gemini:", exc)
		sys.exit(1)

	print_response(response_text)


if __name__ == "__main__":
	main()

