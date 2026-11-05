import unittest

import pandas as pd

from src.analise_financeira import (
    calcular_desvios,
    calcular_indicadores_dashboard,
    classificar_desvio,
    gerar_recomendacoes,
    identificar_alertas,
    obter_indicadores_resumo,
    preparar_comparativos,
)


class CalculoDesviosTests(unittest.TestCase):
    def test_desvio_positivo(self):
        resultado = calcular_desvios(
            pd.Series([100.0]),
            pd.Series([125.0]),
        )

        self.assertEqual(resultado.loc[0, "Desvio absoluto (R$)"], 25.0)
        self.assertEqual(resultado.loc[0, "Desvio percentual (%)"], 25.0)

    def test_desvio_negativo(self):
        resultado = calcular_desvios(
            pd.Series([100.0]),
            pd.Series([80.0]),
        )

        self.assertEqual(resultado.loc[0, "Desvio absoluto (R$)"], -20.0)
        self.assertEqual(resultado.loc[0, "Desvio percentual (%)"], -20.0)

    def test_orcamento_zero_nao_produz_percentual_infinito(self):
        resultado = calcular_desvios(
            pd.Series([0.0]),
            pd.Series([10.0]),
        )

        self.assertEqual(resultado.loc[0, "Desvio absoluto (R$)"], 10.0)
        self.assertTrue(pd.isna(resultado.loc[0, "Desvio percentual (%)"]))

    def test_valores_ausentes_sao_preservados(self):
        resultado = calcular_desvios(
            pd.Series([100.0, None]),
            pd.Series([None, 50.0]),
        )

        self.assertTrue(resultado.isna().all().all())

    def test_classificacao_considera_natureza_e_sinal_da_despesa(self):
        self.assertEqual(
            classificar_desvio(20.0, "receita", 100.0, 120.0),
            "Favorável",
        )
        self.assertEqual(
            classificar_desvio(-20.0, "receita", 100.0, 80.0),
            "Desfavorável",
        )
        self.assertEqual(
            classificar_desvio(-20.0, "despesa", -100.0, -120.0),
            "Desfavorável",
        )
        self.assertEqual(
            classificar_desvio(20.0, "despesa", -100.0, -80.0),
            "Favorável",
        )
        self.assertEqual(
            classificar_desvio(-20.0, "resultado", 100.0, 80.0),
            "Desfavorável",
        )

    def test_total_explicito_nao_e_somado_uma_segunda_vez(self):
        dados = pd.DataFrame(
            [
                ["1. RECEITA BRUTA DE VENDAS", None, None, None, None],
                ["Receita Canal A", 100.0, 100.0, 100.0, 100.0],
                ["Receita Canal B", 100.0, 100.0, 100.0, 100.0],
                ["TOTAL RECEITA BRUTA", 200.0, 200.0, 225.0, 220.0],
            ],
            columns=[
                "Estrutura Contábil / Conta de Resultado",
                "T1 Orçado (R$)",
                "T1 Realizado (R$)",
                "TOTAL ANUAL ORÇADO",
                "TOTAL ANUAL REALIZADO",
            ],
        )

        comparativos = preparar_comparativos(dados)
        resumo = obter_indicadores_resumo(comparativos, "Anual")

        self.assertEqual(len(comparativos), 6)
        self.assertEqual(len(resumo), 1)
        # O resumo usa o total informado, não a soma dos componentes (200).
        self.assertEqual(resumo.iloc[0]["Realizado (R$)"], 220.0)
        self.assertEqual(resumo.iloc[0]["Desvio absoluto (R$)"], -5.0)

    def test_alertas_respeitam_limite_percentual_de_dez_porcento(self):
        dados = pd.DataFrame(
            [
                {
                    "Indicador": "Fretes e Logística",
                    "Categoria": "despesa",
                    "Período": "Anual",
                    "Orçado (R$)": -100.0,
                    "Realizado (R$)": -115.0,
                    "Desvio absoluto (R$)": -15.0,
                    "Desvio percentual (%)": 15.0,
                    "Classificação": "Desfavorável",
                },
                {
                    "Indicador": "Receita Bruta",
                    "Categoria": "receita",
                    "Período": "Anual",
                    "Orçado (R$)": 100.0,
                    "Realizado (R$)": 85.0,
                    "Desvio absoluto (R$)": -15.0,
                    "Desvio percentual (%)": -15.0,
                    "Classificação": "Desfavorável",
                },
                {
                    "Indicador": "EBITDA",
                    "Categoria": "resultado",
                    "Período": "Anual",
                    "Orçado (R$)": 100.0,
                    "Realizado (R$)": 85.0,
                    "Desvio absoluto (R$)": -15.0,
                    "Desvio percentual (%)": -15.0,
                    "Classificação": "Desfavorável",
                },
                {
                    "Indicador": "Reentregas e multas",
                    "Categoria": "despesa",
                    "Período": "Anual",
                    "Orçado (R$)": -100.0,
                    "Realizado (R$)": -130.0,
                    "Desvio absoluto (R$)": -30.0,
                    "Desvio percentual (%)": 30.0,
                    "Classificação": "Desfavorável",
                },
            ]
        )

        alertas = identificar_alertas(dados, 10.0)
        alertas_limite_maior = identificar_alertas(dados, 40.0)

        self.assertEqual(len(alertas), 4)
        self.assertIn("Atenção", alertas["Gravidade"].tolist())
        self.assertIn("Alta", alertas["Gravidade"].tolist())
        self.assertTrue(alertas_limite_maior.empty)
        recomendacoes = gerar_recomendacoes(alertas)
        self.assertTrue(any("frete" in texto.lower() for texto in recomendacoes))
        self.assertTrue(any("reentregas" in texto.lower() for texto in recomendacoes))

    def test_alertas_nao_classificam_percentual_ausente(self):
        dados = pd.DataFrame(
            [
                {
                    "Indicador": "Despesa sem orçamento",
                    "Categoria": "despesa",
                    "Período": "Anual",
                    "Orçado (R$)": 0.0,
                    "Realizado (R$)": -10.0,
                    "Desvio absoluto (R$)": -10.0,
                    "Desvio percentual (%)": None,
                    "Classificação": "Desfavorável",
                }
            ]
        )

        self.assertTrue(identificar_alertas(dados, 10.0).empty)
        self.assertTrue(
            identificar_alertas(pd.DataFrame(), 10.0).empty
        )

    def test_metricas_usam_resumos_explicitos_e_despesas_detalhadas(self):
        dados = pd.DataFrame(
            [
                ["TOTAL RECEITA BRUTA", "receita", 100.0, 90.0, -10.0, -10.0],
                ["Fretes", "despesa", -20.0, -25.0, -5.0, 25.0],
                ["EBITDA", "resultado", 30.0, 20.0, -10.0, -33.33],
            ],
            columns=[
                "Indicador",
                "Categoria",
                "Orçado (R$)",
                "Realizado (R$)",
                "Desvio absoluto (R$)",
                "Desvio percentual (%)",
            ],
        )
        dados["Período"] = "Anual"
        dados["Classificação"] = ["Desfavorável"] * 3

        metricas = calcular_indicadores_dashboard(dados, "Anual")

        self.assertEqual(metricas["Receita"]["Realizado (R$)"], 90.0)
        self.assertEqual(
            metricas["Despesas (linhas incluídas no filtro)"]["Realizado (R$)"],
            -25.0,
        )
        self.assertEqual(metricas["EBITDA"]["Realizado (R$)"], 20.0)


if __name__ == "__main__":
    unittest.main()
