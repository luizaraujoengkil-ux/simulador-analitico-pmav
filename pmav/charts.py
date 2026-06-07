"""
Gráficos analíticos (Plotly) com o tema VistoPred.

Cada função recebe um DataFrame já agregado (ver pmav.aggregations) e devolve uma
figura Plotly estilizada. A renderização fica a cargo da camada de app
(st.plotly_chart).
"""
from __future__ import annotations

import plotly.graph_objects as go

from .formatting import format_number
from .theme import CHART_COLORWAY, COLORS


def _style(fig: go.Figure, height: int = 320, legend: bool = False) -> go.Figure:
    """Aplica o tema visual comum a todas as figuras."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=COLORS["brand_900"], size=12),
        colorway=CHART_COLORWAY,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=COLORS["cinza_200"]),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=COLORS["cinza_200"])
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["cinza_200"], zeroline=False)
    return fig


def chart_cost_by_scenario(df_scn, selected_id: str | None = None) -> go.Figure:
    """Barras: custo total previsto por cenário (destaque no cenário selecionado)."""
    colors = [COLORS["ciano_600"] if cid == selected_id else COLORS["brand_700"] for cid in df_scn["cenario"]]
    fig = go.Figure(
        go.Bar(
            x=df_scn["nome"], y=df_scn["custo_total_previsto"],
            marker_color=colors,
            hovertemplate="<b>%{x}</b><br>Custo previsto: R$ %{y:,.0f}<extra></extra>",
        )
    )
    return _style(fig)


def chart_cost_by_system(df_sys) -> go.Figure:
    """Barras horizontais: custo previsto por sistema."""
    d = df_sys.sort_values("custo_previsto")
    fig = go.Figure(
        go.Bar(
            x=d["custo_previsto"], y=d["sistema"], orientation="h",
            marker_color=COLORS["brand_700"],
            hovertemplate="<b>%{y}</b><br>Custo previsto: R$ %{x:,.0f}<extra></extra>",
        )
    )
    return _style(fig, height=max(320, 24 * len(df_sys)))


def chart_adjusted_vs_predicted(df_sys) -> go.Figure:
    """Barras agrupadas: custo ajustado vs. custo previsto por sistema."""
    fig = go.Figure()
    fig.add_bar(name="Ajustado", x=df_sys["sistema"], y=df_sys["custo_ajustado"], marker_color=COLORS["brand_500"],
                hovertemplate="<b>%{x}</b><br>Ajustado: R$ %{y:,.0f}<extra></extra>")
    fig.add_bar(name="Previsto", x=df_sys["sistema"], y=df_sys["custo_previsto"], marker_color=COLORS["ciano"],
                hovertemplate="<b>%{x}</b><br>Previsto: R$ %{y:,.0f}<extra></extra>")
    fig.update_layout(barmode="group")
    fig = _style(fig, legend=True)
    fig.update_xaxes(tickangle=-35)
    return fig


def chart_alerts_by_system(df_alerts) -> go.Figure:
    """Barras empilhadas: alertas (imediato/preditivo) por sistema."""
    fig = go.Figure()
    if not df_alerts.empty:
        fig.add_bar(name="Imediato", x=df_alerts["sistema"], y=df_alerts["Imediato"], marker_color="#dc2626",
                    hovertemplate="<b>%{x}</b><br>Imediatos: %{y}<extra></extra>")
        fig.add_bar(name="Preditivo", x=df_alerts["sistema"], y=df_alerts["Preditivo"], marker_color="#d97706",
                    hovertemplate="<b>%{x}</b><br>Preditivos: %{y}<extra></extra>")
    fig.update_layout(barmode="stack")
    fig = _style(fig, legend=True)
    fig.update_xaxes(tickangle=-35)
    return fig


def chart_coefficients(model) -> go.Figure:
    """Barras horizontais dos coeficientes β₁–β₄ (azul = aumenta custo, vermelho = reduz)."""
    keys = ["periodicidade_meses", "criticidade", "frequencia_prevista", "horizonte_ano"]
    labels = ["β₁ · Periodicidade", "β₂ · Criticidade", "β₃ · Frequência", "β₄ · Horizonte"]
    vals = [float(model.coefficients[k]) for k in keys]
    colors = ["#dc2626" if v < 0 else COLORS["ciano_600"] for v in vals]
    fig = go.Figure(
        go.Bar(
            x=vals, y=labels, orientation="h", marker_color=colors,
            text=[format_number(v, 0) for v in vals], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>coeficiente: %{x:,.2f}<extra></extra>",
        )
    )
    fig = _style(fig, height=260)
    fig.add_vline(x=0, line_color=COLORS["slate_500"], line_width=1)
    fig.update_yaxes(autorange="reversed")  # β₁ no topo
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["cinza_200"])
    return fig


def chart_cost_and_criticality(df_cc) -> go.Figure:
    """Eixo duplo: custo previsto (barras) + criticidade média projetada (linha)."""
    fig = go.Figure()
    fig.add_bar(name="Custo previsto", x=df_cc["sistema"], y=df_cc["custo_previsto"], marker_color=COLORS["brand_700"],
                hovertemplate="<b>%{x}</b><br>Custo previsto: R$ %{y:,.0f}<extra></extra>")
    fig.add_trace(
        go.Scatter(
            name="Criticidade média projetada", x=df_cc["sistema"], y=df_cc["criticidade_media"],
            mode="lines+markers", yaxis="y2",
            line=dict(color=COLORS["ciano"], width=3), marker=dict(size=8, color=COLORS["ciano"]),
            hovertemplate="<b>%{x}</b><br>Criticidade média: %{y:.2f}<extra></extra>",
        )
    )
    fig = _style(fig, legend=True)
    fig.update_layout(
        yaxis=dict(title="Custo previsto (R$)"),
        yaxis2=dict(title="Criticidade (0–5)", overlaying="y", side="right", range=[0, 5],
                    showgrid=False, autorange="reversed"),  # 0 (pior) no topo
    )
    fig.update_xaxes(tickangle=-35)
    return fig
