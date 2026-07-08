"""Ponto de entrada do MVP: recebe uma imagem aérea e gera um dossiê de auditoria.

Uso:
    python main.py [caminho_da_imagem] [--propriedade-id ID] [--talhao-id ID] [--no-save]

Requer a variável de ambiente GEMINI_API_KEY (pode vir de um arquivo .env).
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

try:
    from PIL import Image, UnidentifiedImageError
except ImportError as exc:
    raise ImportError("Pillow é necessário. Instale com 'pip install Pillow'.") from exc

from prompts import AUDIT_PROMPT
from gemini_service import analyze_image, GeminiAnalysisError

DEFAULT_IMAGE_PATH = "images/imagem-gado.jpg"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_MB = 20
OUTPUT_DIR = Path("output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analisa uma imagem aérea de propriedade rural com IA e gera um dossiê estruturado."
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=DEFAULT_IMAGE_PATH,
        help=f"Caminho da imagem a analisar (padrão: {DEFAULT_IMAGE_PATH}).",
    )
    parser.add_argument(
        "--propriedade-id",
        default="NAO_INFORMADO",
        help="Identificador estável da propriedade, para rastreamento futuro (opcional).",
    )
    parser.add_argument(
        "--talhao-id",
        default="NAO_INFORMADO",
        help="Identificador do talhão/área específica inspecionada (opcional).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Não salvar o dossiê em disco; apenas exibir no terminal.",
    )
    return parser.parse_args()


def validate_image_path(path_str: str) -> Path:
    """Valida existência, tipo e tamanho do arquivo antes de gastar uma chamada de API com ele."""
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Imagem não encontrada em: {path}")
    if not path.is_file():
        raise ValueError(f"O caminho informado não é um arquivo: {path}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Extensão '{path.suffix}' não suportada. "
            f"Use um destes formatos: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_IMAGE_MB:
        raise ValueError(f"Imagem muito grande ({size_mb:.1f} MB). O limite é {MAX_IMAGE_MB} MB.")
    return path


def load_image_as_png_bytes(path: Path) -> bytes:
    """Carrega a imagem do disco, valida sua integridade e retorna bytes em PNG."""
    try:
        with Image.open(path) as img:
            img.verify()  # detecta arquivos corrompidos/malformados cedo
    except UnidentifiedImageError as exc:
        raise ValueError(f"O arquivo não é uma imagem válida: {path}") from exc
    except Exception as exc:
        raise RuntimeError(f"Erro ao validar imagem: {exc}") from exc

    try:
        # verify() invalida o objeto Image, por isso reabrimos o arquivo
        with Image.open(path) as img:
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as exc:
        raise RuntimeError(f"Erro ao carregar imagem: {exc}") from exc


def build_dossie(analise: dict, image_path: Path, propriedade_id: str, talhao_id: str) -> dict:
    """Envelopa a análise da IA com metadados de rastreamento (vistoria/propriedade/talhão).

    Esses IDs estáveis são o que permite, no futuro, ligar cada vistoria a um
    desfecho real (ex.: adimplência do crédito) e transformar fotos soltas em
    série temporal por propriedade.
    """
    now = datetime.now(timezone.utc)
    return {
        "vistoria_id": f"V-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}",
        "propriedade_id": propriedade_id,
        "talhao_id": talhao_id,
        "data_vistoria_utc": now.isoformat(),
        "imagem_analisada": image_path.name,
        "modelo_ia": "gemini-2.5-flash",
        "analise": analise,
    }


def print_dossie(dossie: dict) -> None:
    print("=========================")
    print("RELATÓRIO DA IA")
    print("=========================")
    print()
    print(json.dumps(dossie, ensure_ascii=False, indent=2))


def save_dossie(dossie: dict) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{dossie['vistoria_id']}.json"
    out_path.write_text(json.dumps(dossie, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    load_dotenv()  # carrega .env se existir; não sobrescreve variáveis já definidas no ambiente
    args = parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "Variável de ambiente GEMINI_API_KEY não encontrada.\n"
            "Defina-a em um arquivo .env (veja .env.example) ou exporte-a no ambiente e tente novamente."
        )
        sys.exit(1)

    try:
        image_path = validate_image_path(args.image)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        sys.exit(1)

    try:
        image_bytes = load_image_as_png_bytes(image_path)
    except Exception as exc:
        print(str(exc))
        sys.exit(1)

    try:
        analise = analyze_image(
            api_key=api_key,
            image_bytes=image_bytes,
            mime_type="image/png",
            prompt=AUDIT_PROMPT,
        )
    except GeminiAnalysisError as exc:
        print(f"Erro ao analisar a imagem: {exc}")
        sys.exit(1)

    dossie = build_dossie(analise, image_path, args.propriedade_id, args.talhao_id)
    print_dossie(dossie)

    if not args.no_save:
        out_path = save_dossie(dossie)
        print(f"\nDossiê salvo em: {out_path}")


if __name__ == "__main__":
    main()
