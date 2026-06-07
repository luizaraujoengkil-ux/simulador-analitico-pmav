"""
Fonte de dados do simulador — importação, cadastro manual e montagem da base.

A base usada na simulação é montada a partir de três origens possíveis:
  1. base de exemplo (mock determinístico)         → mock_data.generate_mock_dataset
  2. arquivo importado (CSV/Excel do VistoPred)     → read_uploaded + validate_tasks
  3. Tarefas cadastradas manualmente no app         → formulário (na sessão)

Conceito central: cada **Tarefa** (no VistoPred) é descrita no nível do
subsistema (periodicidade, criticidade, custo...). Ao entrar no simulador, ela é
**expandida nos 10 anos do horizonte** (expand_tasks), participando de cenários,
regressão e alertas como os demais registros.

Módulo PURO (sem Streamlit): a leitura recebe um objeto file-like qualquer.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .mock_data import (
    COLUMNS,
    HORIZON_YEARS,
    REFERENCE_DATE,
    _impact,
    _note,
    _os_type,
    _priority,
    generate_mock_dataset,
)

# Esquema no nível de TAREFA (uma linha por subsistema/tarefa — sem o ano).
TASK_COLUMNS = [
    "id_ativo", "tipo_ativo", "nome_ativo", "sistema", "subsistema", "tipo_os",
    "periodicidade_meses", "criticidade", "custo_base",
    "ambiente_exposicao", "idade_ativo", "fator_degradacao",
    "data_referencia", "observacao_tecnica",
]

# Campos sem os quais a Tarefa não faz sentido.
TASK_REQUIRED = [
    "nome_ativo", "tipo_ativo", "sistema", "subsistema",
    "periodicidade_meses", "criticidade", "custo_base",
]

# Campos opcionais e seus padrões (preenchidos quando ausentes).
TASK_OPTIONAL_DEFAULTS = {
    "id_ativo": None,                 # derivado do nome se vazio
    "tipo_os": "Preventiva",
    "ambiente_exposicao": "Externo",
    "idade_ativo": 0,
    "fator_degradacao": 0.30,
    "data_referencia": REFERENCE_DATE,
    "observacao_tecnica": "",
}

_NUMERIC_FIELDS = ["periodicidade_meses", "criticidade", "custo_base", "idade_ativo", "fator_degradacao"]


# ──────────────────────────────────── Utilidades ─────────────────────────────────


def slugify_id(nome: str) -> str:
    """Gera um id de ativo a partir do nome (ex.: 'Edifício X' → 'EDIFICIO-X')."""
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(nome).strip()).strip("-").upper()
    return s[:16] or "ATIVO"


def _num(x) -> float:
    """Converte valores para float, tolerando formato BR (1.234,56) e 'R$'."""
    try:
        if pd.isna(x):
            return np.nan
    except (TypeError, ValueError):
        pass
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(" ", "").replace("R$", "")
    if not s:
        return np.nan
    if "," in s and "." in s:        # 1.234,56 → 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                    # 1234,56 → 1234.56
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


# ─────────────────────────────────── Template / leitura ──────────────────────────


def make_template_df() -> pd.DataFrame:
    """DataFrame-modelo (com exemplos) para o usuário preencher e reimportar."""
    rows = [
        {"id_ativo": "ED-100", "tipo_ativo": "Edificação", "nome_ativo": "Edifício Exemplo",
         "sistema": "Estrutural", "subsistema": "Vigas e pilares", "tipo_os": "Inspeção",
         "periodicidade_meses": 24, "criticidade": 2, "custo_base": 35000,
         "ambiente_exposicao": "Externo", "idade_ativo": 10, "fator_degradacao": 0.35,
         "data_referencia": "2026-01-01", "observacao_tecnica": "Inspeção estrutural periódica"},
        {"id_ativo": "ED-100", "tipo_ativo": "Edificação", "nome_ativo": "Edifício Exemplo",
         "sistema": "Incêndio", "subsistema": "Sprinklers", "tipo_os": "Preventiva",
         "periodicidade_meses": 12, "criticidade": 1, "custo_base": 18000,
         "ambiente_exposicao": "Interno", "idade_ativo": 10, "fator_degradacao": 0.30,
         "data_referencia": "2026-01-01", "observacao_tecnica": ""},
    ]
    return pd.DataFrame(rows, columns=TASK_COLUMNS)


def task_template_csv() -> bytes:
    """Bytes do template em CSV (UTF-8 com BOM, abre direto no Excel pt-BR)."""
    return make_template_df().to_csv(index=False).encode("utf-8-sig")


def read_uploaded(uploaded) -> pd.DataFrame:
    """Lê um upload (CSV/Excel) num DataFrame. `uploaded` é file-like (tem .name)."""
    name = str(getattr(uploaded, "name", "")).lower()
    if name.endswith(".csv"):
        # sep=None + engine='python' detecta automaticamente ',' ou ';'.
        return pd.read_csv(uploaded, sep=None, engine="python", encoding="utf-8-sig")
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded)  # requer openpyxl (em requirements.txt)
    raise ValueError("Formato não suportado. Envie um arquivo .csv, .xlsx ou .xls.")


# ─────────────────────────────────── Validação ───────────────────────────────────


def validate_tasks(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Normaliza e valida Tarefas importadas.
    Retorna (df_tarefas_limpo, erros, avisos). Se houver erro, df vem vazio.
    """
    errors: list[str] = []
    warnings: list[str] = []

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing_required = [c for c in TASK_REQUIRED if c not in df.columns]
    if missing_required:
        errors.append("Colunas obrigatórias ausentes: " + ", ".join(missing_required))
        return pd.DataFrame(columns=TASK_COLUMNS), errors, warnings

    # Preenche colunas opcionais ausentes.
    for col, default in TASK_OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
            if col != "id_ativo":
                warnings.append(f"Coluna '{col}' ausente — preenchida com padrão.")

    # Coerção numérica (tolerante a formato BR).
    for col in _NUMERIC_FIELDS:
        df[col] = df[col].map(_num)

    before = len(df)
    df = df.dropna(subset=["nome_ativo", "tipo_ativo", "sistema", "subsistema",
                           "periodicidade_meses", "criticidade", "custo_base"])
    dropped = before - len(df)
    if dropped > 0:
        warnings.append(f"{dropped} linha(s) ignorada(s) por dados obrigatórios ausentes/inválidos.")

    if df.empty:
        errors.append("Nenhuma linha válida encontrada após a validação.")
        return pd.DataFrame(columns=TASK_COLUMNS), errors, warnings

    # Saneamento de faixas/tipos.
    df["criticidade"] = df["criticidade"].clip(0, 5).round().astype(int)
    df["periodicidade_meses"] = df["periodicidade_meses"].clip(lower=1).round().astype(int)
    df["idade_ativo"] = df["idade_ativo"].fillna(0).clip(lower=0).round().astype(int)
    df["fator_degradacao"] = df["fator_degradacao"].fillna(0.30).clip(0.0, 1.0).round(2)
    df["custo_base"] = df["custo_base"].clip(lower=0.0).round(2)

    # id_ativo: usa o informado ou deriva do nome.
    def _resolve_id(row):
        v = row.get("id_ativo")
        return str(v).strip() if pd.notna(v) and str(v).strip() else slugify_id(row["nome_ativo"])

    df["id_ativo"] = df.apply(_resolve_id, axis=1)
    df["observacao_tecnica"] = df["observacao_tecnica"].fillna("").astype(str)
    df["data_referencia"] = df["data_referencia"].fillna(REFERENCE_DATE).astype(str)

    return df[TASK_COLUMNS].reset_index(drop=True), errors, warnings


