# AgroAudit — MVP de análise de imagem

Protótipo do núcleo do produto: recebe uma imagem aérea de propriedade rural e
gera um dossiê estruturado (JSON) usando o Gemini como IA de visão, além do
relatório em PDF pronto para entrega (documento formatado como evidência
técnica, com selo, legenda de confiabilidade e seções de auditoria).

## Pré-requisitos

- Python 3.10 ou superior
- Uma chave de API do Gemini — grátis em https://aistudio.google.com/apikey

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e cole sua chave da API do Gemini:

```bash
cp .env.example .env
```

Nunca commite o arquivo `.env` — ele já está listado no `.gitignore`.

## Uso

```bash
python main.py                                   # usa a imagem padrão em images/
python main.py caminho/para/outra_imagem.jpg
python main.py images/09_aerea_talhao_escuro_alagado_canal_caminhao.jpeg --propriedade-id PROP-TO-001 --talhao-id T-01
python main.py images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg --no-save   # não salva em disco, só mostra no terminal
python main.py images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg --no-pdf    # salva só o .json, pula o PDF
```

Formatos aceitos: `.jpg`, `.jpeg`, `.png`, `.webp`. Limite de 20 MB por imagem.

Cada execução gera um `vistoria_id` único e, por padrão, salva o dossiê completo
em `output/<vistoria_id>.json` **e** o relatório correspondente em
`output/<vistoria_id>.pdf`. Os campos `propriedade_id` e `talhao_id` existem
para permitir, no futuro, ligar vistorias da mesma propriedade ao longo do tempo
a um desfecho real (ex.: adimplência do crédito).

Flags relacionadas à geração de PDF:
- `--no-save` — não salva nada em disco (nem `.json` nem `.pdf`), só mostra no terminal.
- `--no-pdf` — salva só o `.json`, pula a geração do PDF (útil se o WeasyPrint
  ou suas dependências de sistema não estiverem instaladas no ambiente).

Se o PDF falhar por qualquer motivo (JSON de vistoria incompleto, WeasyPrint
não instalado, etc.), o `.json` já foi salvo antes e o erro é só um aviso —
o processo não é interrompido por causa disso.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | CLI: validação de entrada, orquestração, salvamento do dossiê (JSON + PDF) |
| `gemini_service.py` | Integração com a API do Gemini (SDK `google-genai`), retries e tratamento de erros |
| `prompts.py` | Prompt de auditoria e taxonomia fixa de categorias de anomalia |
| `report.py` | Monta o contexto de apresentação e renderiza o dossiê JSON → HTML → PDF (Jinja2 + WeasyPrint) |
| `templates/report.html` | Template do relatório (layout, tipografia IBM Plex, selo de autenticidade) |

Modelo usado: `gemini-2.5-flash`.

**Nota sobre o WeasyPrint:** além do pacote Python, ele exige bibliotecas de
sistema (pango, cairo, gdk-pixbuf). Se `pip install` funcionar mas a geração
do PDF falhar com erro de biblioteca não encontrada, veja a documentação do
WeasyPrint para o passo de instalação de sistema específico da sua distro —
ou rode com `--no-pdf` enquanto isso não for resolvido.

## Rodando em container (Docker ou Podman)

Guia completo em [DOCKER.md](DOCKER.md) — build, execução, volumes, troca de
chave sem rebuild, Podman/SELinux e erros comuns.

Resumo rápido:
```bash
docker build -t agroaudit .
docker run --rm --env-file .env -v "${PWD}/output:/app/output" agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

## Solução de problemas (execução direta, sem container)

**`403 PERMISSION_DENIED` / `SERVICE_DISABLED`**
A chave veio de um projeto do Google Cloud sem a Gemini API habilitada. Gere
uma chave nova em https://aistudio.google.com/apikey (já vem habilitada).

**`503 UNAVAILABLE` — "high demand"**
O serviço do Gemini está temporariamente sobrecarregado. O programa já tenta
de novo automaticamente; se persistir, espere um pouco e rode de novo.

## Notas de segurança

- A chave de API só é lida de variável de ambiente/`.env` — nunca hardcoded no código.
- Imagens são validadas (formato, integridade, tamanho) antes de qualquer chamada à API.
- `.env`, `output/` e artefatos de build estão no `.gitignore`.