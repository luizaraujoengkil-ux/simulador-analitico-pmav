"""
Regressão Linear Múltipla (OLS) — núcleo estatístico do simulador.

Modelo (conforme a formulação do artigo):
    Custo_i = β0 + β1·Periodicidade_i + β2·Criticidade_i + β3·Frequência_i + β4·Horizonte_i + ε_i

O ajuste é feito de verdade por Mínimos Quadrados Ordinários usando `statsmodels`
(entrega coeficientes, R², RMSE e p-valores). Caso o statsmodels não esteja
disponível, há fallback transparente em `numpy.linalg.lstsq` (mesma matemática
OLS, sem inferência), garantindo que o app nunca quebre por dependência.

Módulo PURO (sem Streamlit/Plotly): testável isoladamente e portável a backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Variáveis explicativas do modelo e variável resposta.
FEATURES = ["periodicidade_meses", "criticidade", "frequencia_prevista", "horizonte_ano"]
TARGET = "custo_ajustado"

# Coeficientes mockados configuráveis — usados no modo "mock" ou como fallback
# quando há poucos dados. Valores ilustrativos na ordem de grandeza de custos (R$).
DEFAULT_COEFFICIENTS: dict[str, float] = {
    "intercept": 6000.0,            # β0
    "periodicidade_meses": -110.0,  # β1  intervalos maiores ⇒ menor custo
    "criticidade": -1400.0,         # β2  índice maior (menos crítico) ⇒ menor custo
    "frequencia_prevista": 5200.0,  # β3  mais intervenções ⇒ maior custo
    "horizonte_ano": 850.0,         # β4  anos posteriores ⇒ maior custo
}


@dataclass
class ModelFit:
    """Resultado do ajuste do modelo."""
    coefficients: dict[str, float]
    r2: float
    rmse: float
    n: int
    source: str  # 'ols' | 'mock'
    engine: str  # 'statsmodels' | 'numpy' | 'mock'
    pvalues: Optional[dict[str, float]] = None


def predict_cost(coefficients: dict[str, float], df: pd.DataFrame) -> pd.Series:
    """Previsão de custo (vetorizada). Custo não pode ser negativo ⇒ clip em 0."""
    yhat = (
        coefficients["intercept"]
        + coefficients["periodicidade_meses"] * df["periodicidade_meses"]
        + coefficients["criticidade"] * df["criticidade"]
        + coefficients["frequencia_prevista"] * df["frequencia_prevista"]
        + coefficients["horizonte_ano"] * df["horizonte_ano"]
    )
    return yhat.clip(lower=0)


def _metrics(coefficients: dict[str, float], df: pd.DataFrame) -> tuple[float, float]:
    """R² e RMSE de um conjunto de coeficientes sobre o DataFrame."""
    y = df[TARGET].astype(float)
    pred = predict_cost(coefficients, df)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / len(df))) if len(df) else 0.0
    return r2, rmse


def fit_regression(df: pd.DataFrame) -> ModelFit:
    """Ajusta o modelo por OLS (statsmodels, com fallback em numpy)."""
    n = len(df)
    if n < len(FEATURES) + 2:
        r2, rmse = _metrics(DEFAULT_COEFFICIENTS, df) if n else (0.0, 0.0)
        return ModelFit(DEFAULT_COEFFICIENTS, r2, rmse, n, "mock", "mock")

    X = df[FEATURES].astype(float)
    y = df[TARGET].astype(float)

    # Caminho principal: statsmodels (com diagnóstico estatístico).
    try:
        import statsmodels.api as sm

        Xc = sm.add_constant(X, has_constant="add")
        res = sm.OLS(y, Xc).fit()

        coef = {"intercept": float(res.params["const"])}
        coef.update({f: float(res.params[f]) for f in FEATURES})
        pvalues = {"intercept": float(res.pvalues["const"])}
        pvalues.update({f: float(res.pvalues[f]) for f in FEATURES})

        pred = res.predict(Xc).clip(lower=0)
        rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
        return ModelFit(coef, float(res.rsquared), rmse, n, "ols", "statsmodels", pvalues)

    except Exception:
        # Fallback: OLS por mínimos quadrados em numpy (sem p-valores).
        A = np.column_stack([np.ones(n), X.values])
        beta, *_ = np.linalg.lstsq(A, y.values, rcond=None)
        coef = {"intercept": float(beta[0])}
        coef.update({f: float(beta[i + 1]) for i, f in enumerate(FEATURES)})
        r2, rmse = _metrics(coef, df)
        return ModelFit(coef, r2, rmse, n, "ols", "numpy")


def mock_fit(df: pd.DataFrame, coefficients: dict[str, float] | None = None) -> ModelFit:
    """Ajuste com coeficientes mockados (padrão) ou definidos pelo especialista."""
    coef = {**DEFAULT_COEFFICIENTS, **(coefficients or {})}
    n = len(df)
    r2, rmse = _metrics(coef, df) if n else (0.0, 0.0)
    return ModelFit(coef, r2, rmse, n, "mock", "mock")


def fit_or_mock(df: pd.DataFrame, source: str = "ols",
                coefficients: dict[str, float] | None = None) -> ModelFit:
    """Despacha entre o ajuste OLS e os coeficientes mockados/especialista."""
    return mock_fit(df, coefficients) if source == "mock" else fit_regression(df)
