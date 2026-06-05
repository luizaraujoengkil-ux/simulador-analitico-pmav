"""
Formatação pt-BR (puro, sem dependências externas além da stdlib).

Implementação manual de separadores para não depender de `locale` instalado no
servidor (o Streamlit Community Cloud roda em Linux, onde pt_BR pode não existir).
"""
from __future__ import annotations


def _thousands(value: float, decimals: int = 0) -> str:
    s = f"{value:,.{decimals}f}"  # ex.: 1,234,567.89  (estilo en-US)
    # Troca para pt-BR (vírgula <-> ponto) usando um placeholder temporário.
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_brl(value: float) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"R$ {_thousands(v, 0)}"


def format_compact_brl(value: float) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    a = abs(v)
    if a >= 1_000_000:
        return f"R$ {_thousands(v / 1_000_000, 1)} mi"
    if a >= 1_000:
        return f"R$ {_thousands(v / 1_000, 0)} mil"
    return format_brl(v)


def format_number(value: float, decimals: int = 0) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return _thousands(v, decimals)


def format_percent(value: float, decimals: int = 1) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"{_thousands(v * 100, decimals)}%"
