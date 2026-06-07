"""
Gerador da base de dados mockada do PMAV.

Produz um DataFrame na granularidade ativo × sistema × subsistema × ano (1..10).
Os atributos de "condição" (criticidade, periodicidade, custo_base, fator de
degradação...) são definidos UMA vez por subsistema e replicados ao longo dos 10
anos. O que varia por ano (custo ajustado, criticidade projetada) é calculado na
simulação de cenário.

Determinístico (numpy RandomState com seed) ⇒ a demonstração é sempre idêntica.

Integração futura: substitua generate_mock_dataset() por uma leitura de API/DB
que devolva um DataFrame com as mesmas colunas (ver COLUMNS).
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from .catalog import SYSTEM_META, SYSTEMS_BY_ASSET_TYPE

HORIZON_YEARS = 10
REFERENCE_DATE = "2026-01-01"
SUBSYSTEMS_PER_SYSTEM = 2  # mantém o volume de dados equilibrado
DEFAULT_SEED = 20260101

COLUMNS = [
    "id", "id_ativo", "tipo_ativo", "nome_ativo", "sistema", "subsistema", "tipo_os",
    "periodicidade_meses", "frequencia_prevista", "horizonte_ano", "criticidade",
    "custo_base", "data_referencia", "observacao_tecnica", "ambiente_exposicao",
    "idade_ativo", "fator_degradacao", "prioridade", "impacto_operacional",
]


class _AssetSeed(NamedTuple):
    id: str
    tipo: str
    nome: str
    idade: int
    ambiente: str


# Ativos-semente: variados em tipo, idade e ambiente.
ASSETS: list[_AssetSeed] = [
    _AssetSeed("ED-001", "Edificação", "Edifício Corporativo Atlântico", 12, "Externo"),
    _AssetSeed("PT-001", "Ponte", "Ponte Rio Verde", 28, "Litorâneo"),
    _AssetSeed("VD-001", "Viaduto", "Viaduto Leste", 18, "Externo"),
    _AssetSeed("TN-001", "Túnel", "Túnel Serra Azul", 9, "Industrial"),
    _AssetSeed("RD-001", "Rodovia", "Rodovia BR-Setor 7", 22, "Externo"),
    _AssetSeed("CT-001", "Contenção", "Contenção Talude Norte", 6, "Externo"),
]

# Pares (ativo, sistema) com criticidade 0 forçada — garantem ALERTAS IMEDIATOS na demo.
FORCED_IMMINENT: set[tuple[str, str]] = {
    ("PT-001", "Estrutural"),
    ("TN-001", "Incêndio"),
    ("ED-001", "Incêndio"),
}

# Ambientes mais agressivos aceleram a degradação.
ENV_DEGRADATION = {"Interno": 0.0, "Externo": 0.1, "Litorâneo": 0.25, "Industrial": 0.2}


def _pick(rs: np.random.RandomState, seq):
    return seq[int(rs.randint(len(seq)))]


def _pick_criticality(rs: np.random.RandomState, bias: float) -> int:
    noisy = bias + rs.uniform(-1.1, 1.4)
    return int(np.clip(round(noisy), 0, 5))


def _priority(c: int) -> str:
    if c <= 1:
        return "Crítica"
    if c == 2:
        return "Alta"
    if c == 3:
        return "Média"
    return "Baixa"


def _impact(c: int) -> str:
    if c <= 1:
        return "Alto"
    if c <= 3:
        return "Médio"
    return "Baixo"


def _os_type(c: int) -> str:
    """Natureza da O.S. inferida da criticidade base."""
    if c == 0:
        return "Corretiva"
    if c <= 3:
        return "Preventiva"
    return "Inspeção"


def _degradation(rs: np.random.RandomState, idade: int, ambiente: str) -> float:
    base = min(0.6, idade / 60)
    env = ENV_DEGRADATION.get(ambiente, 0.1)
    noise = rs.uniform(-0.05, 0.15)
    return round(float(np.clip(base + env + noise, 0.08, 0.95)), 2)


def _note(sistema: str, subsistema: str, c: int) -> str:
    if c == 0:
        return f"{subsistema} ({sistema}) em condição crítica — inspeção e intervenção imediatas."
    if c <= 2:
        return f"{subsistema} ({sistema}) requer monitoramento próximo e manutenção planejada."
    if c <= 3:
        return f"{subsistema} ({sistema}) em condição moderada; seguir periodicidade do PMAV."
    return f"{subsistema} ({sistema}) em boa condição; manutenção preventiva de rotina."


def generate_mock_dataset(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    """Gera a base completa de registros de manutenção (DataFrame)."""
    rs = np.random.RandomState(seed)
    rows: list[dict] = []

    for asset in ASSETS:
        for sistema in SYSTEMS_BY_ASSET_TYPE[asset.tipo]:
            meta = SYSTEM_META[sistema]
            subs = [str(s) for s in rs.permutation(meta.subsistemas)][:SUBSYSTEMS_PER_SYSTEM]

            for sub_index, subsistema in enumerate(subs):
                # Atributos de condição definidos UMA vez por subsistema.
                forced = sub_index == 0 and (asset.id, sistema) in FORCED_IMMINENT
                criticidade = 0 if forced else _pick_criticality(rs, meta.criticidade_bias)
                periodicidade = int(_pick(rs, meta.periodicidades))
                frequencia = round(12 / periodicidade, 2)  # intervenções/ano
                custo_base = float(round(rs.uniform(meta.custo_base_min, meta.custo_base_max) / 100) * 100)
                fator_degradacao = _degradation(rs, asset.idade, asset.ambiente)
                prioridade = _priority(criticidade)
                impacto = _impact(criticidade)
                observacao = _note(sistema, subsistema, criticidade)

                for ano in range(1, HORIZON_YEARS + 1):
                    rows.append({
                        "id": f"{asset.id}-{sistema}-{sub_index}-A{ano}",
                        "id_ativo": asset.id,
                        "tipo_ativo": asset.tipo,
                        "nome_ativo": asset.nome,
                        "sistema": sistema,
                        "subsistema": subsistema,
                        "tipo_os": _os_type(criticidade),
                        "periodicidade_meses": periodicidade,
                        "frequencia_prevista": frequencia,
                        "horizonte_ano": ano,
                        "criticidade": criticidade,
                        "custo_base": custo_base,
                        "data_referencia": REFERENCE_DATE,
                        "observacao_tecnica": observacao,
                        "ambiente_exposicao": asset.ambiente,
                        "idade_ativo": asset.idade,
                        "fator_degradacao": fator_degradacao,
                        "prioridade": prioridade,
                        "impacto_operacional": impacto,
                    })

    return pd.DataFrame(rows, columns=COLUMNS)


# Lista de ativos para filtros (id + nome + tipo).
MOCK_ASSETS = [{"id": a.id, "nome": a.nome, "tipo": a.tipo} for a in ASSETS]
