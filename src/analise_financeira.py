"""Leitura de planilhas e cálculos comparativos financeiros."""

import re
import unicodedata
from io import BytesIO

import pandas as pd


COLUNAS_COMPARATIVO = [
    "Indicador",
    "Categoria",
    "Período",
    "Orçado (R$)",
    "Realizado (R$)",
    "Desvio absoluto (R$)",
    "Desvio percentual (%)",
    "Classificação",
]

PERIODOS_DRE = ["T1", "T2", "T3", "T4", "Anual"]


class FormatoComparativoNaoSuportado(ValueError):
    """Indica que a aba não contém pares reconhecíveis de orçamento e realizado."""


def listar_abas_excel(conteudo: bytes) -> list[str]:
    """Retorna os nomes das abas de um arquivo Excel no formato .xlsx."""
    if not conteudo:
        raise ValueError("O arquivo recebido está vazio.")

    # BytesIO permite que o Pandas leia os dados em memória sem alterar o arquivo.
    with pd.ExcelFile(BytesIO(conteudo), engine="openpyxl") as planilha:
        return planilha.sheet_names


def ler_aba_excel(conteudo: bytes, nome_aba: str) -> pd.DataFrame:
    """Lê uma aba escolhida e retorna seus dados sem modificá-los."""
    if not conteudo:
        raise ValueError("O arquivo recebido está vazio.")

    return pd.read_excel(
        BytesIO(conteudo),
        sheet_name=nome_aba,
        engine="openpyxl",
    )


def calcular_desvios(orcado: pd.Series, realizado: pd.Series) -> pd.DataFrame:
    """Calcula desvios absolutos e percentuais, preservando ausências."""
    orcado_num = _converter_para_numerico(orcado, "Orçado")
    realizado_num = _converter_para_numerico(realizado, "Realizado")

    desvio = realizado_num - orcado_num
    denominador = orcado_num.where(orcado_num.ne(0))
    percentual = (desvio.div(denominador) * 100).where(
        orcado_num.notna() & realizado_num.notna()
    )
    return pd.DataFrame(
        {
            "Desvio absoluto (R$)": desvio,
            "Desvio percentual (%)": percentual,
        }
    )


def classificar_desvio(
    desvio: float,
    categoria: str,
    orcado: float | None = None,
    realizado: float | None = None,
) -> str:
    """Classifica o desvio conforme a natureza e o sinal contábil do indicador."""
    if pd.isna(desvio):
        return "Sem comparativo"
    if desvio == 0:
        return "Neutro"

    categoria_normalizada = _normalizar_texto(categoria)
    if categoria_normalizada not in {"receita", "despesa", "resultado"}:
        return "Não classificado"

    if categoria_normalizada in {"receita", "resultado"}:
        return "Favorável" if desvio > 0 else "Desfavorável"

    # Na DRE analisada, despesas são registradas com sinal negativo.
    # Se orçamento e realizado tiverem sinais opostos, a regra não é segura.
    if orcado is not None and realizado is not None:
        if pd.notna(orcado) and pd.notna(realizado):
            if orcado * realizado < 0:
                return "Não classificado"
            if orcado < 0:
                return "Desfavorável" if desvio < 0 else "Favorável"
            if orcado > 0:
                return "Desfavorável" if desvio > 0 else "Favorável"

    # Sem orçamento diferente de zero, qualquer gasto realizado é um alerta.
    return "Desfavorável"


