"""
Agregações analíticas do PMAV.

Funções puras que recebem o DataFrame simulado (já filtrado) e devolvem os
insumos das saídas do dashboard: KPIs, séries de gráficos, ranking de sistemas
prioritários e o texto do resumo executivo.
"""
from __future__ import annotations

import pandas as pd

from .formatting import format_brl
from .scenarios import SCENARIO_IDS, SCENARIO_NAMES, Scenario


# ─────────────────────────────────────── KPIs ────────────────────────────────────


def compute_kpis(df: pd.DataFrame) -> dict:
    """Cards-resumo do topo do dashboard."""
    if df.empty:
        return {
            "custo_total_previsto": 0.0, "custo_total_ajustado": 0.0,
            "n_sistemas": 0, "n_ativos": 0, "n_registros": 0,
            "alertas_imediatos": 0, "alertas_preditivos": 0,
            "sistema_mais_critico": "—", "sistema_maior_custo": "—",
        }

    kpis = {
        "custo_total_previsto": float(df["custo_previsto"].sum()),
        "custo_total_ajustado": float(df["custo_ajustado"].sum()),
        "n_sistemas": int(df["sistema"].nunique()),
        "n_ativos": int(df["id_ativo"].nunique()),
        "n_registros": int(len(df)),
        "alertas_imediatos": int((df["status_alerta"] == "Imediato").sum()),
        "alertas_preditivos": int((df["status_alerta"] == "Preditivo").sum()),
    }
    # Sistema mais crítico = menor criticidade projetada média (mais próximo de 0).
    crit = df.groupby("sistema")["criticidade_projetada"].mean()
    kpis["sistema_mais_critico"] = str(crit.idxmin())
    custo = df.groupby("sistema")["custo_previsto"].sum()
    kpis["sistema_maior_custo"] = str(custo.idxmax())
    return kpis


# ──────────────────────────────── Séries de gráficos ─────────────────────────────


def cost_by_scenario(df_all: pd.DataFrame) -> pd.DataFrame:
    """Custo total previsto por cenário (df_all = todos os cenários concatenados)."""
    cols = ["cenario", "nome", "custo_total_previsto"]
    if df_all.empty:
        return pd.DataFrame(columns=cols)
    g = df_all.groupby("cenario", as_index=False).agg(custo_total_previsto=("custo_previsto", "sum"))
    g["nome"] = g["cenario"].map(SCENARIO_NAMES)
    order = {sid: i for i, sid in enumerate(SCENARIO_IDS)}
    g["_o"] = g["cenario"].map(order)
    return g.sort_values("_o").drop(columns="_o").reset_index(drop=True)[cols]