# ─────────────────────── Expansão de Tarefas no horizonte ─────────────────────────


def expand_tasks(df_tasks: pd.DataFrame) -> pd.DataFrame:
    """Expande cada Tarefa (1 linha) nos 10 anos do horizonte (10 linhas)."""
    if df_tasks is None or df_tasks.empty:
        return pd.DataFrame(columns=COLUMNS)

    rows: list[dict] = []
    for idx, t in enumerate(df_tasks.to_dict("records")):
        periodicidade = int(t["periodicidade_meses"]) or 12
        frequencia = round(12 / periodicidade, 2)
        criticidade = int(t["criticidade"])
        sistema = str(t["sistema"])
        subsistema = str(t["subsistema"])
        observacao = str(t.get("observacao_tecnica") or "").strip() or _note(sistema, subsistema, criticidade)
        id_ativo = str(t.get("id_ativo") or slugify_id(t["nome_ativo"]))

        for ano in range(1, HORIZON_YEARS + 1):
            rows.append({
                "id": f"{id_ativo}-{sistema}-X{idx}-A{ano}",
                "id_ativo": id_ativo,
                "tipo_ativo": str(t["tipo_ativo"]),
                "nome_ativo": str(t["nome_ativo"]),
                "sistema": sistema,
                "subsistema": subsistema,
                "tipo_os": str(t.get("tipo_os") or _os_type(criticidade)),
                "periodicidade_meses": periodicidade,
                "frequencia_prevista": frequencia,
                "horizonte_ano": ano,
                "criticidade": criticidade,
                "custo_base": float(t["custo_base"]),
                "data_referencia": str(t.get("data_referencia") or REFERENCE_DATE),
                "observacao_tecnica": observacao,
                "ambiente_exposicao": str(t.get("ambiente_exposicao") or "Externo"),
                "idade_ativo": int(t.get("idade_ativo") or 0),
                "fator_degradacao": float(t.get("fator_degradacao") or 0.30),
                "prioridade": _priority(criticidade),
                "impacto_operacional": _impact(criticidade),
            })
    return pd.DataFrame(rows, columns=COLUMNS)


# ─────────────────────────────── Montagem da base ────────────────────────────────


def assemble_base(example_df: pd.DataFrame | None, extra_tasks: pd.DataFrame | None) -> pd.DataFrame:
    """Concatena a base de exemplo (opcional) com as Tarefas importadas/manuais."""
    parts: list[pd.DataFrame] = []
    if example_df is not None and not example_df.empty:
        parts.append(example_df)
    if extra_tasks is not None and not extra_tasks.empty:
        parts.append(expand_tasks(extra_tasks))
    if not parts:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(parts, ignore_index=True)


def empty_tasks() -> pd.DataFrame:
    """DataFrame vazio com o esquema de Tarefas (para inicializar a sessão)."""
    return pd.DataFrame(columns=TASK_COLUMNS)


def records_to_tasks(df_records: pd.DataFrame) -> pd.DataFrame:
    """
    Colapsa a base no nível de registro/ano de volta ao nível de Tarefa
    (1 linha por id_ativo × sistema × subsistema). Usado para tornar a base de
    exemplo / baixada editável no app.
    """
    if df_records is None or df_records.empty:
        return empty_tasks()
    first = (
        df_records.sort_values("horizonte_ano")
        .groupby(["id_ativo", "sistema", "subsistema"], as_index=False)
        .first()
    )
    for col in TASK_COLUMNS:
        if col not in first.columns:
            first[col] = TASK_OPTIONAL_DEFAULTS.get(col, "")
    return first[TASK_COLUMNS].reset_index(drop=True)


def example_tasks() -> pd.DataFrame:
    """Base de exemplo já no nível de Tarefa (editável no app)."""
    return records_to_tasks(generate_mock_dataset())