def preparar_comparativos(dados: pd.DataFrame) -> pd.DataFrame:
    """Converte uma aba DRE ou de produtos em comparativos sem agregar linhas."""
    if dados.empty:
        return pd.DataFrame(columns=COLUNAS_COMPARATIVO)

    coluna_estrutura = _encontrar_coluna(
        dados, "estrutura contabil conta de resultado"
    )
    coluna_produto = _encontrar_coluna(dados, "linha de produto")

    if coluna_estrutura is not None:
        linhas = _extrair_linhas_dre(dados, coluna_estrutura)
    elif coluna_produto is not None:
        linhas = _extrair_linhas_produto(dados, coluna_produto)
    else:
        raise FormatoComparativoNaoSuportado(
            "A aba não contém uma estrutura reconhecida de comparação "
            "orçado/realizado. A análise está disponível para a DRE e a "
            "tabela de linhas de produto."
        )

    if not linhas:
        return pd.DataFrame(columns=COLUNAS_COMPARATIVO)

    tabela = pd.DataFrame(linhas)
    desvios = calcular_desvios(tabela["Orçado (R$)"], tabela["Realizado (R$)"])
    tabela["Desvio absoluto (R$)"] = desvios["Desvio absoluto (R$)"]
    tabela["Desvio percentual (%)"] = desvios["Desvio percentual (%)"]
    tabela["Classificação"] = [
        classificar_desvio(desvio, categoria, orcado, realizado)
        for desvio, categoria, orcado, realizado in zip(
            tabela["Desvio absoluto (R$)"],
            tabela["Categoria"],
            tabela["Orçado (R$)"],
            tabela["Realizado (R$)"],
        )
    ]
    return tabela[COLUNAS_COMPARATIVO]


def obter_indicadores_resumo(
    tabela: pd.DataFrame, periodo: str
) -> pd.DataFrame:
    """Retorna totais explícitos da planilha, sem somá-los aos componentes."""
    resumos = {
        "total receita bruta": "Receita bruta total",
        "ebitda resultado operacional antes de juros imp": "EBITDA",
        "lucro liquido do exercicio": "Lucro líquido do exercício",
        "total taranis black": "Receita total por produto",
    }
    linhas_resumo = []

    for indicador_normalizado, nome_exibicao in resumos.items():
        correspondencias = tabela[
            (tabela["Período"] == periodo)
            & tabela["Indicador"].map(_normalizar_texto).eq(indicador_normalizado)
        ]
        # Só exibe um valor quando existe uma única linha-fonte inequívoca.
        if (
            len(correspondencias) == 1
            and correspondencias["Orçado (R$)"].notna().all()
            and correspondencias["Realizado (R$)"].notna().all()
        ):
            linha = correspondencias.iloc[0].copy()
            linha["Indicador"] = nome_exibicao
            linhas_resumo.append(linha)

    return pd.DataFrame(linhas_resumo, columns=COLUNAS_COMPARATIVO)


def identificar_alertas(
    tabela: pd.DataFrame, limite_percentual: float = 10.0
) -> pd.DataFrame:
    """Identifica alertas desfavoráveis que atingem o limite percentual.

    Somente linhas classificadas como despesa, receita ou EBITDA são avaliadas.
    Linhas sem percentual calculável, inclusive orçamento zero, não geram alerta
    percentual, pois não há base segura para medir o limite.
    Alertas de pelo menos duas vezes o limite configurado recebem gravidade alta.
    """
    if limite_percentual < 0:
        raise ValueError("O limite percentual não pode ser negativo.")

    colunas_alerta = [
        "Indicador",
        "Categoria",
        "Período",
        "Orçado (R$)",
        "Realizado (R$)",
        "Desvio absoluto (R$)",
        "Desvio percentual (%)",
        "Classificação",
        "Gravidade",
    ]
    if tabela.empty:
        return pd.DataFrame(columns=colunas_alerta)

    indicadores_normalizados = tabela["Indicador"].map(_normalizar_texto)
    e_ebitda = indicadores_normalizados.str.contains("ebitda", regex=False)
    elegiveis = tabela["Categoria"].isin(["receita", "despesa"]) | e_ebitda
    desfavoraveis = tabela["Classificação"].eq("Desfavorável")
    percentuais = pd.to_numeric(
        tabela["Desvio percentual (%)"], errors="coerce"
    )
    atinge_limite = percentuais.abs().ge(limite_percentual)
    alertas = tabela.loc[elegiveis & desfavoraveis & atinge_limite].copy()
    alertas["Gravidade"] = percentuais.loc[alertas.index].abs().ge(
        limite_percentual * 2
    ).map({True: "Alta", False: "Atenção"})
    return alertas[colunas_alerta].sort_values(
        "Desvio percentual (%)",
        key=lambda valores: valores.abs(),
        ascending=False,
    )


