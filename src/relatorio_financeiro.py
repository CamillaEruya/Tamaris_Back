"""Geração segura de relatórios executivos financeiros em HTML."""

from datetime import datetime
from html import escape
from typing import Any

import pandas as pd

from src.analise_financeira import (
    calcular_indicadores_dashboard,
    gerar_recomendacoes,
    identificar_alertas,
)
from src.formatacao import formatar_moeda, formatar_percentual


COLUNAS_OBRIGATORIAS = {
    "Indicador",
    "Categoria",
    "Período",
    "Orçado (R$)",
    "Realizado (R$)",
    "Desvio absoluto (R$)",
    "Desvio percentual (%)",
    "Classificação",
}

AVISO_RESPONSABILIDADE = (
    "Este relatório foi gerado automaticamente a partir dos dados financeiros "
    "importados. Os alertas e recomendações utilizam regras matemáticas e "
    "critérios definidos no sistema. Não representam decisões automatizadas "
    "nem previsões de um modelo de inteligência artificial. Os resultados "
    "devem ser conferidos por um responsável humano."
)


def gerar_relatorio_html(
    dados: pd.DataFrame,
    nome_planilha: str,
    limite_percentual: float = 10.0,
    gerado_em: datetime | None = None,
) -> str:
    """Gera relatório HTML com os comparativos já filtrados pela interface.

    O relatório não refaz os cálculos de desvio. Reutiliza a tabela processada
    pelo dashboard e as funções compartilhadas de métricas e alertas.
    """
    colunas_ausentes = COLUNAS_OBRIGATORIAS.difference(dados.columns)
    if colunas_ausentes:
        raise ValueError(
            "A tabela de análise não contém as colunas obrigatórias: "
            + ", ".join(sorted(colunas_ausentes))
        )

    comparaveis = dados.dropna(subset=["Orçado (R$)", "Realizado (R$)"])
    if comparaveis.empty:
        raise ValueError(
            "Não há comparativos com valores orçados e realizados para gerar "
            "um relatório."
        )

    dados_relatorio = dados.copy()
    momento = gerado_em or datetime.now().astimezone()
    data_formatada = momento.astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")
    periodos = (
        dados_relatorio["Período"].dropna().drop_duplicates().astype(str).tolist()
    )
    periodo_formatado = ", ".join(periodos)
    alertas = identificar_alertas(dados_relatorio, limite_percentual)
    recomendacoes = gerar_recomendacoes(alertas)

    indicadores_por_periodo = []
    for periodo in periodos:
        metricas = calcular_indicadores_dashboard(dados_relatorio, periodo)
        if metricas:
            indicadores_por_periodo.append((periodo, metricas))

    resumo_executivo = _gerar_resumo(
        dados_relatorio, alertas, indicadores_por_periodo
    )
    tabela_html = _gerar_tabela(dados_relatorio)
    alertas_html = _gerar_tabela_alertas(alertas, limite_percentual)
    recomendacoes_html = _gerar_recomendacoes(recomendacoes)
    metricas_html = _gerar_metricas(indicadores_por_periodo)
    nome_escapado = escape(str(nome_planilha), quote=True)
    periodo_escapado = escape(periodo_formatado, quote=True)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório Executivo de Análise Financeira — Taranis Black</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, Helvetica, sans-serif; }}
    body {{ margin: 0; background: #f3f6fa; color: #233044; line-height: 1.5; }}
    main {{ max-width: 1180px; margin: 32px auto; padding: 36px; background: #fff;
            box-shadow: 0 4px 24px #172b4d18; }}
    header {{ border-bottom: 4px solid #244c70; padding-bottom: 18px; }}
    h1 {{ margin: 0; color: #183b5b; font-size: 30px; }}
    h2 {{ color: #244c70; margin-top: 32px; border-bottom: 1px solid #d8e0e8;
          padding-bottom: 8px; }}
    h3 {{ color: #315d7e; }}
    .metadata {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
                 gap: 12px; margin-top: 20px; }}
    .metadata div, .metric {{ padding: 14px; background: #f3f6fa; border-radius: 6px; }}
    .label {{ display: block; color: #5b6b7b; font-size: 12px; text-transform: uppercase; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
                gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d8e0e8; padding: 9px 10px; text-align: left; }}
    th {{ background: #244c70; color: #fff; }}
    tbody tr:nth-child(even) {{ background: #f7f9fb; }}
    .desfavoravel {{ color: #9e2929; font-weight: 700; }}
    .favoravel {{ color: #236b43; font-weight: 700; }}
    .alerta {{ border-left: 4px solid #c94c4c; background: #fff3f1;
               margin: 10px 0; padding: 12px 16px; }}
    .gravidade-alta {{ border-color: #9e2929; }}
    .nota {{ margin-top: 36px; padding: 18px; background: #eef3f8;
             border-left: 4px solid #557b9b; font-size: 13px; }}
    .print {{ color: #244c70; margin-top: 18px; }}
    @media print {{
      body {{ background: #fff; }}
      main {{ max-width: none; margin: 0; padding: 10mm; box-shadow: none; }}
      .print {{ display: none; }}
      h2, h3 {{ break-after: avoid; }}
      table, .alerta, .metric {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="label">Taranis Black</p>
    <h1>Relatório Executivo de Análise Financeira</h1>
    <div class="metadata">
      <div><span class="label">Data de geração</span>{escape(data_formatada)}</div>
      <div><span class="label">Período analisado</span>{periodo_escapado}</div>
      <div><span class="label">Planilha utilizada</span>{nome_escapado}</div>
      <div><span class="label">Limite de alerta</span>{formatar_percentual(limite_percentual)}</div>
    </div>
  </header>

  <section>
    <h2>Resumo executivo</h2>
    {resumo_executivo}
    {metricas_html}
  </section>

  <section>
    <h2>Análise orçado × realizado</h2>
    <div class="table-wrap">{tabela_html}</div>
  </section>

  <section>
    <h2>Alertas financeiros</h2>
    {alertas_html}
  </section>

  <section>
    <h2>Recomendações</h2>
    {recomendacoes_html}
  </section>

  <section>
    <h2>Conclusão</h2>
    {_gerar_conclusao(alertas)}
  </section>

  <footer class="nota">{escape(AVISO_RESPONSABILIDADE)}</footer>
  <p class="print">Para imprimir ou salvar como PDF, use a opção Imprimir do navegador.</p>
</main>
</body>
</html>"""


def _gerar_resumo(
    dados: pd.DataFrame,
    alertas: pd.DataFrame,
    indicadores_por_periodo: list[tuple[str, dict[str, dict[str, Any]]]],
) -> str:
    """Resume resultados já calculados sem agregar períodos diferentes."""
    partes = [
        "<p>O relatório apresenta os comparativos financeiros disponíveis "
        "nos filtros selecionados, sem misturar períodos.</p>"
    ]
    if indicadores_por_periodo:
        partes.append(
            "<p>Indicadores-resumo disponíveis para: "
            + ", ".join(
                escape(periodo, quote=True)
                for periodo, _ in indicadores_por_periodo
            )
            + ".</p>"
        )

    desfavoraveis = dados[dados["Classificação"].eq("Desfavorável")].dropna(
        subset=["Desvio absoluto (R$)"]
    )
    if desfavoraveis.empty:
        partes.append("<p>Não há desvios desfavoráveis classificados nos dados filtrados.</p>")
    else:
        maiores = desfavoraveis.assign(
            _magnitude=desfavoraveis["Desvio absoluto (R$)"].abs()
        ).nlargest(3, "_magnitude")
        itens = "".join(
            "<li>"
            f"{escape(str(linha['Indicador']), quote=True)} "
            f"({escape(str(linha['Período']), quote=True)}): "
            f"{formatar_moeda(linha['Desvio absoluto (R$)'])} "
            f"({formatar_percentual(linha['Desvio percentual (%)'])})."
            "</li>"
            for _, linha in maiores.iterrows()
        )
        partes.append("<p>Maiores desvios desfavoráveis:</p><ul>" + itens + "</ul>")
    partes.append(
        f"<p>{len(alertas)} alerta(s) atingem o limite configurado.</p>"
    )
    return "\n".join(partes)


def _gerar_metricas(
    indicadores_por_periodo: list[tuple[str, dict[str, dict[str, Any]]]],
) -> str:
    if not indicadores_por_periodo:
        return "<p>Não há indicadores-resumo completos para os períodos selecionados.</p>"

    blocos = []
    for periodo, metricas in indicadores_por_periodo:
        blocos.append(f"<h3>Indicadores — {escape(periodo, quote=True)}</h3><div class=\"metrics\">")
        for nome, valores in metricas.items():
            if nome == "Maior desvio absoluto":
                titulo = f"Maior desvio absoluto — {valores['Indicador']}"
                realizado = formatar_moeda(
                    abs(valores["Desvio absoluto (R$)"])
                    if pd.notna(valores["Desvio absoluto (R$)"])
                    else None
                )
            else:
                titulo = f"{nome} — realizado"
                realizado = formatar_moeda(valores["Realizado (R$)"])
            blocos.append(
                '<div class="metric">'
                f'<span class="label">{escape(str(titulo), quote=True)}</span>'
                f"<strong>{realizado}</strong><br>"
                f"Orçado: {formatar_moeda(valores['Orçado (R$)'])}<br>"
                f"Desvio: {formatar_moeda(valores['Desvio absoluto (R$)'])} "
                f"({formatar_percentual(valores['Desvio percentual (%)'])})"
                "</div>"
            )
        blocos.append("</div>")
    return "\n".join(blocos)


def _gerar_tabela(dados: pd.DataFrame) -> str:
    cabecalhos = [
        "Indicador",
        "Categoria",
        "Período",
        "Orçado (R$)",
        "Realizado (R$)",
        "Desvio absoluto (R$)",
        "Desvio percentual (%)",
        "Classificação",
    ]
    linhas = []
    for _, linha in dados.iterrows():
        classe = {
            "Desfavorável": "desfavoravel",
            "Favorável": "favoravel",
        }.get(str(linha["Classificação"]), "")
        celulas = [
            escape(str(linha["Indicador"]), quote=True),
            escape(str(linha["Categoria"]), quote=True),
            escape(str(linha["Período"]), quote=True),
            formatar_moeda(linha["Orçado (R$)"]),
            formatar_moeda(linha["Realizado (R$)"]),
            formatar_moeda(linha["Desvio absoluto (R$)"]),
            formatar_percentual(linha["Desvio percentual (%)"]),
            f'<span class="{classe}">{escape(str(linha["Classificação"]), quote=True)}</span>',
        ]
        linhas.append(
            "<tr>" + "".join(f"<td>{celula}</td>" for celula in celulas) + "</tr>"
        )
    return _montar_tabela(cabecalhos, linhas)


def _gerar_tabela_alertas(alertas: pd.DataFrame, limite_percentual: float) -> str:
    if alertas.empty:
        return (
            "<p>Nenhum desvio desfavorável com percentual calculável atingiu "
            f"o limite de {formatar_percentual(limite_percentual)}.</p>"
        )

    blocos = []
    for _, alerta in alertas.iterrows():
        regra = _explicar_regra(alerta)
        gravidade = str(alerta["Gravidade"])
        classe = "gravidade-alta" if gravidade == "Alta" else ""
        blocos.append(
            f'<div class="alerta {classe}"><strong>{escape(str(alerta["Indicador"]), quote=True)}'
            f" — {escape(str(alerta['Período']), quote=True)} "
            f"({escape(gravidade, quote=True)})</strong><br>"
            f"Desvio: {formatar_moeda(alerta['Desvio absoluto (R$)'])} "
            f"({formatar_percentual(alerta['Desvio percentual (%)'])})<br>"
            f"Regra: {escape(regra, quote=True)}</div>"
        )
    return "<div>" + "".join(blocos) + "</div>"


def _explicar_regra(alerta: pd.Series) -> str:
    categoria = str(alerta["Categoria"])
    indicador = str(alerta["Indicador"]).casefold()
    if "ebitda" in indicador:
        return "EBITDA abaixo do orçamento, com desvio desfavorável que atingiu o limite."
    if categoria == "despesa":
        return "Despesa acima do orçamento, com desvio desfavorável que atingiu o limite."
    if categoria == "receita":
        return "Receita abaixo do orçamento, com desvio desfavorável que atingiu o limite."
    return "Desvio classificado como desfavorável que atingiu o limite."


def _gerar_recomendacoes(recomendacoes: list[str]) -> str:
    if not recomendacoes:
        return "<p>Nenhuma recomendação específica foi justificada pelos alertas atuais.</p>"
    return "<ul>" + "".join(
        f"<li>{escape(recomendacao, quote=True)}</li>"
        for recomendacao in recomendacoes
    ) + "</ul>"


def _gerar_conclusao(alertas: pd.DataFrame) -> str:
    if alertas.empty:
        return (
            "<p>Não foram identificados alertas que atinjam o limite configurado "
            "nos dados filtrados. Os resultados devem ser revisados antes de "
            "qualquer decisão.</p>"
        )

    prioridades = alertas.head(3)["Indicador"].drop_duplicates().tolist()
    lista_prioridades = ", ".join(
        escape(str(indicador), quote=True) for indicador in prioridades
    )
    return (
        f"<p>Foram identificados {len(alertas)} alerta(s) que atingem o limite. "
        f"Prioridades para investigação: {lista_prioridades}. "
        "A análise deve considerar o contexto operacional e a qualidade dos "
        "dados antes de definir ações.</p>"
    )


def _montar_tabela(cabecalhos: list[str], linhas: list[str]) -> str:
    cabecalho_html = "".join(
        f"<th>{escape(cabecalho, quote=True)}</th>" for cabecalho in cabecalhos
    )
    return (
        "<table><thead><tr>"
        + cabecalho_html
        + "</tr></thead><tbody>"
        + "".join(linhas)
        + "</tbody></table>"
    )

