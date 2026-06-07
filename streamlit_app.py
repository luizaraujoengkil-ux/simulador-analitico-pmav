"""
Simulador Analítico PMAV – VistoPred
Ponto de entrada do app Streamlit (arquivo principal lido pelo Streamlit Cloud).

Fluxo:
  Fonte de dados (Modelo / Novo Ativo / VistoPred) → base editável de Tarefas
  → expansão no horizonte → simulação (cenários + OLS + alertas) → dashboard.

UX: o painel "Dados & Tarefas" fica no topo da área principal e ABRE
automaticamente quando o usuário escolhe "Novo Ativo" ou "Baixar do VistoPred",
expondo na hora o formulário / o campo de código. É processado antes de montar a
base, para que edições reflitam no dashboard no mesmo ciclo.
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
MODE_MODEL = "Dados Modelo"
MODE_NEW = "Novo Ativo"
MODE_VP = "Baixar do App VistoPred"

# Opção para criar um sistema personalizado nos formulários.
NEW_SYSTEM_OPT = "➕ Outro (novo sistema)"

# Chaves dos filtros (usadas para resetar no botão "Limpar filtros").
FILTER_KEYS = ["f_ativos", "f_tipos", "f_sistemas", "f_subs", "f_crit", "f_horizonte"]


def clear_filters():
    """Callback do botão Limpar filtros: remove os estados dos filtros."""
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)

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


def asset_type_options() -> list[str]:
    """Tipos padrão + tipos personalizados já presentes na base (para o editor/filtros)."""
    extra = [str(t) for t in st.session_state.working_tasks["tipo_ativo"].dropna().unique()
             if str(t) and str(t) not in ASSET_TYPES]
    return ASSET_TYPES + sorted(set(extra))


def system_options() -> list[str]:
    """Sistemas padrão + sistemas personalizados já presentes na base."""
    extra = [str(s) for s in st.session_state.working_tasks["sistema"].dropna().unique()
             if str(s) and str(s) not in SYSTEM_NAMES]
    return SYSTEM_NAMES + sorted(set(extra))


def editor_column_config(asset_types: list[str], system_types: list[str]) -> dict:
    """Colunas da tabela editável (dropdowns + numéricos validados)."""
    return {
        "id_ativo": st.column_config.TextColumn("ID ativo"),
        "tipo_ativo": st.column_config.SelectboxColumn("Tipo", options=asset_types, required=True),
        "nome_ativo": st.column_config.TextColumn("Nome do ativo", required=True),
        "sistema": st.column_config.SelectboxColumn("Sistema", options=system_types, required=True),
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


# ─────────────────────────── Sidebar (topo) — fonte/cenário ──────────────────────
with st.sidebar:
    st.markdown(
        '<div class="vp-side-eyebrow">VistoPred</div>'
        '<div class="vp-side-logo">Simulador PMAV</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Módulo analítico · v{__version__}")

    st.markdown("**Fonte de dados**")
    mode = st.radio(
        "Selecione a origem dos dados", [MODE_MODEL, MODE_NEW, MODE_VP],
        label_visibility="collapsed",
        captions=["Vários ativos fictícios de exemplo", "Cadastrar do zero / planilha", "Baixar por código da edificação"],
    )
    st.caption("⬇️ Os controles desta opção abrem no painel **Dados & Tarefas** (topo da página).")

    st.divider()
    scenario_id = st.selectbox("Cenário analítico", SCENARIO_IDS,
                               format_func=lambda sid: get_scenario(sid).nome)
    scenario = get_scenario(scenario_id)
    st.caption(scenario.descricao)

    with st.expander("⚙️ Modelo estatístico"):
        source_label = st.radio(
            "Coeficientes da regressão", ["Ajustados (OLS)", "Mockados"],
            help="Os dois usam a mesma fórmula; muda só de onde vêm os pesos (β). "
                 "OLS: calculados dos seus dados. Mockados: fixos no código.",
        )
        source = "ols" if source_label.startswith("Ajustados") else "mock"
        if source == "ols":
            st.caption("🔵 **Ajustados (OLS):** pesos **calculados dos seus dados**; recalculam ao "
                       "editar/importar/baixar. Entrega R² e RMSE. **Recomendado para análise real.**")
        else:
            st.caption("⚪ **Mockados:** pesos **fixos** (referência), não mudam com os dados. "
                       "Para demonstração, base pequena ou impor valores de especialista.")


# ─────────────────────────────────────── Cabeçalho ───────────────────────────────
ui.render_header(scenario)


# ============== PAINEL DE DADOS (topo) — abre sozinho por modo ==================
# Abre automaticamente em "Novo Ativo"/"VistoPred" ou quando a base está vazia.
_panel_open = (mode in (MODE_NEW, MODE_VP)) or st.session_state.working_tasks.empty

with st.expander("📥  Dados & Tarefas — gerenciar a base (importar · editar · baixar do VistoPred)",
                 expanded=_panel_open):

    # ---- Controles específicos do modo selecionado ----
    if mode == MODE_MODEL:
        c = st.columns([1, 2])
        if c[0].button("🔄 Carregar / restaurar base de exemplo", use_container_width=True):
            st.session_state.working_tasks = ds.example_tasks()
            st.session_state.editor_version += 1
            st.rerun()
        c[1].caption("Base fictícia com 6 ativos. Edite as Tarefas na tabela abaixo.")

    elif mode == MODE_NEW:
        st.markdown("##### 🆕 Cadastrar novo ativo (atalho)")
        with st.form("cadastro_ativo", clear_on_submit=True):
            a1, a2, a3 = st.columns([1.3, 1, 1])
            na_nome = a1.text_input("Nome do ativo *")
            na_tipo = a2.selectbox("Tipo de ativo *", ASSET_TYPES,
                                   help="Escolha 'Outro' e digite ao lado para um tipo personalizado.")
            na_tipo_custom = a3.text_input("Se 'Outro', especifique", placeholder="ex.: Reservatório")
            a4, a5, a6 = st.columns(3)
            na_id = a4.text_input("ID do ativo (opcional)")
            na_idade = a5.number_input("Idade (anos)", min_value=0, max_value=120, value=10, step=1)
            na_amb = a6.selectbox("Ambiente", EXPOSURE_ENVIRONMENTS, index=1)
            ok = st.form_submit_button("➕ Cadastrar ativo (cria 1 Tarefa-modelo)", type="primary")
            if ok:
                tipo_final = (na_tipo_custom.strip()
                              if (na_tipo == "Outro" and na_tipo_custom.strip()) else na_tipo)
                if not na_nome.strip():
                    st.error("Informe o **Nome do ativo**.")
                else:
                    skel = ds.skeleton_task(na_nome, tipo_final, na_id, na_idade, na_amb)
                    st.session_state.working_tasks = pd.concat(
                        [st.session_state.working_tasks, skel], ignore_index=True)
                    st.session_state.editor_version += 1
                    st.success(f"Ativo '{na_nome.strip()}' ({tipo_final}) cadastrado com 1 Tarefa-modelo. "
                               "Ajuste sistema, subsistema e custo na tabela abaixo.")
                    st.rerun()
        cc = st.columns([1, 2])
        if cc[0].button("🧹 Começar base vazia", use_container_width=True):
            st.session_state.working_tasks = ds.empty_tasks()
            st.session_state.editor_version += 1
            st.rerun()
        cc[1].caption("Cadastrou o ativo? Ele já aparece nos filtros **Ativo (nome)** e **Tipo de ativo**. "
                      "Use o **formulário guiado** abaixo para adicionar mais Tarefas/O.S. a ele.")

    else:  # MODE_VP
        st.markdown("##### 🔌 Baixar do App VistoPred")
        st.caption("Informe o **Código da Edificação** (ex.: um UUID como "
                   "`d387aef0-9efb-11f0-9f5d-bb4ac9f1ee38`).")
        vc = st.columns([2.2, 1, 1])
        codigo = vc[0].text_input("Código da Edificação", placeholder="cole o código do VistoPred aqui")
        modo_dl = vc[1].radio("Ao baixar", ["Substituir", "Adicionar"], horizontal=False)
        vc[2].caption("🔌 Conexão configurada" if vp.is_configured(vp_cfg)
                      else "ℹ️ Demonstração\n(sem conexão real)")
        if st.button("🔌 Conectar e baixar dados", type="primary"):
            try:
                tarefas_vp, msg = vp.fetch_tasks(codigo, vp_cfg)
                if modo_dl == "Substituir":
                    st.session_state.working_tasks = tarefas_vp
                else:
                    st.session_state.working_tasks = pd.concat(
                        [st.session_state.working_tasks, tarefas_vp], ignore_index=True)
                st.session_state.editor_version += 1
                st.success(f"{len(tarefas_vp)} Tarefa(s) baixada(s) para o código informado.")
                st.info(msg)
                st.rerun()
            except NotImplementedError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error(str(exc))

    st.divider()

    # ---- Tabela editável: corrigir · incluir · excluir ----
    ui.section_title("Base de Tarefas — corrigir · incluir · excluir")
    edited = st.data_editor(
        st.session_state.working_tasks,
        num_rows="dynamic", use_container_width=True, height=320,
        key=f"editor_{st.session_state.editor_version}",
        column_config=editor_column_config(asset_type_options(), system_options()),
    )
    st.session_state.working_tasks = edited
    _clean_now, _, _ = ds.validate_tasks(st.session_state.working_tasks)
    st.caption(f"✅ {len(_clean_now)} Tarefa(s) válida(s) · ➕ adicione no fim da tabela · "
               "selecione linhas e use 🗑️ para excluir. As mudanças atualizam a simulação.")

    # ---- Formulário guiado (principal no modo Novo Ativo) ----
    with st.expander("➕ Adicionar Tarefa (formulário guiado)", expanded=(mode == MODE_NEW)):
        with st.form("nova_tarefa", clear_on_submit=True):
            f1, f2 = st.columns([2, 1])
            nome = f1.text_input("Nome do ativo *")
            id_ativo = f2.text_input("ID do ativo", help="Opcional — gerado do nome se vazio.")
            ft1, ft2 = st.columns(2)
            tipo = ft1.selectbox("Tipo de ativo *", ASSET_TYPES)
            tipo_custom = ft2.text_input("Se 'Outro', especifique", placeholder="tipo personalizado")

            f4, f5 = st.columns(2)
            sistema_sel = f4.selectbox("Sistema *", SYSTEM_NAMES + [NEW_SYSTEM_OPT],
                                       help="Escolha 'Outro (novo sistema)' para criar um sistema novo.")
            sistema_custom = f5.text_input("Se 'Outro', novo sistema", placeholder="ex.: Acessibilidade")
            f5b, f6 = st.columns(2)
            subsistema = f5b.text_input("Subsistema *")
            tipo_os = f6.selectbox("Tipo de O.S.", OS_TYPES)

            f7, f8, f9 = st.columns(3)
            periodicidade = f7.number_input("Periodicidade (meses) *", min_value=1, max_value=120, value=12, step=1)
            criticidade = f8.selectbox("Criticidade *", CRITICALITY_LEVELS, format_func=criticality_label, index=2)
            custo = f9.number_input("Custo base (R$) *", min_value=0.0, value=20000.0, step=500.0)

            f10, f11, f12 = st.columns(3)
            ambiente = f10.selectbox("Ambiente de exposição", EXPOSURE_ENVIRONMENTS, index=1)
            idade = f11.number_input("Idade do ativo (anos)", min_value=0, max_value=120, value=10, step=1)
            fator = f12.slider("Fator de degradação", 0.05, 0.95, 0.30, 0.01)

            data_ref = st.date_input("Data de referência")
            obs = st.text_input("Observação técnica (opcional)")
            submitted = st.form_submit_button("➕ Adicionar Tarefa à base", type="primary")

            if submitted:
                sistema_final = (sistema_custom.strip()
                                 if (sistema_sel == NEW_SYSTEM_OPT and sistema_custom.strip()) else sistema_sel)
                tipo_final = (tipo_custom.strip()
                              if (tipo == "Outro" and tipo_custom.strip()) else tipo)
                if not nome.strip() or not subsistema.strip():
                    st.error("Preencha pelo menos **Nome do ativo** e **Subsistema**.")
                elif sistema_sel == NEW_SYSTEM_OPT and not sistema_custom.strip():
                    st.error("Você escolheu **Outro (novo sistema)** — digite o nome do novo sistema.")
                else:
                    nova = {
                        "id_ativo": id_ativo.strip() or ds.slugify_id(nome),
                        "tipo_ativo": tipo_final, "nome_ativo": nome.strip(),
                        "sistema": sistema_final, "subsistema": subsistema.strip(), "tipo_os": tipo_os,
                        "periodicidade_meses": int(periodicidade), "criticidade": int(criticidade),
                        "custo_base": float(custo), "ambiente_exposicao": ambiente,
                        "idade_ativo": int(idade), "fator_degradacao": float(fator),
                        "data_referencia": str(data_ref), "observacao_tecnica": obs.strip(),
                    }
                    st.session_state.working_tasks = pd.concat(
                        [st.session_state.working_tasks, pd.DataFrame([nova], columns=ds.TASK_COLUMNS)],
                        ignore_index=True)
                    st.session_state.editor_version += 1
                    st.success(f"Tarefa adicionada: {sistema_final} · {subsistema} ({nome}).")
                    st.rerun()

    # ---- Importar planilha ----
    with st.expander("📄 Importar planilha (CSV / Excel)"):
        st.download_button("Baixar template CSV", data=ds.task_template_csv(),
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
                    st.dataframe(clean, use_container_width=True, hide_index=True, height=180)
                    if st.button("➕ Adicionar Tarefas importadas à base", type="primary"):
                        st.session_state.working_tasks = pd.concat(
                            [st.session_state.working_tasks, clean], ignore_index=True)
                        st.session_state.editor_version += 1
                        st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível ler o arquivo: {exc}")

    # ---- Exportar ----
    with st.expander("⬇️ Exportar"):
        x1, x2 = st.columns(2)
        x1.download_button(
            "Exportar Tarefas (CSV)",
            data=st.session_state.working_tasks.to_csv(index=False).encode("utf-8-sig"),
            file_name="tarefas_pmav.csv", mime="text/csv", use_container_width=True)
        x2.download_button(
            "Exportar base completa (10 anos)",
            data=ds.expand_tasks(_clean_now).to_csv(index=False).encode("utf-8-sig"),
            file_name="base_pmav_completa.csv", mime="text/csv",
            disabled=_clean_now.empty, use_container_width=True)


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
def _prune(key: str, options: list) -> None:
    """Remove do estado do filtro valores que não existem mais nas opções."""
    if key in st.session_state:
        st.session_state[key] = [v for v in st.session_state[key] if v in options]


with st.sidebar:
    st.divider()
    st.markdown("**Filtros**")
    st.caption("＊ Campo de filtro vazio = mostra **tudo**. Os filtros se combinam (lógica E).")

    nomes_opt = sorted(base["nome_ativo"].unique()) if has_data else []
    _prune("f_ativos", nomes_opt)
    f_ativos = st.multiselect("Ativo (nome)", nomes_opt, key="f_ativos")

    tipos_opt = sorted(base["tipo_ativo"].unique()) if has_data else []
    _prune("f_tipos", tipos_opt)
    f_tipos = st.multiselect("Tipo de ativo", tipos_opt, key="f_tipos")

    sistemas_opt = sorted(base["sistema"].unique()) if has_data else []
    _prune("f_sistemas", sistemas_opt)
    f_sistemas = st.multiselect("Sistema", sistemas_opt, key="f_sistemas")

    _sub_pool = base[base["sistema"].isin(f_sistemas)] if (f_sistemas and has_data) else base
    subs_opt = sorted(_sub_pool["subsistema"].unique()) if has_data else []
    _prune("f_subs", subs_opt)
    f_subs = st.multiselect("Subsistema", subs_opt, key="f_subs")

    f_crit = st.multiselect("Criticidade", CRITICALITY_LEVELS, format_func=criticality_label, key="f_crit")
    f_horizonte = st.slider("Horizonte (ano do PMAV)", 1, 10, (1, 10), key="f_horizonte")
    st.button("🧹 Limpar filtros", use_container_width=True, on_click=clear_filters)


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


# ─────────────────────────────────────── Dashboard ───────────────────────────────
if not has_data:
    st.info("Sem dados na base. No painel **Dados & Tarefas** (acima): cadastre um **Novo Ativo**, "
            "**baixe do App VistoPred** pelo código, ou volte para os **Dados Modelo** na barra lateral.")
elif df_f.empty:
    st.warning("Nenhum registro corresponde aos filtros selecionados. Ajuste os filtros na barra lateral.")
else:
    ui.render_asset_bar(df_f)
    st.write("")
    ui.render_kpis(kpis)
    with st.expander("ℹ️ Entenda a criticidade e os alertas (e como o cenário muda a simulação)"):
        ui.render_criticality_help()
    st.write("")
    ui.render_model_panel(model)
    ui.section_title("Coeficientes do modelo (β) — efeito de cada fator")
    st.plotly_chart(charts.chart_coefficients(model), use_container_width=True)
    st.caption("Azul = o fator **aumenta** o custo previsto · vermelho = **reduz**. "
               "A **frequência** é o fator dominante e a **criticidade** é o único de efeito inverso. "
               "O β₀ (intercepto) é apenas a âncora da reta — por isso não entra como fator no gráfico.")
    with st.expander("ℹ️ Sobre o modelo — qual opção de coeficientes usar?"):
        st.markdown(
            "**Os dois modos usam a mesma fórmula** — muda só *de onde vêm os pesos (β)*.\n\n"
            "- 🔵 **Ajustados (OLS):** os β são **calculados a partir dos seus dados** (statsmodels). "
            "Adaptam-se quando você edita, importa ou baixa dados; entregam **R²** e **RMSE**. "
            "**Recomendado para análise real.**\n"
            "- ⚪ **Mockados:** β **fixos** (em `pmav/regression.py`), não mudam com os dados. "
            "Bons para **demonstração**, base pequena ou impor **pesos de especialista**.\n\n"
            "**Analogia:** OLS = alfaiate (corta sob medida); Mockado = roupa de tamanho padrão.\n\n"
            "**Dica:** no OLS, o *custo total previsto* tende a coincidir com o *custo total ajustado* "
            "(modelo sem viés). Nos mockados eles divergem — é a régua fixa, não feita sob medida. "
            "Em ambos, só muda o **custo previsto**; o **custo ajustado** (referência do cenário) é o mesmo."
        )
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
ui.section_title("Autoria")
st.markdown(
    "Desenvolvido por **Luiz Araujo** — "
    "[luiz.junior@ime.eb.br](mailto:luiz.junior@ime.eb.br) · "
    "IME — Instituto Militar de Engenharia"
)
st.caption(
    "Simulador Analítico PMAV – VistoPred · base montada na sessão · "
    "modelo de regressão linear múltipla (OLS) para fins analíticos."
)