def gerar_recomendacoes(alertas: pd.DataFrame) -> list[str]:
    """Gera sugestões textuais para avaliação humana a partir dos alertas."""
    if alertas.empty:
        return []

    indicadores = alertas["Indicador"].map(_normalizar_texto)
    recomendacoes = []
    regras = [
        (
            ("frete", "logistica"),
            "Revisar contratos de frete, rotas e condições logísticas para "
            "investigar o aumento dos custos.",
        ),
        (
            ("reentrega", "multa"),
            "Investigar falhas operacionais que possam estar causando "
            "reentregas e multas.",
        ),
        (
            ("pdd", "inadimplencia", "devedores duvidosos"),
            "Revisar os processos de análise de crédito e acompanhamento "
            "da inadimplência.",
        ),
        (
            ("ebitda",),
            "Investigar as despesas e as margens operacionais que podem "
            "explicar o EBITDA abaixo do orçamento.",
        ),
    ]
    for termos, recomendacao in regras:
        if indicadores.map(
            lambda indicador: any(termo in indicador for termo in termos)
        ).any():
            recomendacoes.append(recomendacao)
    return recomendacoes


def calcular_indicadores_dashboard(
    tabela: pd.DataFrame, periodo: str
) -> dict[str, dict[str, object]]:
    """Calcula métricas sem somar totais reportados aos seus componentes."""
    dados = tabela[tabela["Período"].eq(periodo)]
    metricas: dict[str, dict[str, object]] = {}
    resumos = obter_indicadores_resumo(dados, periodo)

    receitas = resumos[
        resumos["Indicador"].isin(
            ["Receita bruta total", "Receita total por produto"]
        )
    ]
    if len(receitas) == 1:
        metricas["Receita"] = _valores_metrica(receitas.iloc[0])

    ebitdas = dados[
        dados["Indicador"].map(_normalizar_texto).str.contains(
            "ebitda", regex=False
        )
    ]
    if len(ebitdas) == 1:
        metricas["EBITDA"] = _valores_metrica(ebitdas.iloc[0])

    despesas = dados[dados["Categoria"].eq("despesa")]
    despesas = despesas[
        ~despesas["Indicador"].map(_normalizar_texto).map(_eh_totalizador)
    ]
    if (
        not despesas.empty
        and despesas["Orçado (R$)"].notna().all()
        and despesas["Realizado (R$)"].notna().all()
    ):
        orcado = despesas["Orçado (R$)"].sum(min_count=1)
        realizado = despesas["Realizado (R$)"].sum(min_count=1)
        desvios = calcular_desvios(
            pd.Series([orcado]), pd.Series([realizado])
        ).iloc[0]
        metricas["Despesas (linhas incluídas no filtro)"] = {
            "Orçado (R$)": orcado,
            "Realizado (R$)": realizado,
            "Desvio absoluto (R$)": desvios["Desvio absoluto (R$)"],
            "Desvio percentual (%)": desvios["Desvio percentual (%)"],
        }

    desvios_validos = dados.dropna(subset=["Desvio absoluto (R$)"])
    if not desvios_validos.empty:
        indice = desvios_validos["Desvio absoluto (R$)"].abs().idxmax()
        metricas["Maior desvio absoluto"] = _valores_metrica(dados.loc[indice])

    return metricas


def _valores_metrica(linha: pd.Series) -> dict[str, object]:
    return {
        "Indicador": linha["Indicador"],
        "Orçado (R$)": linha["Orçado (R$)"],
        "Realizado (R$)": linha["Realizado (R$)"],
        "Desvio absoluto (R$)": linha["Desvio absoluto (R$)"],
        "Desvio percentual (%)": linha["Desvio percentual (%)"],
    }


def _eh_totalizador(indicador: str) -> bool:
    return indicador.startswith(("total ", "subtotal "))


