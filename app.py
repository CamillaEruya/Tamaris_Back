"""Interface do dashboard financeiro Taranis Black."""

import base64
from datetime import datetime

import pandas as pd
import streamlit as st

from src.analise_financeira import (
    FormatoComparativoNaoSuportado,
    calcular_indicadores_dashboard,
    gerar_recomendacoes,
    identificar_alertas,
    listar_abas_excel,
    ler_aba_excel,
    preparar_comparativos,
)
from src.visualizacoes import (
    grafico_evolucao,
    grafico_maiores_desvios,
    grafico_orcado_realizado,
)
from src.relatorio_financeiro import gerar_relatorio_html
from src.formatacao import formatar_moeda, formatar_percentual


def _destacar_desfavoravel(linha: pd.Series) -> list[str]:
    """Aplica destaque visual às linhas classificadas como desfavoráveis."""
    estilo = (
        "background-color: #ffe1e1"
        if linha["Classificação"] == "Desfavorável"
        else ""
    )
    return [estilo] * len(linha)


def _preparar_dados_para_exibicao(dados: pd.DataFrame) -> pd.DataFrame:
    """Converte apenas colunas heterogêneas na cópia enviada ao Streamlit."""
    exibicao = dados.copy()
    for coluna in exibicao.columns:
        valores = exibicao[coluna].dropna()
        if (
            pd.api.types.is_object_dtype(exibicao[coluna])
            and valores.map(type).nunique() > 1
        ):
            exibicao[coluna] = exibicao[coluna].map(
                lambda valor: None if pd.isna(valor) else str(valor)
            )
    return exibicao


def _exibir_graficos(dados: pd.DataFrame) -> None:
    st.subheader("Gráficos financeiros")
    grafico_barras = grafico_orcado_realizado(dados)
    if grafico_barras is None:
        st.info("Não há valores comparáveis para gerar o gráfico de barras.")
    else:
        st.plotly_chart(grafico_barras, width="stretch")

    grafico_linhas = grafico_evolucao(dados)
    if grafico_linhas is None:
        st.info(
            "A evolução exige dados trimestrais orçados e realizados. "
            "O total anual não é tratado como um trimestre."
        )
    else:
        if "Anual" in dados["Período"].values:
            st.caption(
                "A evolução temporal exibe apenas T1–T4. O total anual é "
                "comparativo separado e não é somado aos trimestres."
            )
        st.plotly_chart(grafico_linhas, width="stretch")

    grafico_desvios = grafico_maiores_desvios(dados)
    if grafico_desvios is None:
        st.info("Não há desvios desfavoráveis comparáveis para este gráfico.")
    else:
        st.plotly_chart(grafico_desvios, width="stretch")


def _exibir_metricas(dados: pd.DataFrame, periodo: str) -> None:
    metricas = calcular_indicadores_dashboard(dados, periodo)
    st.subheader("Indicadores principais")
    if not metricas:
        st.info("Não há indicadores-resumo completos para o período selecionado.")
        return

    colunas = st.columns(min(len(metricas), 4))
    for indice, (nome, valores) in enumerate(metricas.items()):
        coluna = colunas[indice % len(colunas)]
        if nome == "Maior desvio absoluto":
            coluna.metric(
                f"Maior desvio absoluto — {valores['Indicador']}",
                formatar_moeda(
                    abs(valores["Desvio absoluto (R$)"])
                    if pd.notna(valores["Desvio absoluto (R$)"])
                    else None
                ),
                delta=formatar_percentual(valores["Desvio percentual (%)"]),
            )
        else:
            coluna.metric(
                f"{nome} — realizado",
                formatar_moeda(valores["Realizado (R$)"]),
                delta=(
                    f"Orçado: {formatar_moeda(valores['Orçado (R$)'])} | "
                    f"Desvio: {formatar_moeda(valores['Desvio absoluto (R$)'])} "
                    f"({formatar_percentual(valores['Desvio percentual (%)'])})"
                ),
            )


