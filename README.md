<div align="center">

# 🛠️ Simulador Analítico PMAV — VistoPred

**Previsão de custos, cenários e apoio à decisão em manutenção preventiva de ativos.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://simulador-analitico-pmav.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-0891b2.svg)](LICENSE)

Módulo analítico complementar ao **PMAV (Plano de Manutenção Avançado)** e à lógica do **VistoPred**.

</div>

---

## 📌 Visão geral

O **Simulador Analítico PMAV** é um aplicativo web (Streamlit) que demonstra como dados estruturados de manutenção preventiva podem apoiar a **previsão de custos**, a **comparação de cenários**, a **priorização de sistemas** e a **geração de alertas** — fazendo a transição conceitual da manutenção **preventiva** para a **preditiva**.

O motor estatístico usa **regressão linear múltipla (OLS)** para estimar o custo de manutenção em um horizonte de **10 anos**, considerando periodicidade, criticidade, frequência e horizonte de intervenção.

> 🔗 **App online:** `https://simulador-analitico-pmav.streamlit.app` *(atualize após o deploy)*

---

## ✨ Funcionalidades

- 🎚️ **Filtros interativos** — tipo de ativo, sistema, subsistema, cenário, criticidade e horizonte (ano 1–10).
- 🧮 **6 cenários analíticos** — Base, Conservador, Otimista, Ambiente agressivo, Restrição orçamentária, Envelhecimento acelerado.
- 📈 **Modelo de regressão linear múltipla (OLS)** com R², RMSE e coeficientes transparentes (modo OLS ↔ coeficientes mockados).
- 🟦 **Cards-resumo (KPIs)** — custo previsto, custo ajustado, sistemas avaliados, alertas e sistemas críticos/caros.
- 📊 **Gráficos analíticos**:
  - Custo total previsto por cenário
  - Custo previsto por sistema
  - Custo ajustado vs. custo previsto
  - Distribuição de alertas por sistema
  - Custo previsto + criticidade média projetada (eixo duplo)
- 🚨 **Painel de alertas** — imediatos (criticidade 0) e preditivos (tendência de deterioração), com motivo, impacto e ação sugerida.
- 🏆 **Ranking de sistemas prioritários** por score composto (custo + criticidade + alertas).
- 📋 **Tabela analítica detalhada** com **exportação CSV**.
- 📝 **Resumo executivo automático** coerente com os filtros e o cenário.
- 🎨 **Identidade visual VistoPred** (azul escuro, petróleo, ciano/teal) — cara de produto, não Streamlit genérico.

---

## 🧠 Lógica analítica

Modelo de **regressão linear múltipla**:

```
Custo_i = β0 + β1·Periodicidade_i + β2·Criticidade_i + β3·Frequência_i + β4·Horizonte_i + ε_i
```

- Coeficientes **estimados por OLS** (`statsmodels`), com fallback transparente em `numpy.linalg.lstsq`.
- **Custo ajustado** (cenário) × **custo previsto** (modelo) → resíduo e qualidade do ajuste (R²/RMSE).

**Escala de criticidade**

| Nível | Significado | Efeito |
|:---:|---|---|
| **0** | Risco iminente | 🔴 **Alerta imediato** |
| 1 | Muito alta | — |
| 2 | Alta | — |
| 3 | Moderada | — |
| 4 | Baixa | — |
| 5 | Muito baixa | condição mais favorável |

Quando a **criticidade projetada** tende ao nível 0 ao longo do horizonte, o sistema gera um 🟠 **alerta preditivo**.

---

## 🏗️ Arquitetura

Separação rígida em camadas — o núcleo analítico é **puro** (não importa Streamlit), o que o torna testável e portável para um backend.

```
dados  →  pmav/analytics (puro)  →  pmav/ui (Streamlit + Plotly)
```

```
simulador-analitico-pmav/
├── streamlit_app.py            # ponto de entrada (orquestrador do dashboard)
├── requirements.txt
├── README.md  ·  LICENSE  ·  .gitignore
├── .streamlit/
│   ├── config.toml             # tema VistoPred
│   └── secrets.toml.example    # modelo de secrets (o real não é versionado)
├── assets/
│   └── vistopred_logo.svg
└── pmav/                       # pacote Python
    ├── catalog.py              # enums, criticidade, sistemas/subsistemas
    ├── scenarios.py            # 6 cenários e seus fatores
    ├── mock_data.py            # gerador determinístico (DataFrame)
    ├── regression.py           # regressão linear múltipla (OLS)        ⟵ puro
    ├── simulation.py           # cenários + alertas + orquestração       ⟵ puro
    ├── aggregations.py         # KPIs, rankings, séries, resumo          ⟵ puro
    ├── formatting.py           # formatação pt-BR                        ⟵ puro
    ├── theme.py                # CSS/paleta VistoPred                    ⟵ UI
    ├── components.py           # header, cards, badges, alertas          ⟵ UI
    └── charts.py               # gráficos Plotly                         ⟵ UI
```

**Fluxo:** `mock_data` → `simulation.run` (aplica cenário + ajusta OLS + classifica alertas) → filtros → `aggregations` → `components`/`charts`.

---

## 🧰 Tecnologias

| Camada | Stack |
|---|---|
| App / UI | **Streamlit** |
| Dados | **pandas**, **numpy** |
| Modelo | **statsmodels** (OLS) · fallback **numpy** |
| Contratos | **pydantic**, typing |
| Gráficos | **Plotly** |
| Utilidades | pathlib, typing (stdlib) |

---

## 💻 Instalação e execução local

> Requer **Python 3.11+**.

```bash
# 1. Clonar o repositório
git clone https://github.com/<seu-usuario>/simulador-analitico-pmav.git
cd simulador-analitico-pmav

# 2. Criar e ativar um ambiente virtual
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Rodar o app
streamlit run streamlit_app.py
```

O app abre em `http://localhost:8501`.

---

## ☁️ Deploy no Streamlit Community Cloud

1. Faça o **push** do projeto para um repositório **público** no GitHub.
2. Acesse **[share.streamlit.io](https://share.streamlit.io)** e clique em **“New app”**.
3. Selecione o repositório, a branch **`main`** e o arquivo principal **`streamlit_app.py`**.
4. Em **Advanced settings**, escolha **Python 3.11**.
5. Clique em **Deploy**. A cada `git push` na branch `main`, o app **atualiza automaticamente**.

> Não é necessário `runtime.txt`. As dependências são lidas do `requirements.txt` na raiz.
> A v1 **não usa secrets** (dados mockados). Para integrações futuras, use o painel de *Secrets* do app + `st.secrets`.

---

## 🗺️ Roadmap

- [ ] Integração com dados reais da VistoPred (API/DB) substituindo `mock_data.py`.
- [ ] Modelos preditivos de degradação (scikit-learn / séries temporais).
- [ ] Intervalos de confiança e diagnóstico de resíduos no painel do modelo.
- [ ] Exportação de relatório executivo em PDF.
- [ ] Multi-ativo comparativo e *benchmark* entre carteiras.
- [ ] Autenticação e perfis de acesso.
- [ ] Testes automatizados (pytest) sobre a camada analítica pura.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE).

---

<div align="center">

**VistoPred** · Simulador Analítico PMAV · módulo analítico de manutenção preventiva de ativos

</div>
