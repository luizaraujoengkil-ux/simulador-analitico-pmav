"""
Simulador Analítico PMAV – VistoPred
Ponto de entrada do app Streamlit (arquivo principal lido pelo Streamlit Cloud).

Este arquivo é o ORQUESTRADOR: lê filtros, dispara a simulação (cacheada) e
compõe o dashboard a partir das camadas `pmav.aggregations`, `pmav.charts` e
`pmav.components`. Toda a lógica de domínio/estatística vive em `pmav/`.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pmav import __version__
from pmav import aggregations as agg
from pmav import charts
from pmav import components as ui
from pmav.catalog import CRITICALITY_LEVELS, criticality_label
from pmav.mock_data import generate_mock_dataset
from pmav.scenarios import SCENARIO_IDS, SCENARIOS, get_scenario
from pmav.simulation import simulate_concat
from pmav.theme import inject_css

# ─────────────────────────────── Configuração da página ──────────────────────────
st.set_page_config(
    page_title="Simulador Analítico PMAV – VistoPred",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


# ─────────────────────────────── Simulação (cacheada) ────────────────────────────
@st.cache_data(show_spinner=False)
def load_simulation(source: str):
    """
    Gera a base mockada e roda TODOS os cenários de uma vez.
    Retorna (DataFrame com todos os cenários, dict {id_cenário: ModelFit}).
    Cacheado por `source` (ols/mock) — recomputa só quando o usuário troca o modo.
    """
    base = generate_mock_dataset()
    full, models = simulate_concat(base, SCENARIOS, source)
    return full, models


# ───────────────────────────────────── Sidebar ───────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="vp-side-eyebrow">VistoPred</div>'
        '<div class="vp-side-logo">Simulador PMAV</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Módulo analítico · v{__version__}")
    st.divider()

    scenario_id = st.selectbox(
        "Cenário analítico", SCENARIO_IDS,
        format_func=lambda sid: get_scenario(sid).nome,
    )
    scenario = get_scenario(scenario_id)
    st.caption(scenario.descricao)

    with st.expander("⚙️ Modelo estatístico"):
        source_label = st.radio(
            "Coeficientes da regressão",
            ["Ajustados (OLS)", "Mockados"],
            help="OLS: coeficientes estimados dos dados (statsmodels). "
                 "Mockados: coeficientes fixos configuráveis em pmav/regression.py.",
        )
        source = "ols" if source_label.startswith("Ajustados") else "mock"

    full, models = load_simulation(source)
    base_attrs = full[full["cenario"] == scenario_id]

    st.divider()
    st.markdown("**Filtros**")
    f_tipos = st.multiselect("Tipo de ativo", sorted(base_attrs["tipo_ativo"].unique()))
    f_sistemas = st.multiselect("Sistema", sorted(base_attrs["sistema"].unique()))
    _sub_pool = base_attrs[base_attrs["sistema"].isin(f_sistemas)] if f_sistemas else base_attrs
    f_subs = st.multiselect("Subsistema", sorted(_sub_pool["subsistema"].unique()))
    f_crit = st.multiselect("Criticidade", CRITICALITY_LEVELS, format_func=criticality_label)
    f_horizonte = st.slider("Horizonte (ano do PMAV)", 1, 10, (1, 10))

    st.divider()
    st.caption("Dados mockados determinísticos · pronto para integração futura à VistoPred.")


# ────────────────────────────────── Aplicação de filtros ─────────────────────────
def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["horizonte_ano"].between(f_horizonte[0], f_horizonte[1])
    if f_tipos:
        mask &= df["tipo_ativo"].isin(f_tipos)
    if f_sistemas:
        mask &= df["sistema"].isin(f_sistemas)
    if f_subs:
        mask &= df["subsistema"].isin(f_subs)
    if f_crit:
        mask &= df["criticidade"].isin(f_crit)
    return df[mask]


df_scn = full[full["cenario"] == scenario_id]
df_f = apply_filters(df_scn)            # cenário selecionado + filtros
df_all_f = apply_filters(full)          # todos os cenários + filtros (p/ comparação)
model = models[scenario_id]
kpis = agg.compute_kpis(df_f)


# ─────────────────────────────────────── Layout ──────────────────────────────────
ui.render_header(scenario)

if df_f.empty:
    st.warning("Nenhum registro corresponde aos filtros selecionados. Ajuste os filtros na barra lateral.")
    st.stop()

ui.render_kpis(kpis)
st.write("")
ui.render_model_panel(model)
st.write("")

# Linha 1 de gráficos
col1, col2 = st.columns(2)
with col1:
    ui.section_title("Custo total previsto por cenário")
    st.plotly_chart(
        charts.chart_cost_by_scenario(agg.cost_by_scenario(df_all_f), scenario_id),
        use_container_width=True,
    )
with col2:
    ui.section_title("Custo previsto por sistema")
    st.plotly_chart(charts.chart_cost_by_system(agg.cost_by_system(df_f)), use_container_width=True)

# Linha 2 de gráficos
col3, col4 = st.columns(2)
with col3:
    ui.section_title("Custo ajustado vs. custo previsto")
    st.plotly_chart(charts.chart_adjusted_vs_predicted(agg.adjusted_vs_predicted(df_f)), use_container_width=True)
with col4:
    ui.section_title("Distribuição de alertas por sistema")
    st.plotly_chart(charts.chart_alerts_by_system(agg.alerts_by_system(df_f)), use_container_width=True)

# Gráfico de eixo duplo (largura total)
ui.section_title("Custo previsto e criticidade média projetada por sistema")
st.plotly_chart(charts.chart_cost_and_criticality(agg.cost_and_criticality_by_system(df_f)), use_container_width=True)
st.write("")

# Ranking + Alertas
left, right = st.columns([1.15, 1])
with left:
    ui.section_title("Ranking de sistemas prioritários")
    st.dataframe(
        agg.system_ranking(df_f),
        use_container_width=True, hide_index=True,
        column_config={
            "sistema": "Sistema",
            "custo_previsto": st.column_config.NumberColumn("Custo previsto (R$)", format="%.0f"),
            "criticidade_media": st.column_config.NumberColumn("Crit. média", format="%.2f"),
            "alertas": st.column_config.NumberColumn("Alertas"),
            "score": st.column_config.ProgressColumn("Score de prioridade", min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )
with right:
    ui.section_title("Painel de alertas")
    ui.render_alert_panel(df_f)

st.write("")

# Tabela analítica detalhada + exportação
ui.section_title("Tabela analítica detalhada")
table_cols = [
    "nome_ativo", "tipo_ativo", "sistema", "subsistema", "criticidade", "criticidade_projetada",
    "periodicidade_meses", "frequencia_prevista", "horizonte_ano",
    "custo_base", "custo_ajustado", "custo_previsto", "prioridade", "status_alerta",
]
st.dataframe(
    df_f[table_cols],
    use_container_width=True, hide_index=True, height=360,
    column_config={
        "nome_ativo": "Ativo",
        "tipo_ativo": "Tipo",
        "sistema": "Sistema",
        "subsistema": "Subsistema",
        "criticidade": st.column_config.NumberColumn("Criticidade", help="0 = risco iminente · 5 = muito baixa"),
        "criticidade_projetada": st.column_config.NumberColumn("Crit. projetada", format="%.2f"),
        "periodicidade_meses": st.column_config.NumberColumn("Period. (meses)"),
        "frequencia_prevista": st.column_config.NumberColumn("Freq./ano", format="%.2f"),
        "horizonte_ano": st.column_config.NumberColumn("Ano"),
        "custo_base": st.column_config.NumberColumn("Custo base (R$)", format="%.0f"),
        "custo_ajustado": st.column_config.NumberColumn("Custo ajustado (R$)", format="%.0f"),
        "custo_previsto": st.column_config.NumberColumn("Custo previsto (R$)", format="%.0f"),
        "prioridade": "Prioridade",
        "status_alerta": "Alerta",
    },
)
st.download_button(
    "⬇️ Exportar tabela (CSV)",
    data=df_f.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"pmav_{scenario_id}.csv",
    mime="text/csv",
)

st.write("")

# Resumo executivo
ui.section_title("Resumo executivo")
ui.render_executive_summary(agg.executive_summary(df_f, scenario, kpis))

st.write("")
st.caption(
    "Simulador Analítico PMAV – VistoPred · dados simulados para demonstração · "
    "modelo de regressão linear múltipla (OLS) para fins analíticos."
)