def _exibir_alertas(dados: pd.DataFrame, limite_percentual: float) -> None:
    st.subheader("Alertas e recomendações")
    alertas = identificar_alertas(dados, limite_percentual)
    if alertas.empty:
        st.success(
            "Nenhum desvio desfavorável com percentual calculável atingiu "
            f"o limite de {limite_percentual:.0f}%."
        )
    else:
        for _, alerta in alertas.iterrows():
            mensagem = (
                f"{alerta['Indicador']} ({alerta['Período']}): "
                f"desvio de {formatar_moeda(alerta['Desvio absoluto (R$)'])} "
                f"({formatar_percentual(alerta['Desvio percentual (%)'])})."
            )
            if alerta["Gravidade"] == "Alta":
                st.error(mensagem)
            else:
                st.warning(mensagem)

    recomendacoes = gerar_recomendacoes(alertas)
    if recomendacoes:
        st.markdown("**Sugestões para avaliação:**")
        for recomendacao in recomendacoes:
            st.markdown(f"- {recomendacao}")
    st.caption(
        "Os alertas e recomendações são gerados por regras de análise "
        "financeira e devem ser avaliados por um responsável humano."
    )


st.set_page_config(
    page_title="Taranis Black | Dashboard Financeiro",
    page_icon="📊",
    layout="wide",
)

st.title("Taranis Black | Dashboard Financeiro")
st.write(
    "Monitoramento de indicadores financeiros e análise de desvios orçamentários"
)

st.header("Importação de Dados Financeiros")
arquivo = st.file_uploader(
    "Selecione uma planilha Excel (.xlsx)",
    type=["xlsx"],
)

if arquivo is None:
    st.info("Envie uma planilha .xlsx para visualizar e analisar seus dados.")
