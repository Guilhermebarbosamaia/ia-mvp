"""
report.py — AgroAudit: transforma o JSON de vistoria (saída da IA) em HTML/PDF.

Responsabilidades:
- Validar/normalizar o JSON de entrada (schema descrito no briefing do produto).
- Derivar campos de apresentação que o template Jinja2 não deveria calcular
  (rótulos de estado, classes CSS de severidade/aptidão, hash de selo etc).
- Renderizar o template Jinja2 -> HTML.
- Opcionalmente converter HTML -> PDF via WeasyPrint.

Uso típico (ver também gerar_relatorio.py para uso via linha de comando):

    from report import gerar_html, gerar_pdf

    html = gerar_html(dados_vistoria)
    gerar_pdf(dados_vistoria, "output/VST-2026-0741.pdf")
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Estados de honestidade aceitos por campo. Qualquer outro valor recebido do
# JSON é tratado como "não identificável" (fail-safe: nunca assumir confirmado).
ESTADO_LABELS = {
    "confirmado": "Confirmado",
    "estimado": "Estimado",
    "nao_identificavel": "Não identificável",
}

# Classificações de aptidão aceitas -> classe CSS correspondente no template.
# NUNCA inclua aqui nenhum mapeamento numérico/score — a classificação é
# estritamente qualitativa, por exigência de produto.
APTIDAO_CSS = {
    "apto": "apto",
    "apto com ressalvas": "apto_com_ressalvas",
    "inapto": "inapto",
    "indeterminado": "indeterminado",
}


class VistoriaValidationError(ValueError):
    """Levantado quando o JSON de entrada não atende ao schema mínimo esperado."""


def humanizar(value: Any) -> Any:
    """Formata um valor cru do schema (categorias/enums em minúsculo ou
    snake_case, ex.: 'solo_exposto', 'sim', 'boa') para exibição: troca
    underscore por espaço e garante a primeira letra maiúscula. Não altera
    valores que não sejam string (None, número, etc. passam direto), nem o
    travessão "—" usado como placeholder de campo vazio.
    """
    if not isinstance(value, str) or not value or value == "—":
        return value
    texto = value.replace("_", " ")
    return texto[0].upper() + texto[1:]


def _get_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["humanizar"] = humanizar
    return env


def _estado(value: str | None) -> str:
    """Normaliza um valor de estado de campo para uma das 3 chaves válidas.
    O schema real usa "não identificável" (com acento/espaço) como valor de
    status \u2014 mapeamos para a chave interna "nao_identificavel"."""
    if value in ESTADO_LABELS:
        return value
    if value == "não identificável":
        return "nao_identificavel"
    return "nao_identificavel"


def _campo(label: str, value: Any, estado: str | None) -> dict:
    """Monta um campo de exibição {label, value, estado, estado_label} para o template.
    Usado apenas onde o schema real traz um indicador de confiabilidade próprio
    (hoje: analise.uso_do_solo.status)."""
    est = _estado(estado)
    display_value = humanizar(value) if value not in (None, "") else "—"
    return {
        "label": label,
        "value": display_value,
        "estado": est,
        "estado_label": ESTADO_LABELS[est],
    }


def _campo_simples(label: str, value: Any) -> dict:
    """Campo de exibição sem tag de confiabilidade — para dados que o schema
    real não acompanha de um indicador de confiança próprio (ex.: cobertura
    vegetal, cercas). NUNCA fabrique um estado aqui."""
    display_value = humanizar(value) if value not in (None, "") else "—"
    return {"label": label, "value": display_value}


def _hash_selo(vistoria_id: str, data_vistoria_utc: str) -> str:
    """
    Gera um selo curto e determinístico a partir do ID da vistoria + timestamp,
    para exibição no rodapé. Isto NÃO é uma assinatura criptográfica — é apenas
    um identificador de conferência visual/rastreabilidade do documento gerado.
    Se a instituição exigir assinatura digital/verificação forte, assine o PDF
    final separadamente (ex.: com certificado ICP-Brasil) fora deste template.
    """
    raw = f"{vistoria_id}|{data_vistoria_utc}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:8].upper()


def _validar(dados: dict) -> None:
    obrigatorios = [
        "vistoria_id",
        "propriedade_id",
        "talhao_id",
        "data_vistoria_utc",
        "modelo_ia",
        "analise",
    ]
    faltantes = [campo for campo in obrigatorios if campo not in dados]
    if faltantes:
        raise VistoriaValidationError(
            f"JSON de vistoria incompleto. Campos obrigatórios ausentes: {faltantes}"
        )

    analise = dados.get("analise", {})
    secoes_obrigatorias = [
        "uso_do_solo",
        "rebanho",
        "infraestrutura",
        "anomalias",
        "aptidao_garantia",
        "limitacoes_da_analise",
        "recomendacoes_auditor",
    ]
    faltantes_secao = [s for s in secoes_obrigatorias if s not in analise]
    if faltantes_secao:
        raise VistoriaValidationError(
            f"Bloco 'analise' incompleto. Seções ausentes: {faltantes_secao}"
        )

    classificacao = analise.get("aptidao_garantia", {}).get("classificacao")
    if classificacao not in APTIDAO_CSS:
        raise VistoriaValidationError(
            "aptidao_garantia.classificacao deve ser um dos valores qualitativos "
            f"aceitos {list(APTIDAO_CSS.keys())}; recebido: {classificacao!r}. "
            "O sistema não aceita score numérico neste campo."
        )


def montar_contexto(dados: dict) -> dict:
    """
    Recebe o JSON de vistoria (já carregado como dict) e retorna o contexto
    pronto para o template Jinja2, com os campos derivados de apresentação.
    """
    _validar(dados)
    analise = dados["analise"]

    # Uso do Solo: o schema real só carrega confiabilidade no campo "status"
    # (nível da seção). Os demais campos são descritivos e NÃO recebem tag —
    # fabricar um estado por campo aqui daria uma falsa impressão de precisão.
    uso_solo = analise.get("uso_do_solo", {})
    uso_do_solo_status_tag = _campo("Status", uso_solo.get("status"), uso_solo.get("status"))
    uso_do_solo_fields = [
        _campo_simples("Tipo principal", uso_solo.get("tipo_principal")),
        _campo_simples("Cobertura vegetal", uso_solo.get("cobertura_vegetal")),
        _campo_simples("Solo exposto", uso_solo.get("solo_exposto")),
        _campo_simples("Sinais de queimada", uso_solo.get("sinais_de_queimada")),
        _campo_simples("Condição da vegetação", uso_solo.get("condicao_vegetacao")),
    ]

    # Infraestrutura: o schema real não traz nenhum indicador de confiabilidade
    # por campo — mostrar como grid simples, sem tag. "condicao_geral" segue
    # exibida como resumo textual no rodapé da seção (já implementado no template).
    infra = analise.get("infraestrutura", {})
    infraestrutura_fields = [
        _campo_simples("Cercas", infra.get("cercas")),
        _campo_simples("Estradas", infra.get("estradas")),
        _campo_simples("Construções", infra.get("construcoes")),
        _campo_simples("Corpos d\u2019água", infra.get("corpos_dagua")),
        _campo_simples("Bebedouros", infra.get("bebedouros")),
    ]

    aptidao = analise.get("aptidao_garantia", {})

    return {
        "vistoria_id": dados.get("vistoria_id"),
        "propriedade_id": dados.get("propriedade_id"),
        "talhao_id": dados.get("talhao_id"),
        "data_vistoria_utc": dados.get("data_vistoria_utc"),
        "imagem_analisada": dados.get("imagem_analisada"),
        "modelo_ia": dados.get("modelo_ia"),
        "analise": analise,
        "uso_do_solo_status_tag": uso_do_solo_status_tag,
        "uso_do_solo_fields": uso_do_solo_fields,
        "infraestrutura_fields": infraestrutura_fields,
        "aptidao_css_class": APTIDAO_CSS[aptidao["classificacao"]],
        "hash_selo": _hash_selo(dados.get("vistoria_id", ""), dados.get("data_vistoria_utc", "")),
    }


def gerar_html(dados: dict, template_name: str = "report.html") -> str:
    """Renderiza o HTML final a partir do JSON de vistoria (dict já carregado)."""
    env = _get_env()
    template = env.get_template(template_name)
    contexto = montar_contexto(dados)
    return template.render(**contexto)


def gerar_pdf(dados: dict, output_path: str | os.PathLike, template_name: str = "report.html") -> Path:
    """
    Renderiza o HTML e converte para PDF via WeasyPrint, salvando em output_path.
    Requer o pacote `weasyprint` instalado (e suas dependências de sistema:
    pango, cairo, gdk-pixbuf — ver documentação do WeasyPrint por plataforma).
    """
    from weasyprint import HTML  # import local: só exige a dependência quando usada

    html_str = gerar_html(dados, template_name=template_name)
    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf(str(destino))
    return destino
