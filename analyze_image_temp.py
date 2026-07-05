import os
import json
import re
from io import BytesIO
from PIL import Image
import google.generativeai as genai

prompt = """Você é um sistema especializado em análise de imagens aéreas para auditoria rural. Seus relatórios são usados como evidência técnica em processos de crédito rural, auditorias bancárias e processos judiciais no Brasil.

REGRA FUNDAMENTAL: você nunca inventa ou estima sem base visual direta. Para cada campo use exatamente um destes estados:
- \"confirmado\" — visível e identificável com clareza
- \"estimado\" — visível mas com incerteza (sempre declare a margem)
- \"não identificável\" — ausente no frame ou resolução insuficiente

Analise a imagem fornecida e retorne APENAS um JSON válido, sem texto adicional, sem markdown, sem backticks, seguindo exatamente esta estrutura:

{
  \"uso_do_solo\": {
    \"tipo_principal\": string,
    \"status\": \"confirmado\" | \"estimado\" | \"não identificável\",
    \"cobertura_vegetal\": \"densa\" | \"parcial\" | \"escassa\" | \"ausente\",
    \"solo_exposto\": \"sim\" | \"não\" | \"parcial\",
    \"sinais_de_queimada\": \"sim\" | \"não\" | \"indícios\",
    \"condicao_vegetacao\": \"saudável\" | \"estressada\" | \"degradada\" | \"não identificável\",
    \"observacoes\": string
  },
  \"rebanho\": {
    \"detectado\": true | false,
    \"contagem_estimada\": número ou null,
    \"margem_de_erro\": string ou null,
    \"confianca\": \"alta\" | \"média\" | \"baixa\" | \"não aplicável\",
    \"distribuicao\": string ou \"não detectado\",
    \"comportamento\": string ou \"não detectado\"
  },
  \"infraestrutura\": {
    \"cercas\": \"presente\" | \"ausente\" | \"parcialmente visível\" | \"fora do frame\",
    \"estradas\": \"presente\" | \"ausente\" | \"parcialmente visível\" | \"fora do frame\",
    \"construcoes\": \"presente\" | \"ausente\" | \"parcialmente visível\" | \"fora do frame\",
    \"corpos_dagua\": \"presente\" | \"ausente\" | \"parcialmente visível\" | \"fora do frame\",
    \"bebedouros\": \"presente\" | \"ausente\" | \"parcialmente visível\" | \"fora do frame\",
    \"condicao_geral\": \"boa\" | \"regular\" | \"precária\" | \"não identificável\"
  },
  \"anomalias\": [
    {
      \"descricao\": string,
      \"localizacao_aproximada\": string,
      \"severidade\": \"baixa\" | \"média\" | \"alta\",
      \"status\": \"confirmado\" | \"indício\"
    }
  ],
  \"aptidao_garantia\": {
    \"score\": número de 0 a 100,
    \"classificacao\": \"apto\" | \"apto com ressalvas\" | \"inapto\" | \"indeterminado\",
    \"justificativa\": string citando especificamente o que foi observado,
    \"campos_nao_identificaveis\": número
  },
  \"limitacoes_da_analise\": [string],
  \"recomendacoes_auditor\": [
    {
      \"acao\": string,
      \"motivo\": string,
      \"urgencia\": \"baixa\" | \"média\" | \"alta\"
    }
  ]
}

REGRAS ADICIONAIS:
1. limitacoes_da_analise nunca pode estar vazio. Toda imagem tem limitações.
2. Cada recomendacao_auditor deve ter motivo diretamente ligado a algo observado ou não observado nesta imagem.
3. Se campos_nao_identificaveis for maior que 4, a classificacao deve ser obrigatoriamente \"indeterminado\".
4. Contagem de rebanho sempre com margem de erro explícita. Nunca um número exato.
5. anomalias: só liste o que é visualmente verificável. Lista vazia é preferível a anomalia inventada."""

api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise RuntimeError('GEMINI_API_KEY não encontrada')

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

with open('images/preview.jpg', 'rb') as f:
    img_bytes = f.read()

image = Image.open(BytesIO(img_bytes))
response = model.generate_content([prompt, image])
text = response.text.strip()

match = re.search(r'\{.*\}', text, re.S)
if match:
    candidate = match.group(0)
    try:
        data = json.loads(candidate)
    except Exception:
        data = json.loads(candidate.replace('```json', '').replace('```', ''))
    print(json.dumps(data, ensure_ascii=False, indent=2))
else:
    print(text)