def cost_by_system(df: pd.DataFrame) -> pd.DataFrame:
    """Custo previsto e ajustado por sistema (ordenado por custo previsto)."""
    cols = ["sistema", "custo_previsto", "custo_ajustado"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    g = df.groupby("sistema", as_index=False).agg(
        custo_previsto=("custo_previsto", "sum"),
        custo_ajustado=("custo_ajustado", "sum"),
    )
    return g.sort_values("custo_previsto", ascending=False).reset_index(drop=True)[cols]


def adjusted_vs_predicted(df: pd.DataFrame) -> pd.DataFrame:
    """Comparação custo ajustado vs. custo previsto por sistema."""
    return cost_by_system(df)


def alerts_by_system(df: pd.DataFrame) -> pd.DataFrame:
    """Distribuição de alertas (Imediato/Preditivo) por sistema."""
    cols = ["sistema", "Imediato", "Preditivo", "total"]
    sub = df[df["status_alerta"] != "Normal"]
    if sub.empty:
        return pd.DataFrame(columns=cols)
    g = sub.groupby(["sistema", "status_alerta"]).size().unstack(fill_value=0)
    for c in ("Imediato", "Preditivo"):
        if c not in g.columns:
            g[c] = 0
    g = g.reset_index()
    g["total"] = g["Imediato"] + g["Preditivo"]
    return g.sort_values("total", ascending=False).reset_index(drop=True)[cols]


def cost_and_criticality_by_system(df: pd.DataFrame) -> pd.DataFrame:
    """Custo previsto + criticidade média projetada por sistema (eixo duplo)."""
    cols = ["sistema", "custo_previsto", "criticidade_media"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    g = df.groupby("sistema", as_index=False).agg(
        custo_previsto=("custo_previsto", "sum"),
        criticidade_media=("criticidade_projetada", "mean"),
    )
    g["criticidade_media"] = g["criticidade_media"].round(2)
    return g.sort_values("custo_previsto", ascending=False).reset_index(drop=True)[cols]


# ───────────────────────────── Ranking de prioridade ─────────────────────────────


def system_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ranking de sistemas prioritários por um score composto:
      45% custo previsto + 35% severidade (criticidade) + 20% nº de alertas.
    """
    cols = ["sistema", "custo_previsto", "criticidade_media", "alertas", "score"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    g = df.groupby("sistema", as_index=False).agg(
        custo_previsto=("custo_previsto", "sum"),
        criticidade_media=("criticidade_projetada", "mean"),
        alertas=("status_alerta", lambda s: int((s != "Normal").sum())),
    )
    custo_max = g["custo_previsto"].max() or 1.0
    alertas_max = g["alertas"].max() or 1
    custo_norm = g["custo_previsto"] / custo_max
    severidade_norm = (5 - g["criticidade_media"]) / 5  # mais crítico ⇒ maior
    alertas_norm = g["alertas"] / alertas_max

    g["score"] = (0.45 * custo_norm + 0.35 * severidade_norm + 0.20 * alertas_norm).round(3)
    g["criticidade_media"] = g["criticidade_media"].round(2)
    return g.sort_values("score", ascending=False).reset_index(drop=True)[cols]


# ──────────────────────────────── Resumo executivo ───────────────────────────────


def executive_summary(df: pd.DataFrame, scenario: Scenario, kpis: dict) -> str:
    """Texto automático de apoio à decisão, coerente com os filtros e o cenário."""
    if df.empty:
        return "Nenhum registro corresponde aos filtros selecionados. Ajuste os filtros para gerar a análise."

    prioritarios = system_ranking(df).head(3)["sistema"].tolist()
    lista_prior = ", ".join(prioritarios) if prioritarios else "—"
    imediatos = kpis["alertas_imediatos"]
    preditivos = kpis["alertas_preditivos"]

    if imediatos > 0:
        recomendacao = (
            f"Há **{imediatos} alerta(s) imediato(s)** (criticidade 0): recomenda-se **intervenção corretiva "
            "prioritária** e inspeção especializada antes da continuidade operacional."
        )
    elif preditivos > 0:
        recomendacao = (
            f"Não há alertas imediatos, mas **{preditivos} alerta(s) preditivo(s)** sinalizam deterioração: "
            "recomenda-se **antecipar a manutenção preventiva** e revisar a periodicidade do PMAV."
        )
    else:
        recomendacao = "Sem alertas críticos no recorte atual: manter a execução do plano preventivo conforme o PMAV."

    return (
        f"No cenário **{scenario.nome}**, o custo total previsto pelo modelo é de "
        f"**{format_brl(kpis['custo_total_previsto'])}** (custo ajustado de referência: "
        f"{format_brl(kpis['custo_total_ajustado'])}), distribuído em **{kpis['n_sistemas']} sistema(s)** "
        f"de **{kpis['n_ativos']} ativo(s)**. A maior concentração de criticidade está no sistema "
        f"**{kpis['sistema_mais_critico']}**, e o maior custo previsto no sistema "
        f"**{kpis['sistema_maior_custo']}**. Sistemas prioritários: **{lista_prior}**. {recomendacao}"
    )