def _extrair_linhas_dre(
    dados: pd.DataFrame, coluna_indicador: str
) -> list[dict[str, object]]:
    pares = []
    for periodo in PERIODOS_DRE[:4]:
        orcado = _encontrar_coluna(dados, f"{periodo.lower()} orcado")
        realizado = _encontrar_coluna(dados, f"{periodo.lower()} realizado")
        if orcado is not None and realizado is not None:
            pares.append((periodo, orcado, realizado))

    orcado_anual = _encontrar_coluna(dados, "total anual orcado")
    realizado_anual = _encontrar_coluna(dados, "total anual realizado")
    if orcado_anual is not None and realizado_anual is not None:
        pares.append(("Anual", orcado_anual, realizado_anual))
    if not pares:
        raise FormatoComparativoNaoSuportado(
            "A aba da DRE não contém colunas compatíveis de orçamento e realizado."
        )

    linhas = []
    secao = ""
    for _, registro in dados.iterrows():
        indicador = registro[coluna_indicador]
        if pd.isna(indicador):
            continue
        indicador = str(indicador).strip()
        indicador_normalizado = _normalizar_texto(indicador)
        if re.match(r"^[1-4]\s", indicador_normalizado):
            secao = indicador_normalizado
            continue

        categoria = _categorizar_linha_dre(indicador_normalizado, secao)
        for periodo, coluna_orcado, coluna_realizado in pares:
            valor_orcado = _converter_valor(
                registro[coluna_orcado], coluna_orcado, indicador
            )
            valor_realizado = _converter_valor(
                registro[coluna_realizado], coluna_realizado, indicador
            )
            if pd.isna(valor_orcado) and pd.isna(valor_realizado):
                continue
            linhas.append(
                {
                    "Indicador": indicador,
                    "Categoria": categoria,
                    "Período": periodo,
                    "Orçado (R$)": valor_orcado,
                    "Realizado (R$)": valor_realizado,
                }
            )
    return linhas


def _extrair_linhas_produto(
    dados: pd.DataFrame, coluna_indicador: str
) -> list[dict[str, object]]:
    coluna_orcado = _encontrar_coluna(dados, "orcado anual")
    coluna_realizado = _encontrar_coluna(dados, "realizado anual")
    if coluna_orcado is None or coluna_realizado is None:
        raise FormatoComparativoNaoSuportado(
            "A aba de produtos não contém os dois campos anuais necessários."
        )

    linhas = []
    for _, registro in dados.iterrows():
        indicador = registro[coluna_indicador]
        if pd.isna(indicador):
            continue
        indicador = str(indicador).strip()
        valor_orcado = _converter_valor(
            registro[coluna_orcado], coluna_orcado, indicador
        )
        valor_realizado = _converter_valor(
            registro[coluna_realizado], coluna_realizado, indicador
        )
        if pd.isna(valor_orcado) and pd.isna(valor_realizado):
            continue
        linhas.append(
            {
                "Indicador": indicador,
                "Categoria": "receita",
                "Período": "Anual",
                "Orçado (R$)": valor_orcado,
                "Realizado (R$)": valor_realizado,
            }
        )
    return linhas


def _categorizar_linha_dre(indicador: str, secao: str) -> str:
    if any(palavra in indicador for palavra in ("ebitda", "lucro")):
        return "resultado"
    if secao.startswith("1 ") or "receita" in indicador:
        return "receita"
    termos_despesa = (
        "despesa",
        "custo",
        "imposto",
        "deducao",
        "cancelamento",
        "devolucao",
        "reentrega",
        "multa",
        "provisao",
        "irpj",
        "csll",
    )
    if (
        secao.startswith(("2 ", "3 ", "4 "))
        or any(palavra in indicador for palavra in termos_despesa)
    ):
        return "despesa"
    return "não classificado"


def _encontrar_coluna(dados: pd.DataFrame, prefixo_normalizado: str) -> str | None:
    correspondencias = [
        coluna
        for coluna in dados.columns
        if _normalizar_texto(str(coluna)).startswith(prefixo_normalizado)
    ]
    if len(correspondencias) > 1:
        raise ValueError(
            f"Mais de uma coluna corresponde ao campo '{prefixo_normalizado}'."
        )
    return correspondencias[0] if correspondencias else None


def _normalizar_texto(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(
        caractere for caractere in sem_acentos if not unicodedata.combining(caractere)
    )
    sem_pontuacao = re.sub(r"[^a-zA-Z0-9]+", " ", sem_acentos).lower()
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


def _converter_valor(valor: object, coluna: str, indicador: str) -> float:
    convertido = _converter_para_numerico(
        pd.Series([valor]), f"{coluna} ({indicador})"
    )
    return convertido.iloc[0]


def _converter_para_numerico(serie: pd.Series, nome: str) -> pd.Series:
    numerica = pd.to_numeric(serie, errors="coerce")
    invalido = serie.notna() & numerica.isna()
    if invalido.any():
        raise ValueError(f"O campo '{nome}' contém valores não numéricos.")
    return numerica
