"""
Cliente de integração com o App VistoPred (download por código de edificação).

Estado atual: a CONEXÃO REAL é um ponto de extensão (placeholder). Enquanto a API
não está configurada (via st.secrets['vistopred']), o cliente devolve dados de
DEMONSTRAÇÃO determinísticos para o código informado — permitindo exercitar todo
o fluxo (baixar → editar → simular) de forma honesta.

Quando a API estiver disponível, implemente a chamada real em `_fetch_real` (ex.:
requests/httpx para `{base_url}/edificacoes/{codigo}/tarefas` com a api_key) e
mapeie a resposta para as colunas de TASK_COLUMNS.

Módulo PURO (sem Streamlit): a configuração é passada como dicionário.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .catalog import SYSTEM_META
from .data_source import TASK_COLUMNS
from .mock_data import REFERENCE_DATE, _os_type

# Sistemas usados na demonstração de uma edificação.
_DEMO_SYSTEMS = ["Estrutural", "Elétrico", "Incêndio", "Hidrossanitário", "Climatização", "Cobertura"]


def is_configured(config: dict | None) -> bool:
    """Há configuração suficiente para uma conexão real?"""
    return bool(config and config.get("base_url") and config.get("api_key"))


def _seed_from_code(codigo: str) -> int:
    """Seed determinística derivada do código (sem depender de hash() aleatório)."""
    s = str(codigo)
    val = sum(ord(c) * (i + 1) for i, c in enumerate(s))
    return (val % (2**32 - 1)) or 1


def _demo_tasks(codigo: str) -> pd.DataFrame:
    """Gera Tarefas determinísticas para uma edificação fictícia do código."""
    rs = np.random.RandomState(_seed_from_code(codigo))
    nome = f"Edificação {str(codigo).strip()}"
    id_ativo = f"VP-{str(codigo).strip()}"
    idade = int(rs.randint(5, 35))
    ambiente = ["Externo", "Litorâneo", "Industrial", "Interno"][rs.randint(4)]

    rows = []
    for sistema in _DEMO_SYSTEMS:
        meta = SYSTEM_META[sistema]
        subsistema = str(meta.subsistemas[rs.randint(len(meta.subsistemas))])
        criticidade = int(np.clip(round(meta.criticidade_bias + rs.uniform(-1.0, 1.2)), 0, 5))
        periodicidade = int(meta.periodicidades[rs.randint(len(meta.periodicidades))])
        custo_base = float(round(rs.uniform(meta.custo_base_min, meta.custo_base_max) / 100) * 100)
        fator = round(float(np.clip(idade / 60 + rs.uniform(-0.05, 0.2), 0.08, 0.95)), 2)
        rows.append({
            "id_ativo": id_ativo, "tipo_ativo": "Edificação", "nome_ativo": nome,
            "sistema": sistema, "subsistema": subsistema, "tipo_os": _os_type(criticidade),
            "periodicidade_meses": periodicidade, "criticidade": criticidade, "custo_base": custo_base,
            "ambiente_exposicao": ambiente, "idade_ativo": idade, "fator_degradacao": fator,
            "data_referencia": REFERENCE_DATE,
            "observacao_tecnica": f"Importado do VistoPred (código {codigo}).",
        })
    return pd.DataFrame(rows, columns=TASK_COLUMNS)


def _fetch_real(codigo: str, config: dict) -> pd.DataFrame:
    """
    PONTO DE EXTENSÃO — integração real com a API do VistoPred.

    Exemplo de implementação futura:
        import requests
        url = f"{config['base_url']}/edificacoes/{codigo}/tarefas"
        resp = requests.get(url, headers={"Authorization": f"Bearer {config['api_key']}"}, timeout=30)
        resp.raise_for_status()
        df = pd.json_normalize(resp.json())
        # mapear df.columns -> TASK_COLUMNS e devolver validate_tasks(df)[0]
    """
    raise NotImplementedError(
        "Integração real com a API VistoPred ainda não implementada neste ambiente. "
        "Implemente pmav.vistopred_client._fetch_real e configure st.secrets['vistopred']."
    )


def fetch_tasks(codigo: str, config: dict | None = None) -> tuple[pd.DataFrame, str]:
    """
    Baixa as Tarefas de uma edificação pelo código.
    Retorna (df_tarefas, mensagem). Usa a API real se configurada; senão, demonstração.
    """
    if not str(codigo).strip():
        raise ValueError("Informe o código da edificação para baixar os dados.")

    if is_configured(config):
        df = _fetch_real(codigo, config)  # pode levantar NotImplementedError até a integração existir
        return df, f"Dados baixados do VistoPred para o código {codigo}."

    return (
        _demo_tasks(codigo),
        "Conexão real não configurada — exibindo dados de DEMONSTRAÇÃO para o código informado. "
        "Configure st.secrets['vistopred'] (base_url, api_key) para conectar de verdade.",
    )
