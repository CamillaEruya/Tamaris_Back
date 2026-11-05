"""Gráficos Plotly para os comparativos financeiros."""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from src.formatacao import formatar_moeda


ORDEM_PERIODOS = ["T1", "T2", "T3", "T4"]


def grafico_orcado_realizado(dados: pd.DataFrame) -> go.Figure | None:
    """Cria barras agrupadas sem agregar indicadores ou períodos."""
    validos = dados.dropna(subset=["Orçado (R$)", "Realizado (R$)"])
    if validos.empty:
        return None

    fig = go.Figure()
    rotulos = [
        f"{linha.Indicador} — {linha.Período}"
        for linha in validos.itertuples(index=False)
    ]
    for coluna, nome, cor in (
        ("Orçado (R$)", "Orçado", "#3973ac"),
        ("Realizado (R$)", "Realizado", "#ed9b40"),
    ):
        valores = validos[coluna].tolist()
        fig.add_trace(
            go.Bar(
                name=nome,
                x=rotulos,
                y=valores,
                text=[formatar_moeda(valor) for valor in valores],
                textposition="auto",
                marker_color=cor,
                customdata=validos[["Indicador", "Período"]].to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}<br>Período: %{customdata[1]}"
                    f"<br>{nome}: R$ %{{y:,.2f}}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="Orçado × Realizado",
        barmode="group",
        xaxis_title="Indicador e período",
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        legend_title="Série",
        template="plotly_white",
    )
    return fig


def grafico_evolucao(dados: pd.DataFrame) -> go.Figure | None:
    """Mostra a evolução trimestral; o total anual não é um trimestre."""
    trimestrais = dados[dados["Período"].isin(ORDEM_PERIODOS)].copy()
    if trimestrais.empty:
        return None

    longo = trimestrais.melt(
        id_vars=["Indicador", "Categoria", "Período"],
        value_vars=["Orçado (R$)", "Realizado (R$)"],
        var_name="Série",
        value_name="Valor (R$)",
    ).dropna(subset=["Valor (R$)"])
    if longo.empty:
        return None

    fig = px.line(
        longo,
        x="Período",
        y="Valor (R$)",
        color="Indicador",
        line_dash="Série",
        markers=True,
        category_orders={"Período": ORDEM_PERIODOS},
        hover_data=["Categoria"],
        template="plotly_white",
        title="Evolução trimestral",
    )
    fig.update_layout(
        xaxis_title="Período",
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        legend_title="Indicador / série",
    )
    return fig


def grafico_maiores_desvios(dados: pd.DataFrame, limite: int = 10) -> go.Figure | None:
    """Ordena os maiores desvios desfavoráveis pela magnitude absoluta."""
    desfavoraveis = dados[
        dados["Classificação"].eq("Desfavorável")
    ].dropna(subset=["Desvio absoluto (R$)"])
    if desfavoraveis.empty:
        return None

    maiores = desfavoraveis.assign(
        Magnitude=desfavoraveis["Desvio absoluto (R$)"].abs()
    ).nlargest(limite, "Magnitude")
    maiores = maiores.sort_values("Magnitude", ascending=True)
    rotulos = [
        f"{linha.Indicador} — {linha.Período}"
        for linha in maiores.itertuples(index=False)
    ]
    fig = go.Figure(
        go.Bar(
            x=maiores["Magnitude"],
            y=rotulos,
            orientation="h",
            marker_color="#c94c4c",
            text=[formatar_moeda(valor) for valor in maiores["Magnitude"]],
            textposition="auto",
            customdata=maiores[
                ["Desvio absoluto (R$)", "Desvio percentual (%)", "Categoria"]
            ].to_numpy(),
            hovertemplate=(
                "%{y}<br>Magnitude: R$ %{x:,.2f}"
                "<br>Desvio assinado: R$ %{customdata[0]:,.2f}"
                "<br>Desvio percentual: %{customdata[1]:.2f}%"
                "<br>Categoria: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="Maiores desvios financeiros desfavoráveis",
        xaxis_title="Magnitude do desvio desfavorável (R$)",
        yaxis_title="Indicador e período",
        xaxis_tickprefix="R$ ",
        xaxis_tickformat=",.0f",
        template="plotly_white",
    )
    return fig
