import base64
import unittest
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from streamlit.testing.v1 import AppTest

from src.analise_financeira import calcular_indicadores_dashboard
from src.relatorio_financeiro import (
    AVISO_RESPONSABILIDADE,
    gerar_relatorio_html,
)


class VerificadorHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def _criar_comparativos():
    return pd.DataFrame(
        [
            {
                "Indicador": "TOTAL RECEITA BRUTA",
                "Categoria": "receita",
                "Período": "Anual",
                "Orçado (R$)": 1000.0,
                "Realizado (R$)": 900.0,
                "Desvio absoluto (R$)": -100.0,
                "Desvio percentual (%)": -10.0,
                "Classificação": "Desfavorável",
            },
            {
                "Indicador": "EBITDA",
                "Categoria": "resultado",
                "Período": "Anual",
                "Orçado (R$)": 200.0,
                "Realizado (R$)": 150.0,
                "Desvio absoluto (R$)": -50.0,
                "Desvio percentual (%)": -25.0,
                "Classificação": "Desfavorável",
            },
            {
                "Indicador": "Fretes e Logística",
                "Categoria": "despesa",
                "Período": "Anual",
                "Orçado (R$)": -100.0,
                "Realizado (R$)": -120.0,
                "Desvio absoluto (R$)": -20.0,
                "Desvio percentual (%)": 20.0,
                "Classificação": "Desfavorável",
            },
        ]
    )


class RelatorioFinanceiroTests(unittest.TestCase):
    def setUp(self):
        self.dados = _criar_comparativos()
        self.data_geracao = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

    def test_relatorio_reflete_metricas_do_dashboard_e_classificacao(self):
        metricas_dashboard = calcular_indicadores_dashboard(
            self.dados, "Anual"
        )
        html = gerar_relatorio_html(
            self.dados,
            "planilha_original.xlsx",
            10.0,
            self.data_geracao,
        )

        self.assertIn("R$ 900,00", html)
        self.assertIn("R$ 1.000,00", html)
        self.assertIn("R$ 150,00", html)
        self.assertIn("R$ 120,00", html)
        self.assertIn("Desfavorável", html)
        self.assertEqual(
            metricas_dashboard["Receita"]["Realizado (R$)"], 900.0
        )
        self.assertIn("05/11/2026", html)
        self.assertIn("planilha_original.xlsx", html)

    def test_relatorio_respeita_o_conjunto_filtrado(self):
        filtrados = self.dados[self.dados["Indicador"].eq("EBITDA")]
        html = gerar_relatorio_html(
            filtrados, "origem.xlsx", 10.0, self.data_geracao
        )

        self.assertIn(">EBITDA<", html)
        self.assertNotIn("TOTAL RECEITA BRUTA", html)
        self.assertNotIn("Fretes e Logística", html)

    def test_recomendacoes_dependem_dos_alertas(self):
        html_com_alertas = gerar_relatorio_html(
            self.dados, "origem.xlsx", 10.0, self.data_geracao
        )
        html_sem_alertas = gerar_relatorio_html(
            self.dados, "origem.xlsx", 100.0, self.data_geracao
        )

        self.assertIn("Revisar contratos de frete", html_com_alertas)
        self.assertIn("EBITDA abaixo do orçamento", html_com_alertas)
        self.assertNotIn("Revisar contratos de frete", html_sem_alertas)
        self.assertIn(
            "Nenhuma recomendação específica foi justificada",
            html_sem_alertas,
        )

    def test_html_escapa_conteudo_da_planilha_e_nome_do_arquivo(self):
        dados = self.dados.iloc[[0]].copy()
        dados.loc[dados.index[0], "Indicador"] = '<script>alert("x")</script>'
        html = gerar_relatorio_html(
            dados,
            'arquivo"><img src=x onerror=alert(1)>.xlsx',
            10.0,
            self.data_geracao,
        )

        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_html_e_legivel_e_valores_ausentes_sao_marcados(self):
        ausente = self.dados.iloc[[0]].copy()
        ausente.loc[ausente.index[0], "Desvio percentual (%)"] = None
        parcial = self.dados.iloc[[1]].copy()
        parcial.loc[parcial.index[0], "Realizado (R$)"] = None
        parcial.loc[parcial.index[0], "Desvio absoluto (R$)"] = None
        parcial.loc[parcial.index[0], "Desvio percentual (%)"] = None
        dados = pd.concat([ausente, parcial], ignore_index=True)
        html = gerar_relatorio_html(
            dados, "origem.xlsx", 10.0, self.data_geracao
        )
        parser = VerificadorHTML()
        parser.feed(html)
        parser.close()

        self.assertIn("html", parser.tags)
        self.assertIn("table", parser.tags)
        self.assertIn("—", html)
        self.assertIn("EBITDA", html)
        self.assertIn(AVISO_RESPONSABILIDADE, html)

    def test_nao_gera_relatorio_vazio_ou_sem_pares_comparaveis(self):
        with self.assertRaises(ValueError):
            gerar_relatorio_html(
                self.dados.iloc[0:0],
                "origem.xlsx",
                gerado_em=self.data_geracao,
            )

        dados_sem_pares = self.dados.iloc[[0]].copy()
        dados_sem_pares["Realizado (R$)"] = None
        with self.assertRaises(ValueError):
            gerar_relatorio_html(
                dados_sem_pares,
                "origem.xlsx",
                gerado_em=self.data_geracao,
            )

    def test_dashboard_expoe_download_html_com_preview(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Linha de Produto",
                "Orçado Anual (R$)",
                "Realizado Anual (R$)",
            ]
        )
        sheet.append(["Produto de teste", 100.0, 100.0])
        conteudo = BytesIO()
        workbook.save(conteudo)

        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()
        app.file_uploader[0].set_value(
            (
                "dados.xlsx",
                conteudo.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ).run()

        self.assertFalse(app.exception)
        botao = app.get("download_button")
        self.assertEqual(len(botao), 1)
        self.assertEqual(botao[0].label, "Baixar Relatório HTML")
        self.assertTrue(botao[0].proto.url.endswith(".html"))
        iframe = app.get("iframe")
        self.assertEqual(len(iframe), 1)
        relatorio_preview = base64.b64decode(
            iframe[0].proto.src.partition(",")[2]
        ).decode("utf-8")
        self.assertTrue(relatorio_preview.startswith("<!DOCTYPE html>"))

        app.sidebar.multiselect[0].set_value([]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("download_button")), 0)

    def test_dashboard_inicia_sem_upload_e_pede_uma_planilha(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.file_uploader), 1)
        self.assertTrue(
            any("Envie uma planilha" in mensagem.value for mensagem in app.info)
        )

    def test_upload_excel_invalido_exibe_erro_sem_encerrar_aplicacao(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()
        app.file_uploader[0].set_value(
            (
                "arquivo_invalido.xlsx",
                b"conteudo que nao e uma planilha",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ).run()

        self.assertEqual(len(app.exception), 1)
        self.assertIn("File is not a zip file", app.exception[0].message)
        self.assertTrue(any("Não foi possível ler" in item.value for item in app.error))

    def test_upload_excel_vazio_exibe_aviso_sem_erro(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()
        app.file_uploader[0].set_value(
            (
                "arquivo_vazio.xlsx",
                b"",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ).run()

        self.assertFalse(app.exception)
        self.assertTrue(
            any("arquivo enviado está vazio" in item.value for item in app.warning)
        )
        self.assertEqual(len(app.get("download_button")), 0)


if __name__ == "__main__":
    unittest.main()
