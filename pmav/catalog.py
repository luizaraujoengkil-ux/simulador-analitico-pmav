"""
Catálogo de domínio do PMAV.

Centraliza enums (tipos de ativo, sistemas, ambientes), a escala de criticidade,
os metadados de cada sistema (subsistemas, faixas de custo, periodicidades) e o
mapa de sistemas aplicáveis por tipo de ativo.

É a "fonte da verdade" do domínio: adicionar um sistema ou ajustar faixas de
custo é uma edição de uma única tabela.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


# ───────────────────────────────── Enums de domínio ──────────────────────────────


class AssetType(str, Enum):
    EDIFICACAO = "Edificação"
    PONTE = "Ponte"
    VIADUTO = "Viaduto"
    TUNEL = "Túnel"
    RODOVIA = "Rodovia"
    CONTENCAO = "Contenção"
    OUTRO = "Outro"


class SystemName(str, Enum):
    ESTRUTURAL = "Estrutural"
    ELETRICO = "Elétrico"
    HIDROSSANITARIO = "Hidrossanitário"
    INCENDIO = "Incêndio"
    ELETROMECANICO = "Eletromecânico"
    COBERTURA = "Cobertura"
    REVESTIMENTOS = "Revestimentos"
    IMPERMEABILIZACAO = "Impermeabilização"
    CLIMATIZACAO = "Climatização"
    SPDA = "SPDA"
    GAS = "Gás"
    DRENAGEM = "Drenagem"
    ESQUADRIAS = "Esquadrias"
    SEGURANCA = "Segurança"
    LAZER = "Lazer"


class ExposureEnvironment(str, Enum):
    INTERNO = "Interno"
    EXTERNO = "Externo"
    LITORANEO = "Litorâneo"
    INDUSTRIAL = "Industrial"


# Listas de strings prontas para uso em filtros / DataFrame.
ASSET_TYPES: list[str] = [e.value for e in AssetType]
SYSTEM_NAMES: list[str] = [e.value for e in SystemName]
EXPOSURE_ENVIRONMENTS: list[str] = [e.value for e in ExposureEnvironment]

# Tipos de Ordem de Serviço (O.S.) / natureza da Tarefa.
OS_TYPES: list[str] = ["Preventiva", "Corretiva", "Preditiva", "Inspeção"]


# ─────────────────────────────── Escala de criticidade ───────────────────────────


class CriticalityInfo(BaseModel):
    level: int
    label: str
    short: str
    color: str  # hex usado em badges/gráficos
    description: str
    imminent: bool  # gatilho de ALERTA IMEDIATO


CRITICALITY_LEVELS: list[int] = [0, 1, 2, 3, 4, 5]

CRITICALITY_SCALE: dict[int, CriticalityInfo] = {
    0: CriticalityInfo(level=0, label="Risco iminente", short="Iminente", color="#dc2626",
                       description="Condição crítica — exige intervenção imediata.", imminent=True),
    1: CriticalityInfo(level=1, label="Muito alta", short="Muito alta", color="#ea580c",
                       description="Criticidade muito alta.", imminent=False),
    2: CriticalityInfo(level=2, label="Alta", short="Alta", color="#f59e0b",
                       description="Criticidade alta.", imminent=False),
    3: CriticalityInfo(level=3, label="Moderada", short="Moderada", color="#eab308",
                       description="Criticidade moderada.", imminent=False),
    4: CriticalityInfo(level=4, label="Baixa", short="Baixa", color="#65a30d",
                       description="Criticidade baixa.", imminent=False),
    5: CriticalityInfo(level=5, label="Muito baixa", short="Muito baixa", color="#16a34a",
                       description="Condição mais favorável.", imminent=False),
}


def criticality_label(level: int) -> str:
    info = CRITICALITY_SCALE.get(int(level))
    return f"{level} — {info.label}" if info else str(level)


# ──────────────────────── Metadados de sistemas / subsistemas ─────────────────────


class SystemMeta(BaseModel):
    subsistemas: list[str]
    custo_base_min: float  # R$ por intervenção
    custo_base_max: float
    periodicidades: list[int]  # meses típicos entre intervenções
    criticidade_bias: float  # tendência de criticidade (menor = mais crítico)


# Faixas de custo e periodicidades realistas por sistema.
SYSTEM_META: dict[str, SystemMeta] = {
    "Estrutural": SystemMeta(subsistemas=["Vigas e pilares", "Lajes", "Fundações", "Juntas de dilatação"],
                             custo_base_min=18000, custo_base_max=92000, periodicidades=[12, 24, 36, 60], criticidade_bias=1.4),
    "Elétrico": SystemMeta(subsistemas=["Quadros de distribuição", "Subestação", "Iluminação", "Cabeamento"],
                           custo_base_min=8000, custo_base_max=46000, periodicidades=[6, 12, 24, 36], criticidade_bias=1.8),
    "Hidrossanitário": SystemMeta(subsistemas=["Reservatórios", "Tubulações", "Bombas de recalque", "Rede de esgoto"],
                                  custo_base_min=5000, custo_base_max=30000, periodicidades=[6, 12, 24], criticidade_bias=2.6),
    "Incêndio": SystemMeta(subsistemas=["Hidrantes", "Sprinklers", "Detecção e alarme", "Extintores"],
                           custo_base_min=6000, custo_base_max=36000, periodicidades=[3, 6, 12, 24], criticidade_bias=1.3),
    "Eletromecânico": SystemMeta(subsistemas=["Elevadores", "Escadas rolantes", "Portões automáticos", "Ventilação"],
                                 custo_base_min=12000, custo_base_max=72000, periodicidades=[3, 6, 12], criticidade_bias=2.0),
    "Cobertura": SystemMeta(subsistemas=["Telhamento", "Calhas e rufos", "Estrutura de cobertura"],
                            custo_base_min=7000, custo_base_max=42000, periodicidades=[12, 24, 36], criticidade_bias=2.8),
    "Revestimentos": SystemMeta(subsistemas=["Fachada", "Pisos", "Pintura", "Forros"],
                                custo_base_min=10000, custo_base_max=60000, periodicidades=[24, 36, 60], criticidade_bias=3.2),
    "Impermeabilização": SystemMeta(subsistemas=["Lajes expostas", "Áreas molhadas", "Subsolo", "Reservatórios"],
                                    custo_base_min=8000, custo_base_max=50000, periodicidades=[24, 36, 60], criticidade_bias=2.4),
    "Climatização": SystemMeta(subsistemas=["Chillers", "Fan-coils", "Dutos", "Splits"],
                               custo_base_min=9000, custo_base_max=56000, periodicidades=[3, 6, 12], criticidade_bias=2.7),
    "SPDA": SystemMeta(subsistemas=["Captação", "Descidas", "Aterramento"],
                       custo_base_min=3000, custo_base_max=15000, periodicidades=[12, 24], criticidade_bias=2.2),
    "Gás": SystemMeta(subsistemas=["Rede de distribuição", "Reguladores", "Detecção de vazamento"],
                      custo_base_min=4000, custo_base_max=22000, periodicidades=[6, 12, 24], criticidade_bias=1.6),
    "Drenagem": SystemMeta(subsistemas=["Galerias", "Bocas de lobo", "Bombas de drenagem"],
                           custo_base_min=5000, custo_base_max=28000, periodicidades=[6, 12, 24], criticidade_bias=2.5),
    "Esquadrias": SystemMeta(subsistemas=["Janelas", "Portas corta-fogo", "Fachada envidraçada"],
                             custo_base_min=4000, custo_base_max=26000, periodicidades=[24, 36, 60], criticidade_bias=3.6),
    "Segurança": SystemMeta(subsistemas=["CFTV", "Controle de acesso", "Alarmes"],
                            custo_base_min=5000, custo_base_max=25000, periodicidades=[6, 12, 24], criticidade_bias=3.0),
    "Lazer": SystemMeta(subsistemas=["Piscina", "Academia", "Playground"],
                        custo_base_min=3000, custo_base_max=18000, periodicidades=[12, 24, 36], criticidade_bias=4.0),
}


# ─────────────────────── Sistemas aplicáveis por tipo de ativo ────────────────────
# Reforça que o modelo é genérico (não só de edificações).
SYSTEMS_BY_ASSET_TYPE: dict[str, list[str]] = {
    "Edificação": SYSTEM_NAMES,
    "Ponte": ["Estrutural", "Impermeabilização", "Drenagem", "Revestimentos", "SPDA", "Segurança"],
    "Viaduto": ["Estrutural", "Impermeabilização", "Drenagem", "Revestimentos", "SPDA"],
    "Túnel": ["Estrutural", "Elétrico", "Incêndio", "Eletromecânico", "Climatização", "Drenagem", "Segurança", "Impermeabilização"],
    "Rodovia": ["Estrutural", "Drenagem", "Segurança", "Revestimentos"],
    "Contenção": ["Estrutural", "Drenagem", "Impermeabilização"],
    "Outro": ["Estrutural", "Elétrico", "Hidrossanitário", "Segurança"],
}
