"""
Simulador Analítico PMAV – VistoPred
Ponto de entrada do app Streamlit (arquivo principal lido pelo Streamlit Cloud).

Fluxo:
  Fonte de dados (Modelo / Novo Ativo / VistoPred) → base editável de Tarefas
  → expansão no horizonte → simulação (cenários + OLS + alertas) → dashboard.

Observação de ordem: a aba "Dados & Tarefas" é processada ANTES de montar a base
(embora apareça depois no layout), para que edições na tabela atualizem o
dashboard no mesmo ciclo.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pmav import __version__
from pmav import aggregations as agg
from pmav import charts
from pmav import components as ui
from pmav import data_source as ds
from pmav import vistopred_client as vp
from pmav.catalog import (
    ASSET_TYPES,
    CRITICALITY_LEVELS,
    EXPOSURE_ENVIRONMENTS,
    OS_TYPES,
    SYSTEM_NAMES,
    criticality_label,
)
from pmav.mock_data import COLUMNS
from pmav.scenarios import SCENARIOS, SCENARIO_IDS, get_scenario
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

# Modos de fonte de dados.
MODE_MODEL = "Edificação Modelo"
MODE_NEW = "Novo Ativo"
MODE_VP = "Baixar do App VistoPred"

# Estado da sessão.
if "working_tasks" not in st.session_state:
    st.session_state.working_tasks = ds.example_tasks()   # começa com a base de exemplo
if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0                    # versiona o editor p/ recarregar

# Configuração de conexão VistoPred (opcional, via secrets).
try:
    vp_cfg = dict(st.secrets.get("vistopred", {}))
except Exception:
    vp_cfg = {}


# ─────────────────────────────── Funções cacheadas ───────────────────────────────
@st.cache_data(show_spinner=False)
def run_simulation_cached(source: str, base: pd.DataFrame):
    """Roda todos os cenários sobre a base. Cache por (source + conteúdo da base)."""
    return simulate_concat(base, SCENARIOS, source)


# ─────────────────────────── Sidebar (topo) — fonte/cenário ──────────────────────
with st.sidebar:
    st.markdown(
        '<div class="vp-side-eyebrow">VistoPred</div>'
        '<div class="vp-side-logo">Simulador PMAV</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Módulo analítico · v{__version__}")

    # >>> Seletor de FONTE DE DADOS (área destacada no topo) <<<
    st.markdown("**Fonte de dados**")
    mode = st.radio(
        "Selecione a origem dos dados", [MODE_MODEL, MODE_NEW, MODE_VP],
        label_visibility="collapsed",
        captions=["Base fictícia de exemplo", "Cadastrar do zero / planilha", "Baixar por código da edificação"],
    )

    st.divider()
    scenario_id = st.selectbox("Cenário analítico", SCENARIO_IDS,
                               format_func=lambda sid: get_scenario(sid).nome)
    scenario = get_scenario(scenario_id)
    st.caption(scenario.descricao)

    with st.expander("⚙️ Modelo estatístico"):
        source_label = st.radio(
            "Coeficientes da regressão", ["Ajustados (OLS)", "Mockados"],
            help="OLS: estimados dos dados (statsmodels). Mockados: fixos (pmav/regression.py).",
        )
        source = "ols" if source_label.startswith("Ajustados") else "mock"


# ─────────────────────────────────── Cabeçalho + abas ────────────────────────────
ui.render_header(scenario)
tab_dash, tab_data = st.tabs(["📊  Dashboard", "📥  Dados & Tarefas"])


def editor_column_config() -> dict:
    """Configuração das colunas da tabela editável (dropdowns + numéricos validados)."""
    return {
        "id_ativo": st.column_config.TextColumn("ID ativo"),
        "tipo_ativo": st.column_config.SelectboxColumn("Tipo", options=ASSET_TYPES, required=True),
        "nome_ativo": st.column_config.TextColumn("Nome do ativo", required=True),
        "sistema": st.column_config.SelectboxColumn("Sistema", options=SYSTEM_NAMES, required=True),
        "subsistema": st.column_config.TextColumn("Subsistema", required=True),
        "tipo_os": st.column_config.SelectboxColumn("Tipo de O.S.", options=OS_TYPES),
        "periodicidade_meses": st.column_config.NumberColumn("Period. (meses)", min_value=1, max_value=120, step=1),
        "criticidade": st.column_config.NumberColumn("Criticidade", min_value=0, max_value=5, step=1,
                                                     help="0 = risco iminente · 5 = muito baixa"),
        "custo_base": st.column_config.NumberColumn("Custo base (R$)", min_value=0.0, step=500.0, format="%.0f"),
        "ambiente_exposicao": st.column_config.SelectboxColumn("Ambiente", options=EXPOSURE_ENVIRONMENTS),
        "idade_ativo": st.column_config.NumberColumn("Idade (anos)", min_value=0, max_value=120, step=1),
        "fator_degradacao": st.column_config.NumberColumn("Fator degr.", min_value=0.0, max_value=1.0, step=0.01, format="%.2f"),
        "data_referencia": st.column_config.TextColumn("Data ref."),
        "observacao_tecnica": st.column_config.TextColumn("Observação", width="large"),
    }


# ============================ ABA 2 — DADOS & TAREFAS ===========================
# (processada antes de montar a base; aparece como 2ª aba no layout)
with tab_data:
    ui.section_title(f"Fonte de dados — {mode}")

    if mode == MODE_MODEL:
        c = st.columns([1, 2])
        if c[0].button("🔄 Carregar / restaurar base de exemplo", use_container_width=True):
            st.session_state.working_tasks = ds.example_tasks()
            st.session_state.editor_version += 1
            st.rerun()
        c[1].caption("Base fictícia com 6 ativos (Edificação, Ponte, Viaduto, Túnel, Rodovia, Contenção). "
                     "Edite as Tarefas na tabela abaixo.")

    elif mode == MODE_NEW:
        c = st.columns([1, 2])
        if c[0].button("🆕 Iniciar base vazia (novo ativo)", use_container_width=True):
            st.session_state.working_tasks = ds.empty_tasks()
            st.session_state.editor_version += 1
            st.rerun()
        c[1].caption("Comece do zero: cadastre o ativo (tipo, nome) e suas Tarefas/O.S. na tabela abaixo, "
                     "ou importe uma planilha logo adiante.")

    else:  # MODE_VP
        st.caption("Baixe os dados de uma edificação do App VistoPred informando o **código**.")
        c = st.columns([1.4, 1, 1])
        codigo = c[0].text_input("Código da edificação (VistoPred)", placeholder="ex.: 10482")
        modo_dl = c[1].radio("Ao baixar", ["Substituir", "Adicionar"], horizontal=True)
        c[2].caption("🔌 Conexão configurada" if vp.is_configured(vp_cfg)
                     else "ℹ️ Demonstração (conexão real não configurada)")
        if st.button("🔌 Conectar e baixar", type="primary"):
            try:
                tarefas_vp, msg = vp.fetch_tasks(codigo, vp_cfg)
                if modo_dl == "Substituir":
                    st.session_state.working_tasks = tarefas_vp
                else:
                    st.session_state.working_tasks = pd.concat(
                        [st.session_state.working_tasks, tarefas_vp], ignore_index=True)
                st.session_state.editor_version += 1
                st.success(f"{len(tarefas_vp)} Tarefa(s) baixada(s) para o código {codigo}.")
                st.info(msg)
                st.rerun()
            except NotImplementedError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error(str(exc))

    st.divider()

    # Tabela editável: editar · incluir · excluir
    ui.section_title("Editar base — Tarefas (corrigir · incluir · excluir)")
    edited = st.data_editor(
        st.session_state.working_tasks,
        num_rows="dynamic", use_container_width=True, height=380,
        key=f"editor_{st.session_state.editor_version}",
        column_config=editor_column_config(),
    )
    st.session_state.working_tasks = edited
    _clean_now, _, _ = ds.validate_tasks(st.session_state.working_tasks)
    st.caption(f"✅ {len(_clean_now)} Tarefa(s) válida(s) na base · ➕ adicione linhas no fim da tabela · "
               "selecione e use 🗑️ para excluir. As mudanças atualizam a simulação automaticamente.")

    st.divider()

    # Importar planilha (CSV/Excel)
    ui.section_title("Importar planilha (CSV / Excel)")
    st.download_button("📄 Baixar template CSV", data=ds.task_template_csv(),
                       file_name="template_tarefas_pmav.csv", mime="text/csv")
    uploaded = st.file_uploader("Enviar arquivo de Tarefas (uma linha por Tarefa)", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        try:
            raw = ds.read_uploaded(uploaded)
            clean, errors, warnings = ds.validate_tasks(raw)
            for e in errors:
                st.error(e)
            for w in warnings:
                st.warning(w)
            if not clean.empty:
                st.success(f"{len(clean)} Tarefa(s) válida(s) prontas para importar.")
                st.dataframe(clean, use_container_width=True, hide_index=True, height=200)
                if st.button("➕ Adicionar Tarefas importadas à base", type="primary"):
                    st.session_state.working_tasks = pd.concat(
                        [st.session_state.working_tasks, clean], ignore_index=True)
                    st.session_state.editor_version += 1
                    st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível ler o arquivo: {exc}")

    st.divider()

    # Exportar
    ui.section_title("Exportar")
    e1, e2 = st.columns(2)
    e1.download_button(
        "⬇️ Exportar Tarefas (CSV)",
        data=st.session_state.working_tasks.to_csv(index=False).encode("utf-8-sig"),
        file_name="tarefas_pmav.csv", mime="text/csv", use_container_width=True,
    )
    e2.download_button(
        "⬇️ Exportar base completa (expandida 10 anos)",
        data=ds.expand_tasks(_clean_now).to_csv(index=False).encode("utf-8-sig"),
        file_name="base_pmav_completa.csv", mime="text/csv",
        disabled=_clean_now.empty, use_container_width=True,
    )


# ─────────────────────── Montagem da base + simulação ────────────────────────────
clean_tasks, _, _ = ds.validate_tasks(st.session_state.working_tasks)
base = ds.expand_tasks(clean_tasks)
has_data = not base.empty

if has_data:
    full, models = run_simulation_cached(source, base)
    df_scn = full[full["cenario"] == scenario_id]
else:
    full = pd.DataFrame(columns=COLUMNS)
    df_scn = full


# ─────────────────────────────── Sidebar (filtros) ───────────────────────────────
with st.sidebar:
    st.divider()
    st.markdown("**Filtros**")
    nomes_opt = sorted(base["nome_ativo"].unique()) if has_data else []
    f_ativos = st.multiselect("Ativo (nome)", nomes_opt)
    f_tipos = st.multiselect("Tipo de ativo", sorted(base["tipo_ativo"].unique()) if has_data else [])
    f_sistemas = st.multiselect("Sistema", sorted(base["sistema"].unique()) if has_data else [])
    _sub_pool = base[base["sistema"].isin(f_sistemas)] if (f_sistemas and has_data) else base
    f_subs = st.multiselect("Subsistema", sorted(_sub_pool["subsistema"].unique()) if has_data else [])
    f_crit = st.multiselect("Criticidade", CRITICALITY_LEVELS, format_func=criticality_label)
    f_horizonte = st.slider("Horizonte (ano do PMAV)", 1, 10, (1, 10))
    st.divider()
    st.caption("Base na sessão · pronto para integração futura ao VistoPred.")


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df["horizonte_ano"].between(f_horizonte[0], f_horizonte[1])
    if f_ativos:
        mask &= df["nome_ativo"].isin(f_ativos)
    if f_tipos:
        mask &= df["tipo_ativo"].isin(f_tipos)
    if f_sistemas:
        mask &= df["sistema"].isin(f_sistemas)
    if f_subs:
        mask &= df["subsistema"].isin(f_subs)
    if f_crit:
        mask &= df["criticidade"].isin(f_crit)
    return df[mask]


if has_data:
    df_f = apply_filters(df_scn)
    df_all_f = apply_filters(full)
    model = models[scenario_id]
    kpis = agg.compute_kpis(df_f)
else:
    df_f = full
    df_all_f = full
    model = None
    kpis = agg.compute_kpis(df_f)


# ============================== ABA 1 — DASHBOARD ================================
with tab_dash:
    if not has_data:
        st.info("Sem dados na base. Use o seletor **Fonte de dados** (barra lateral): carregue a "
                "**Edificação Modelo**, comece um **Novo Ativo** ou **baixe do App VistoPred** — "
                "e edite as Tarefas na aba *Dados & Tarefas*.")
    elif df_f.empty:
        st.warning("Nenhum registro corresponde aos filtros selecionados. Ajuste os filtros na barra lateral.")
    else:
        ui.render_asset_bar(df_f)
        st.write("")
        ui.render_kpis(kpis)
        st.write("")
        ui.render_model_panel(model)
        st.write("")

        col1, col2 = st.columns(2)
        with col1:
            ui.section_title("Custo total previsto por cenário")
            st.plotly_chart(charts.chart_cost_by_scenario(agg.cost_by_scenario(df_all_f), scenario_id),
                            use_container_width=True)
        with col2:
            ui.section_title("Custo previsto por sistema")
            st.plotly_chart(charts.chart_cost_by_system(agg.cost_by_system(df_f)), use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            ui.section_title("Custo ajustado vs. custo previsto")
            st.plotly_chart(charts.chart_adjusted_vs_predicted(agg.adjusted_vs_predicted(df_f)), use_container_width=True)
        with col4:
            ui.section_title("Distribuição de alertas por sistema")
            st.plotly_chart(charts.chart_alerts_by_system(agg.alerts_by_system(df_f)), use_container_width=True)

        ui.section_title("Custo previsto e criticidade média projetada por sistema")
        st.plotly_chart(charts.chart_cost_and_criticality(agg.cost_and_criticality_by_system(df_f)), use_container_width=True)
        st.write("")

        left, right = st.columns([1.15, 1])
        with left:
            ui.section_title("Ranking de sistemas prioritários")
            st.dataframe(
                agg.system_ranking(df_f), use_container_width=True, hide_index=True,
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
        ui.section_title("Tabela analítica detalhada")
        table_cols = [
            "nome_ativo", "tipo_ativo", "sistema", "subsistema", "tipo_os", "criticidade", "criticidade_projetada",
            "periodicidade_meses", "frequencia_prevista", "horizonte_ano",
            "custo_base", "custo_ajustado", "custo_previsto", "prioridade", "status_alerta",
        ]
        st.dataframe(
            df_f[table_cols], use_container_width=True, hide_index=True, height=360,
            column_config={
                "nome_ativo": "Ativo", "tipo_ativo": "Tipo", "sistema": "Sistema", "subsistema": "Subsistema",
                "tipo_os": "Tipo O.S.",
                "criticidade": st.column_config.NumberColumn("Criticidade", help="0 = risco iminente · 5 = muito baixa"),
                "criticidade_projetada": st.column_config.NumberColumn("Crit. projetada", format="%.2f"),
                "periodicidade_meses": st.column_config.NumberColumn("Period. (meses)"),
                "frequencia_prevista": st.column_config.NumberColumn("Freq./ano", format="%.2f"),
                "horizonte_ano": st.column_config.NumberColumn("Ano"),
                "custo_base": st.column_config.NumberColumn("Custo base (R$)", format="%.0f"),
                "custo_ajustado": st.column_config.NumberColumn("Custo ajustado (R$)", format="%.0f"),
                "custo_previsto": st.column_config.NumberColumn("Custo previsto (R$)", format="%.0f"),
                "prioridade": "Prioridade", "status_alerta": "Alerta",
            },
        )
        st.download_button(
            "⬇️ Exportar tabela filtrada (CSV)",
            data=df_f.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"pmav_{scenario_id}.csv", mime="text/csv",
        )

        st.write("")
        ui.section_title("Resumo executivo")
        ui.render_executive_summary(agg.executive_summary(df_f, scenario, kpis))


st.write("")
st.caption(
    "Simulador Analítico PMAV – VistoPred · base montada na sessão · "
    "modelo de regressão linear múltipla (OLS) para fins analíticos."
)
