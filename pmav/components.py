"""
Componentes visuais do dashboard (Streamlit + HTML/CSS da identidade VistoPred).

Cada função renderiza um bloco reutilizável: header, cards-resumo, badges,
painel de alertas e resumo executivo.
"""
from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

from .catalog import CRITICALITY_SCALE
from .formatting import format_brl, format_compact_brl, format_number, format_percent
from .regression import ModelFit
from .scenarios import Scenario
from .theme import COLORS, criticality_color


def render_header(scenario: Scenario) -> None:
    st.markdown(
        f"""
        <div class="vp-header">
            <div class="vp-logo">V</div>
            <div>
                <p class="eyebrow">VistoPred</p>
                <h1>Simulador Analítico PMAV</h1>
                <p class="sub">Previsão de custos, cenários e apoio à decisão em manutenção preventiva de ativos</p>
            </div>
            <div class="scn">
                <div class="lbl">Cenário ativo</div>
                <div class="val">{html.escape(scenario.nome)}</div>
                <div class="cred">Desenvolvido por <b>Luiz Araujo</b> ·
                    <a href="mailto:luiz.junior@ime.eb.br">luiz.junior@ime.eb.br</a><br>
                    IME — Instituto Militar de Engenharia</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kpi_card(label: str, value: str, hint: str = "", tone: str = "default", small: bool = False) -> str:
    val_cls = "val sm" if small else "val"
    if tone in ("danger", "warn"):
        val_cls += f" {tone}"
    hint_html = f'<div class="hint">{html.escape(hint)}</div>' if hint else ""
    return (
        f'<div class="vp-card vp-kpi"><div class="accent-bar"></div>'
        f'<div class="lbl">{html.escape(label)}</div>'
        f'<div class="{val_cls}">{html.escape(value)}</div>{hint_html}</div>'
    )


def render_kpis(kpis: dict) -> None:
    """Renderiza os 7 cards-resumo em duas linhas."""
    row1 = st.columns(4)
    cards1 = [
        _kpi_card("Custo total previsto", format_brl(kpis["custo_total_previsto"]), "Estimado pelo modelo (OLS)"),
        _kpi_card("Custo total ajustado", format_brl(kpis["custo_total_ajustado"]), "Referência do cenário"),
        _kpi_card("Sistemas avaliados", format_number(kpis["n_sistemas"]), f'{format_number(kpis["n_ativos"])} ativo(s) · {format_number(kpis["n_registros"])} registros'),
        _kpi_card("Alertas imediatos", format_number(kpis["alertas_imediatos"]), "Criticidade 0 (risco iminente)", tone="danger"),
    ]
    for col, card in zip(row1, cards1):
        col.markdown(card, unsafe_allow_html=True)

    row2 = st.columns(3)
    cards2 = [
        _kpi_card("Alertas preditivos", format_number(kpis["alertas_preditivos"]), "Tendência de deterioração", tone="warn"),
        _kpi_card("Sistema mais crítico", str(kpis["sistema_mais_critico"]), "Menor criticidade projetada média", small=True),
        _kpi_card("Maior custo previsto", str(kpis["sistema_maior_custo"]), "Sistema com maior custo no recorte", small=True),
    ]
    for col, card in zip(row2, cards2):
        col.markdown(card, unsafe_allow_html=True)


def render_model_panel(model: ModelFit) -> None:
    """Card transparente do modelo estatístico (coeficientes, R², RMSE)."""
    c = model.coefficients
    engine = {"statsmodels": "statsmodels OLS", "numpy": "numpy OLS", "mock": "coeficientes mockados"}.get(model.engine, model.engine)
    if model.source == "mock":
        meaning = "⚪ Modo Mockado — pesos fixos (referência); não se ajustam aos dados."
    else:
        meaning = "🔵 Modo Ajustado (OLS) — pesos estimados dos dados; recalculam quando a base muda."
    betas = [
        ("β₀ (intercepto)", c["intercept"]),
        ("β₁ (periodicidade)", c["periodicidade_meses"]),
        ("β₂ (criticidade)", c["criticidade"]),
        ("β₃ (frequência)", c["frequencia_prevista"]),
        ("β₄ (horizonte)", c["horizonte_ano"]),
    ]
    chips = "".join(
        f'<div style="background:{COLORS["cinza_100"]};border:1px solid {COLORS["cinza_200"]};border-radius:12px;'
        f'padding:8px 12px;min-width:130px;flex:1"><div style="font-size:11px;color:{COLORS["slate_500"]}">{html.escape(k)}</div>'
        f'<div style="font-family:monospace;font-weight:700;color:{COLORS["brand_800"]}">{format_number(v, 2)}</div></div>'
        for k, v in betas
    )
    st.markdown(
        f"""
        <div class="vp-card">
            <div class="vp-section">Modelo estatístico — regressão linear múltipla</div>
            <div style="font-size:13px;color:{COLORS['slate_500']};margin-bottom:6px">
                Custo = β₀ + β₁·Periodicidade + β₂·Criticidade + β₃·Frequência + β₄·Horizonte &nbsp;·&nbsp; motor: {html.escape(engine)}
            </div>
            <div style="font-size:12.5px;color:{COLORS['brand_700']};font-weight:600;margin-bottom:10px">{html.escape(meaning)}</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">{chips}</div>
            <div style="font-size:12px;color:{COLORS['slate_500']};margin-top:12px">
                R² = <b>{format_percent(model.r2)}</b> &nbsp;·&nbsp; RMSE = <b>{format_brl(model.rmse)}</b>
                &nbsp;·&nbsp; n = {format_number(model.n)} observações
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def criticality_badge(level: int) -> str:
    info = CRITICALITY_SCALE.get(int(level))
    label = info.label if info else str(level)
    color = criticality_color(level)
    return f'<span class="vp-badge" style="background:{color}">{level} · {html.escape(label)}</span>'


def alert_badge(tipo: str) -> str:
    color = {"Imediato": "#dc2626", "Preditivo": "#d97706"}.get(tipo, "#64748b")
    return f'<span class="vp-badge" style="background:{color}">{html.escape(tipo)}</span>'


def render_alert_panel(df: pd.DataFrame, limit: int = 12) -> None:
    """Painel de alertas com destaque visual (imediatos primeiro)."""
    alerts = df[df["status_alerta"] != "Normal"].copy()
    if alerts.empty:
        st.success("Nenhum alerta no recorte atual. Sistemas dentro dos parâmetros do PMAV.")
        return

    # Ordena: Imediato antes de Preditivo; depois por criticidade projetada (pior primeiro).
    order = {"Imediato": 0, "Preditivo": 1}
    alerts["_o"] = alerts["status_alerta"].map(order)
    alerts = alerts.sort_values(["_o", "criticidade_projetada"]).head(limit)

    for row in alerts.itertuples(index=False):
        cls = "imediato" if row.status_alerta == "Imediato" else "preditivo"
        st.markdown(
            f"""
            <div class="vp-alert {cls}">
                <div class="top">{alert_badge(row.status_alerta)}
                    <span class="sys">{html.escape(row.sistema)} · {html.escape(row.subsistema)}</span>
                    <span class="vp-pill">{html.escape(row.nome_ativo)} · ano {row.horizonte_ano}</span>
                </div>
                <div class="row"><b>Motivo:</b> {html.escape(str(row.motivo_alerta))}</div>
                <div class="row"><b>Impacto:</b> {html.escape(str(row.impacto_alerta))}</div>
                <div class="row"><b>Ação sugerida:</b> {html.escape(str(row.acao_sugerida))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_executive_summary(text: str) -> None:
    # Converte **negrito** (markdown) para <b> — markdown não é processado dentro de HTML.
    text_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    st.markdown(f'<div class="vp-exec">{text_html}</div>', unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f'<div class="vp-section">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_criticality_help() -> None:
    """Legenda: escala de criticidade (0–5), regras de alerta e efeito do cenário."""
    badges = "".join(
        f'<span class="vp-badge" style="background:{info.color};margin:2px 6px 2px 0">'
        f'{lvl} · {html.escape(info.label)}</span>'
        for lvl, info in CRITICALITY_SCALE.items()
    )
    st.markdown(f'<div style="margin:2px 0 10px">{badges}</div>', unsafe_allow_html=True)
    st.markdown(
        "**Escala de criticidade** — vai de **0 (risco iminente)** a **5 (condição mais favorável)**. "
        "Quanto **menor o número, pior** a condição do sistema/subsistema.\n\n"
        "**Como os alertas são decididos** (para cada tarefa, em cada ano do horizonte):\n"
        "- 🔴 **Imediato** — criticidade **= 0** hoje → exige ação **agora**.\n"
        "- 🟠 **Preditivo** — criticidade > 0, mas a **projeção** indica queda a **≤ 1,0** ao longo dos anos "
        "(deterioração) → antecipar a manutenção.\n"
        "- ⚪ **Normal** — a projeção permanece **acima de 1,0**.\n\n"
        "**Como isso muda na simulação** — a *criticidade projetada* cai ao longo dos 10 anos conforme o "
        "**fator de degradação** do ativo e o **cenário** escolhido:\n"
        "- Cenários severos (**Ambiente agressivo**, **Envelhecimento acelerado**, **Restrição orçamentária**) "
        "**aceleram a deterioração** → mais alertas preditivos e custos maiores.\n"
        "- **Otimista** reduz a deterioração; **Base** é a referência neutra.\n\n"
        "Troque o **cenário** ou aplique **filtros** na barra lateral e todos os números acima recalculam na hora."
    )


def render_asset_bar(df: pd.DataFrame) -> None:
    """Barra de contexto do(s) ativo(s) no recorte atual (nome + dados em destaque)."""
    if df.empty:
        return

    ativos = df.drop_duplicates("id_ativo")
    n = int(ativos["id_ativo"].nunique())

    if n == 1:
        r = ativos.iloc[0]
        nsys = int(df["sistema"].nunique())
        pills = "".join(
            f'<span class="vp-pill">{html.escape(str(v))}</span>'
            for v in (
                r["tipo_ativo"],
                f'{int(r["idade_ativo"])} anos',
                r["ambiente_exposicao"],
                f"{nsys} sistema(s)",
                r["id_ativo"],
            )
        )
        st.markdown(
            f"""
            <div class="vp-card" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
                <div>
                    <div class="lbl" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:{COLORS['slate_500']};font-weight:600">Ativo em análise</div>
                    <div style="font-size:20px;font-weight:800;color:{COLORS['brand_900']}">{html.escape(str(r["nome_ativo"]))}</div>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-left:auto">{pills}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        nomes = sorted(ativos["nome_ativo"].astype(str).unique())
        mostra = ", ".join(nomes[:6]) + ("…" if len(nomes) > 6 else "")
        st.markdown(
            f"""
            <div class="vp-card" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
                <div class="lbl" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:{COLORS['slate_500']};font-weight:600">Ativos no recorte</div>
                <span style="font-size:20px;font-weight:800;color:{COLORS['brand_900']}">{n}</span>
                <span style="color:{COLORS['slate_700']};font-size:13px">{html.escape(mostra)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
