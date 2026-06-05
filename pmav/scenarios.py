"""
Cenários analíticos do PMAV.

Cada cenário é um conjunto de fatores que altera, de forma coerente, custo,
frequência, deterioração e a projeção de criticidade. Adicionar um cenário novo
é só acrescentar um item em SCENARIOS.
"""
from __future__ import annotations

from pydantic import BaseModel


class ScenarioFactors(BaseModel):
    custo: float            # multiplicador geral de custo
    custo_horizonte: float  # crescimento adicional de custo por ano de horizonte
    frequencia: float       # multiplicador da frequência prevista
    degradacao: float       # multiplicador da taxa de deterioração
    criticidade_shift: float  # deslocamento da criticidade projetada (− piora, + melhora)


class Scenario(BaseModel):
    id: str
    nome: str
    descricao: str
    accent: str  # cor de destaque (hex)
    factors: ScenarioFactors


SCENARIOS: list[Scenario] = [
    Scenario(id="base", nome="Base",
             descricao="Linha de base do PMAV, sem ajustes externos. Referência de comparação.",
             accent="#2670bd",
             factors=ScenarioFactors(custo=1.00, custo_horizonte=0.020, frequencia=1.00, degradacao=1.00, criticidade_shift=0.0)),
    Scenario(id="conservador", nome="Conservador",
             descricao="Margem de segurança em custos e frequência; postura cautelosa de planejamento.",
             accent="#0e7490",
             factors=ScenarioFactors(custo=1.08, custo_horizonte=0.025, frequencia=1.05, degradacao=1.05, criticidade_shift=-0.10)),
    Scenario(id="otimista", nome="Otimista",
             descricao="Condições favoráveis, boa execução do plano e menor deterioração.",
             accent="#16a34a",
             factors=ScenarioFactors(custo=0.92, custo_horizonte=0.015, frequencia=0.95, degradacao=0.90, criticidade_shift=0.20)),
    Scenario(id="agressivo", nome="Ambiente agressivo",
             descricao="Exposição severa (litorâneo/industrial): custos e deterioração elevados.",
             accent="#ea580c",
             factors=ScenarioFactors(custo=1.20, custo_horizonte=0.030, frequencia=1.10, degradacao=1.30, criticidade_shift=-0.40)),
    Scenario(id="restricao", nome="Restrição orçamentária",
             descricao="Manutenção adiada por restrição de verba — menos intervenções, mais risco acumulado.",
             accent="#9333ea",
             factors=ScenarioFactors(custo=0.85, custo_horizonte=0.020, frequencia=0.80, degradacao=1.25, criticidade_shift=-0.30)),
    Scenario(id="envelhecimento", nome="Envelhecimento acelerado",
             descricao="Ativo envelhecendo rápido: custo cresce no horizonte e criticidade tende ao nível 0.",
             accent="#dc2626",
             factors=ScenarioFactors(custo=1.10, custo_horizonte=0.050, frequencia=1.00, degradacao=1.50, criticidade_shift=-0.50)),
]

SCENARIO_BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}
SCENARIO_IDS: list[str] = [s.id for s in SCENARIOS]
SCENARIO_NAMES: dict[str, str] = {s.id: s.nome for s in SCENARIOS}


def get_scenario(scenario_id: str) -> Scenario:
    """Retorna o cenário pelo id (com fallback no cenário Base)."""
    return SCENARIO_BY_ID.get(scenario_id, SCENARIOS[0])
