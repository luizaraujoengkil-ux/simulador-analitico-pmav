"""
Identidade visual VistoPred para o Streamlit.

Concentra a paleta de cores, o CSS customizado (cards, header, badges) e helpers
de cor. A combinação de azul escuro, azul petróleo e ciano/teal dá o aspecto de
produto analítico premium — não um Streamlit genérico.
"""
from __future__ import annotations

import streamlit as st

from .catalog import CRITICALITY_SCALE

# Paleta VistoPred.
COLORS = {
    "brand_950": "#081a31",
    "brand_900": "#0f2c50",
    "brand_800": "#143a6a",
    "brand_700": "#174680",
    "brand_500": "#2670bd",
    "petroleo": "#0e4d5c",
    "ciano": "#06b6d4",
    "ciano_600": "#0891b2",
    "teal": "#14b8a6",
    "branco": "#ffffff",
    "cinza_100": "#f1f5f9",
    "cinza_200": "#e2e8f0",
    "slate_500": "#64748b",
    "slate_700": "#334155",
}

# Sequência de cores para gráficos (coerente com a marca).
CHART_COLORWAY = ["#174680", "#0891b2", "#14b8a6", "#2670bd", "#0e4d5c", "#7eb5e6", "#22d3ee"]


def criticality_color(level: int) -> str:
    info = CRITICALITY_SCALE.get(int(level))
    return info.color if info else COLORS["slate_500"]


def inject_css() -> None:
    """Injeta o CSS global do app (chamar uma vez, logo após set_page_config)."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; }}

        /* Espaçamento e fundo */
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1400px; }}
        [data-testid="stAppViewContainer"] {{
            background:
              radial-gradient(1200px 600px at 100% -10%, rgba(6,182,212,0.07), transparent 60%),
              radial-gradient(1000px 500px at -10% 0%, rgba(15,44,80,0.07), transparent 55%),
              {COLORS['cinza_100']};
        }}
        #MainMenu, footer {{ visibility: hidden; }}

        /* Header / banner */
        .vp-header {{
            background: linear-gradient(110deg, {COLORS['brand_950']} 0%, {COLORS['brand_900']} 45%, {COLORS['petroleo']} 100%);
            border-radius: 18px; padding: 22px 26px; color: #fff;
            display: flex; align-items: center; gap: 18px;
            box-shadow: 0 18px 40px -22px rgba(8,26,49,0.55);
            margin-bottom: 18px;
        }}
        .vp-logo {{
            width: 52px; height: 52px; border-radius: 14px; flex: 0 0 auto;
            display: grid; place-items: center; font-weight: 800; font-size: 26px;
            color: {COLORS['ciano']}; background: rgba(6,182,212,0.16);
            border: 1px solid rgba(34,211,238,0.45);
        }}
        .vp-header .eyebrow {{ font-size: 12px; letter-spacing: .22em; text-transform: uppercase; color: #22d3ee; font-weight: 700; margin: 0; }}
        .vp-header h1 {{ font-size: 24px; font-weight: 800; margin: 2px 0 2px; line-height: 1.15; }}
        .vp-header p.sub {{ font-size: 14px; color: rgba(214,233,249,0.85); margin: 0; }}
        .vp-header .scn {{ margin-left: auto; text-align: right; }}
        .vp-header .scn .lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color: rgba(214,233,249,0.7); }}
        .vp-header .scn .val {{ font-size: 16px; font-weight: 700; }}

        /* Cards / KPIs */
        .vp-card {{
            background: #fff; border: 1px solid {COLORS['cinza_200']}; border-radius: 16px;
            padding: 16px 18px; box-shadow: 0 1px 2px rgba(8,26,49,.04), 0 12px 30px -18px rgba(8,26,49,.28);
            height: 100%;
        }}
        .vp-kpi .lbl {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; color: {COLORS['slate_500']}; font-weight: 600; }}
        .vp-kpi .val {{ font-size: 26px; font-weight: 800; color: {COLORS['brand_900']}; margin-top: 4px; line-height: 1.1; }}
        .vp-kpi .val.sm {{ font-size: 18px; }}
        .vp-kpi .val.danger {{ color: #dc2626; }}
        .vp-kpi .val.warn {{ color: #d97706; }}
        .vp-kpi .hint {{ font-size: 11px; color: {COLORS['slate_500']}; margin-top: 2px; }}
        .vp-kpi .accent-bar {{ height: 3px; width: 38px; border-radius: 999px; margin-bottom: 10px;
            background: linear-gradient(90deg, {COLORS['brand_700']}, {COLORS['ciano']}); }}

        /* Section title */
        .vp-section {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
            color: {COLORS['brand_800']}; margin: 6px 0 2px; }}

        /* Badges */
        .vp-badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; color: #fff; }}
        .vp-pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700;
            border: 1px solid {COLORS['cinza_200']}; color: {COLORS['slate_700']}; background: {COLORS['cinza_100']}; }}

        /* Alert cards */
        .vp-alert {{ border-radius: 14px; padding: 14px 16px; margin-bottom: 10px; border-left: 5px solid #94a3b8; background: #fff;
            border: 1px solid {COLORS['cinza_200']}; box-shadow: 0 10px 26px -20px rgba(8,26,49,.4); }}
        .vp-alert.imediato {{ border-left-color: #dc2626; background: linear-gradient(90deg, rgba(220,38,38,.06), #fff 40%); }}
        .vp-alert.preditivo {{ border-left-color: #d97706; background: linear-gradient(90deg, rgba(217,119,6,.06), #fff 40%); }}
        .vp-alert .top {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
        .vp-alert .sys {{ font-weight: 700; color: {COLORS['brand_900']}; }}
        .vp-alert .row {{ font-size: 13px; color: {COLORS['slate_700']}; margin: 2px 0; }}
        .vp-alert .row b {{ color: {COLORS['brand_800']}; }}

        /* Executive summary */
        .vp-exec {{ background: linear-gradient(120deg, #fff, {COLORS['cinza_100']}); border: 1px solid {COLORS['cinza_200']};
            border-radius: 16px; padding: 18px 22px; font-size: 15px; line-height: 1.6; color: {COLORS['slate_700']};
            box-shadow: 0 12px 30px -22px rgba(8,26,49,.35); }}

        /* Sidebar branding */
        [data-testid="stSidebar"] {{ background: linear-gradient(180deg, {COLORS['brand_950']}, {COLORS['brand_900']}); }}
        [data-testid="stSidebar"] * {{ color: #e8f1fb; }}
        [data-testid="stSidebar"] .vp-side-logo {{ font-weight: 800; font-size: 18px; color: #fff; }}
        [data-testid="stSidebar"] .vp-side-eyebrow {{ font-size: 11px; letter-spacing: .2em; text-transform: uppercase; color: #22d3ee; font-weight: 700; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
