"""
Simulação de cenários do PMAV.

Fluxo orquestrado por `run_simulation`:
    1. aplica os fatores do cenário      → custo_ajustado, criticidade_projetada
    2. ajusta a regressão (OLS)           → coeficientes β, R², RMSE
    3. prevê o custo de cada registro     → custo_previsto, resíduo
    4. classifica os alertas              → status_alerta + motivo/impacto/ação

Módulo PURO (sem Streamlit/Plotly).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .regression import ModelFit, fit_or_mock, predict_cost
from .scenarios import Scenario, get_scenario

# Constantes de calibração do modelo de deterioração.
K_CRIT = 0.08              # sensibilidade da criticidade projetada à degradação
K_COST = 0.02             # sensibilidade do custo à degradação acumulada
PREDICTIVE_THRESHOLD = 1.0  # criticidade projetada ≤ limiar ⇒ ALERTA PREDITIVO


@dataclass
class SimulationResult:
    cenario: str
    df: pd.DataFrame
    model: ModelFit


def apply_scenario(df: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """Aplica os fatores do cenário, criando custo_ajustado e criticidade_projetada."""
    f = scenario.factors
    out = df.copy()
    anos = out["horizonte_ano"] - 1  # ano 1 = sem crescimento acumulado

    custo_anual_base = out["custo_base"] * out["frequencia_prevista"]
    crescimento_horizonte = 1 + f.custo_horizonte * anos
    degradacao_custo = 1 + out["fator_degradacao"] * f.degradacao * anos * K_COST
    out["custo_ajustado"] = (custo_anual_base * f.custo * crescimento_horizonte * degradacao_custo).round(2)

    # Criticidade projetada: parte da base e deteriora rumo a 0.
    degrade = out["fator_degradacao"] * f.degradacao * out["horizonte_ano"] * K_CRIT
    out["criticidade_projetada"] = (out["criticidade"] - degrade + f.criticidade_shift).clip(0, 5).round(2)
    return out


def classify_alerts(df: pd.DataFrame) -> np.ndarray:
    """Vetoriza a classificação de alertas (Imediato / Preditivo / Normal)."""
    cond_imediato = df["criticidade"] == 0
    cond_preditivo = df["criticidade_projetada"] <= PREDICTIVE_THRESHOLD
    return np.select([cond_imediato, cond_preditivo], ["Imediato", "Preditivo"], default="Normal")


def _alert_details(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Gera motivo, impacto e ação sugerida para os alertas (apoio à decisão)."""
    motivos, impactos, acoes = [], [], []
    for row in df.itertuples(index=False):
        tipo = row.status_alerta
        if tipo == "Imediato":
            motivos.append(f"Criticidade 0 (risco iminente) em {row.subsistema} — {row.sistema}.")
            impactos.append(f"Impacto operacional {row.impacto_operacional.lower()}; risco de falha e de segurança.")
            acoes.append("Intervenção corretiva imediata e inspeção especializada antes da próxima operação.")
        elif tipo == "Preditivo":
            motivos.append(f"Tendência de deterioração: criticidade projetada de {row.criticidade_projetada:.1f} no ano {row.horizonte_ano}.")
            impactos.append(f"Degradação acelerada (fator {row.fator_degradacao:.2f}, ambiente {row.ambiente_exposicao.lower()}).")
            acoes.append("Antecipar manutenção preventiva e reavaliar a periodicidade do PMAV para o subsistema.")
        else:
            motivos.append("")
            impactos.append("")
            acoes.append("")
    return motivos, impactos, acoes


def run_simulation(df_base: pd.DataFrame, scenario: Scenario, source: str = "ols") -> SimulationResult:
    """Executa a simulação completa para um cenário."""
    df = apply_scenario(df_base, scenario)

    model = fit_or_mock(df, source)
    df["custo_previsto"] = predict_cost(model.coefficients, df).round(2)
    df["residuo"] = (df["custo_ajustado"] - df["custo_previsto"]).round(2)
    df["cenario"] = scenario.id

    df["status_alerta"] = classify_alerts(df)
    motivos, impactos, acoes = _alert_details(df)
    df["motivo_alerta"] = motivos
    df["impacto_alerta"] = impactos
    df["acao_sugerida"] = acoes

    return SimulationResult(cenario=scenario.id, df=df, model=model)


def run_all_scenarios(df_base: pd.DataFrame, scenarios: list[Scenario], source: str = "ols") -> list[SimulationResult]:
    """Executa a simulação para todos os cenários (comparação entre cenários)."""
    return [run_simulation(df_base, s, source) for s in scenarios]


def simulate_concat(df_base: pd.DataFrame, scenarios: list[Scenario], source: str = "ols"):
    """
    Roda todos os cenários e devolve:
      - um único DataFrame com TODOS os registros enriquecidos (coluna `cenario`)
      - um dicionário {id_cenario: ModelFit}
    Conveniente para a camada de UI (1 chamada cacheável).
    """
    frames: list[pd.DataFrame] = []
    models: dict[str, ModelFit] = {}
    for s in scenarios:
        res = run_simulation(df_base, s, source)
        frames.append(res.df)
        models[s.id] = res.model
    full = pd.concat(frames, ignore_index=True)
    return full, models


# Reexport conveniente.
__all__ = [
    "SimulationResult", "apply_scenario", "classify_alerts",
    "run_simulation", "run_all_scenarios", "simulate_concat", "get_scenario",
]
