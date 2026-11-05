import unittest

import pandas as pd

from src.visualizacoes import (
    grafico_evolucao,
    grafico_maiores_desvios,
    grafico_orcado_realizado,
)


class VisualizacoesTests(unittest.TestCase):
    def setUp(self):
        self.dados = pd.DataFrame(
            [
                ["Receita", "receita", "T1", 100.0, 90.0, -10.0, -10.0, "Desfavorável"],
                ["Receita", "receita", "T2", 120.0, 130.0, 10.0, 8.33, "Favorável"],
                ["Fretes", "despesa", "T1", -20.0, -25.0, -5.0, 25.0, "Desfavorável"],
                ["Receita", "receita", "Anual", 220.0, 220.0, 0.0, 0.0, "Neutro"],
            ],
            columns=[
                "Indicador",
                "Categoria",
                "Período",
                "Orçado (R$)",
                "Realizado (R$)",
                "Desvio absoluto (R$)",
                "Desvio percentual (%)",
                "Classificação",
            ],
        )

    def test_barras_comparam_orcado_e_realizado_sem_agregar(self):
        figura = grafico_orcado_realizado(self.dados)

        self.assertIsNotNone(figura)
        self.assertEqual(len(figura.data), 2)
        self.assertEqual(len(figura.data[0].x), len(self.dados))
        self.assertIn("T1", figura.data[0].x[0])
        self.assertEqual(figura.data[0].y[0], 100.0)
        self.assertEqual(figura.data[1].y[0], 90.0)

    def test_evolucao_temporal_omite_total_anual(self):
        figura = grafico_evolucao(self.dados)

        self.assertIsNotNone(figura)
        self.assertEqual(list(figura.data[0].x), ["T1", "T2"])

    def test_maiores_desvios_excluem_favoraveis(self):
        figura = grafico_maiores_desvios(self.dados)

        self.assertIsNotNone(figura)
        self.assertEqual(len(figura.data[0].x), 2)
        self.assertEqual(max(figura.data[0].x), 10.0)

    def test_graficos_nao_sao_criados_sem_dados(self):
        vazios = self.dados.iloc[0:0]

        self.assertIsNone(grafico_orcado_realizado(vazios))
        self.assertIsNone(grafico_evolucao(vazios))
        self.assertIsNone(grafico_maiores_desvios(vazios))


if __name__ == "__main__":
    unittest.main()
