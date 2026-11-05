"""Formatadores compartilhados para valores financeiros apresentados na interface."""

import pandas as pd


def formatar_moeda(valor: object) -> str:
    """Formata um valor numérico em reais, preservando sinal e ausências."""
    if valor is None or pd.isna(valor):
        return "—"
    numero = float(valor)
    formatado = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace(
        "X", "."
    )
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {formatado}"


def formatar_percentual(valor: object) -> str:
    """Formata um percentual ou indica que ele não está disponível."""
    if valor is None or pd.isna(valor):
        return "—"
    return f"{float(valor):.2f}%"
