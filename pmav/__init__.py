"""
Simulador Analítico PMAV – VistoPred.

Pacote com a camada de dados, o núcleo analítico (puro, sem Streamlit) e a
camada de apresentação (UI/Plotly). Arquitetura:

    dados (catalog/scenarios/mock_data)
        → analytics (regression/simulation/aggregations)  [PURO]
            → ui (theme/components/charts)                 [Streamlit/Plotly]
"""

__version__ = "0.1.0"
__app_name__ = "Simulador Analítico PMAV – VistoPred"
