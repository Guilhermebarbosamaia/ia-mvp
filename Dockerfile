# Imagem base leve com Python
FROM python:3.12-slim

# Evita gerar arquivos .pyc e força os logs a aparecerem na hora (sem buffer)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copia só o requirements primeiro — assim o Docker reaproveita o cache
# dessa camada em builds futuros, desde que as dependências não mudem
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY main.py gemini_service.py prompts.py ./
COPY images ./images

# Diretório onde os dossiês serão salvos — normalmente montado como volume
# em tempo de execução, para os arquivos sobreviverem além do container
RUN mkdir -p /app/output

# NUNCA copie o .env para dentro da imagem — a chave de API é passada em
# tempo de execução (--env-file .env, ou docker-compose com env_file).

ENTRYPOINT ["python", "main.py"]
