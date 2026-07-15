# Imagem base leve com Python
FROM python:3.12-slim

# Evita gerar arquivos .pyc e força os logs a aparecerem na hora (sem buffer)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Bibliotecas de sistema exigidas pelo WeasyPrint para renderizar o PDF
# (pango/cairo para texto e layout, gdk-pixbuf para imagens, libffi para os
# bindings cffi). Sem isso, "import weasyprint" falha dentro do container
# mesmo com o pacote Python já instalado via pip.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copia só o requirements primeiro — assim o Docker reaproveita o cache
# dessa camada em builds futuros, desde que as dependências não mudem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY main.py gemini_service.py prompts.py report.py ./
COPY templates ./templates
COPY images ./images

# Diretório onde os dossiês serão salvos — normalmente montado como volume
# em tempo de execução, para os arquivos sobreviverem além do container
RUN mkdir -p /app/output

# NUNCA copie o .env para dentro da imagem — a chave de API é passada em
# tempo de execução (--env-file .env, ou docker-compose com env_file).

ENTRYPOINT ["python", "main.py"]