else:
    conteudo = arquivo.getvalue()

    if not conteudo:
        st.warning("O arquivo enviado está vazio. Selecione outra planilha.")
    else:
        try:
            abas = listar_abas_excel(conteudo)
        except Exception as erro:
            st.error(
                "Não foi possível ler o arquivo. Verifique se é uma "
                "planilha .xlsx válida."
            )
            with st.expander("Detalhes técnicos do erro"):
                st.exception(erro)
        else:
            if not abas:
                st.warning("A planilha não contém abas para exibir.")
            else:
                aba_selecionada = st.selectbox("Selecione uma aba", abas)

                try:
                    dados = ler_aba_excel(conteudo, aba_selecionada)
                except Exception as erro:
                    st.error("Ocorreu um erro ao ler a aba selecionada.")
                    with st.expander("Detalhes técnicos do erro"):
                        st.exception(erro)
                else:
                    if dados.empty:
                        st.warning("A aba selecionada está vazia.")

                    col_aba, col_registros, colunas = st.columns(3)
                    col_aba.metric("Aba selecionada", aba_selecionada)
                    col_registros.metric("Registros", len(dados))
                    colunas.metric("Colunas", len(dados.columns))
                    st.dataframe(_preparar_dados_para_exibicao(dados), width="stretch")

                    st.header("Análise Financeira — Orçado × Realizado")
                    try:
                        comparativos = preparar_comparativos(dados)
                    except FormatoComparativoNaoSuportado as erro:
                        st.info(str(erro))
                    except Exception as erro:
                        st.error("Não foi possível preparar a análise financeira.")
                        with st.expander("Detalhes técnicos do erro"):
                            st.exception(erro)
                    else:
                        if comparativos.empty:
                            st.info(
                                "Não há linhas com valores orçados ou realizados "
                                "para comparar nesta aba."
                            )
                        else:
                            st.sidebar.header("Filtros do dashboard")
                            ordem_periodos = ["T1", "T2", "T3", "T4", "Anual"]
                            periodos = [
                                periodo
                                for periodo in ordem_periodos
                                if periodo in comparativos["Período"].values
                            ]
                            categorias = (
                                comparativos["Categoria"].drop_duplicates().tolist()
                            )
                            periodos_selecionados = st.sidebar.multiselect(
                                "Período",
                                options=periodos,
                                default=periodos,
                            )
                            categorias_selecionadas = st.sidebar.multiselect(
                                "Categoria financeira",
                                options=categorias,
                                default=categorias,
                            )
                            dados_filtrados = comparativos[
                                comparativos["Período"].isin(periodos_selecionados)
                                & comparativos["Categoria"].isin(
                                    categorias_selecionadas
                                )
                            ]
                            indicadores = (
                                dados_filtrados["Indicador"].drop_duplicates().tolist()
                            )
                            indicadores_selecionados = st.sidebar.multiselect(
                                "Indicador",
                                options=indicadores,
                                default=indicadores,
                            )
                            limite_alerta = st.sidebar.slider(
                                "Limite percentual para alertas",
                                min_value=0,
                                max_value=100,
                                value=10,
                                step=1,
                                format="%d%%",
                            )
                            dados_filtrados = dados_filtrados[
                                dados_filtrados["Indicador"].isin(
                                    indicadores_selecionados
                                )
                            ]

                            st.header("Dashboard Financeiro")
                            if dados_filtrados.empty:
                                st.info("Nenhum dado corresponde aos filtros.")
                            else:
                                if len(periodos_selecionados) == 1:
                                    periodo_resumo = periodos_selecionados[0]
                                    _exibir_metricas(
                                        dados_filtrados, periodo_resumo
                                    )
                                else:
                                    st.caption(
                                        "Selecione um único período para exibir "
                                        "indicadores-resumo sem misturar períodos."
                                    )

                                _exibir_graficos(dados_filtrados)
                                _exibir_alertas(dados_filtrados, limite_alerta)

                            st.subheader("Tabela de análise")
                            if dados_filtrados.empty:
                                st.info("Nenhum indicador corresponde aos filtros.")
                            else:
                                st.caption(
                                    "O percentual usa o valor orçado com seu sinal "
                                    "original. Como despesas na DRE usam valores "
                                    "negativos, um aumento de despesa pode ter "
                                    "percentual positivo e ser desfavorável."
                                )
                                tabela_formatada = (
                                    dados_filtrados.style.apply(
                                        _destacar_desfavoravel, axis=1
                                    ).format(
                                        {
                                            "Orçado (R$)": formatar_moeda,
                                            "Realizado (R$)": formatar_moeda,
                                            "Desvio absoluto (R$)": formatar_moeda,
                                            "Desvio percentual (%)": formatar_percentual,
                                        },
                                        na_rep="—",
                                    )
                                )
                                st.dataframe(tabela_formatada, width="stretch")

                            st.header("Relatório Executivo")
                            dados_validos_relatorio = dados_filtrados.dropna(
                                subset=["Orçado (R$)", "Realizado (R$)"]
                            )
                            if dados_validos_relatorio.empty:
                                st.info(
                                    "Não há comparativos válidos nos filtros atuais "
                                    "para gerar um relatório."
                                )
                            else:
                                gerado_em = datetime.now().astimezone()
                                try:
                                    relatorio_html = gerar_relatorio_html(
                                        dados_filtrados,
                                        arquivo.name,
                                        limite_alerta,
                                        gerado_em,
                                    )
                                except Exception as erro:
                                    st.error("Não foi possível gerar o relatório.")
                                    with st.expander("Detalhes técnicos do erro"):
                                        st.exception(erro)
                                else:
                                    st.caption(
                                        "Período: "
                                        + ", ".join(
                                            dados_validos_relatorio[
                                                "Período"
                                            ].drop_duplicates()
                                        )
                                        + " | Gerado em "
                                        + gerado_em.strftime("%d/%m/%Y %H:%M:%S %Z")
                                    )
                                    st.download_button(
                                        "Baixar Relatório HTML",
                                        data=relatorio_html.encode("utf-8"),
                                        file_name="relatorio_taranis_black.html",
                                        mime="text/html",
                                        key="baixar_relatorio_html",
                                    )
                                    with st.expander("Prévia do relatório", expanded=True):
                                        html_base64 = base64.b64encode(
                                            relatorio_html.encode("utf-8")
                                        ).decode("ascii")
                                        st.iframe(
                                            f"data:text/html;base64,{html_base64}",
                                            height=760,
                                        )
