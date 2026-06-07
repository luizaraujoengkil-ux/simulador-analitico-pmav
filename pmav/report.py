"""
Geração de relatórios PDF (reportlab + matplotlib).

Dois relatórios:
  - build_simulation_report : "foto" da simulação atual (cenário + filtros).
  - build_full_report       : consolidado dos 6 cenários (apoio à decisão).

Módulo PURO (sem Streamlit): recebe DataFrames já simulados e devolve os bytes do
PDF. Sem acesso a disco — ideal para o Streamlit Community Cloud.
"""
from __future__ import annotations

import io
import re
from math import ceil
from xml.sax.saxutils import escape as xml_escape

import matplotlib
matplotlib.use("Agg")  # backend headless (servidor sem tela)
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import aggregations as agg
from .formatting import format_brl, format_number, format_percent
from .scenarios import Scenario

# Paleta VistoPred (reportlab).
BRAND = colors.HexColor("#0f2c50")
PETROLEO = colors.HexColor("#0e4d5c")
CIANO = colors.HexColor("#0891b2")
LIGHT = colors.HexColor("#f1f5f9")
LINE = colors.HexColor("#e2e8f0")
GREY = colors.HexColor("#64748b")

AUTHOR_LINE = ("Desenvolvido por Luiz Araujo · luiz.junior@ime.eb.br · "
               "IME — Instituto Militar de Engenharia")
DISCLAIMER = "Dados simulados para fins analíticos · modelo de regressão linear múltipla (OLS)."


# ─────────────────────────────────── Estilos / utils ─────────────────────────────


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("VPEyebrow", parent=ss["Normal"], fontSize=8, textColor=CIANO,
                          spaceAfter=2, leading=10))
    ss.add(ParagraphStyle("VPTitle", parent=ss["Title"], textColor=BRAND, fontSize=20,
                          spaceAfter=2, leading=24))
    ss.add(ParagraphStyle("VPSub", parent=ss["Normal"], textColor=GREY, fontSize=10, spaceAfter=2))
    ss.add(ParagraphStyle("VPH2", parent=ss["Heading2"], textColor=PETROLEO, fontSize=13,
                          spaceBefore=12, spaceAfter=5, leading=15))
    ss.add(ParagraphStyle("VPBody", parent=ss["Normal"], fontSize=9.5, leading=13, spaceAfter=4))
    ss.add(ParagraphStyle("VPSmall", parent=ss["Normal"], fontSize=8, textColor=GREY, leading=10))
    return ss


def _rich(text: str) -> str:
    """Escapa XML e converte **negrito** (markdown) em <b> para o reportlab."""
    t = xml_escape(str(text))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.1 * cm, AUTHOR_LINE)
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.4 * cm, A4[0] - 2 * cm, 1.4 * cm)
    canvas.restoreState()


def _table(data, col_widths=None, align_right_from=1):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if align_right_from is not None:
        style.append(("ALIGN", (align_right_from, 1), (-1, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


# ─────────────────────────────── Gráficos (matplotlib) ───────────────────────────


def _ax(ax, grid="x"):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7.5, colors="#334155")
    if grid in ("x", "both"):
        ax.grid(axis="x", color="#e2e8f0", linewidth=0.5)
    if grid in ("y", "both"):
        ax.grid(axis="y", color="#e2e8f0", linewidth=0.5)
    ax.set_axisbelow(True)


def _fig_image(fig, width_cm=16.0):
    fw, fh = fig.get_size_inches()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)
    w = width_cm * cm
    return RLImage(buf, width=w, height=w * (fh / fw))


def _fig_cost_by_system(df):
    d = agg.cost_by_system(df).sort_values("custo_previsto").tail(12)
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    ax.barh(d["sistema"], d["custo_previsto"], color="#174680")
    ax.ticklabel_format(style="plain", axis="x")
    ax.set_title("Custo previsto por sistema (R$)", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "x")
    fig.tight_layout()
    return fig


def _fig_alerts_by_system(df):
    d = agg.alerts_by_system(df)
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    if not d.empty:
        ax.bar(d["sistema"], d["Imediato"], color="#dc2626", label="Imediato")
        ax.bar(d["sistema"], d["Preditivo"], bottom=d["Imediato"], color="#d97706", label="Preditivo")
        ax.legend(fontsize=8, frameon=False)
        plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=7)
    ax.set_title("Alertas por sistema", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "y")
    fig.tight_layout()
    return fig


def _fig_coefficients(model):
    keys = ["periodicidade_meses", "criticidade", "frequencia_prevista", "horizonte_ano"]
    labels = ["β₁ Periodicidade", "β₂ Criticidade", "β₃ Frequência", "β₄ Horizonte"]
    vals = [float(model.coefficients[k]) for k in keys]
    cols = ["#dc2626" if v < 0 else "#0891b2" for v in vals]
    fig, ax = plt.subplots(figsize=(7.4, 2.6))
    ax.barh(labels, vals, color=cols)
    ax.axvline(0, color="#64748b", linewidth=0.8)
    ax.ticklabel_format(style="plain", axis="x")
    ax.set_title("Coeficientes do modelo (β)", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "x")
    fig.tight_layout()
    return fig


def _fig_fit_scatter(df):
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    if not df.empty:
        x = df["custo_ajustado"]
        y = df["custo_previsto"]
        ax.scatter(x, y, s=12, color="#174680", alpha=0.45, edgecolors="none")
        lo = float(min(x.min(), y.min()))
        hi = float(max(x.max(), y.max()))
        ax.plot([lo, hi], [lo, hi], "--", color="#dc2626", linewidth=1.4, label="45° (perfeito)")
        ax.legend(fontsize=8, frameon=False)
        ax.ticklabel_format(style="plain", axis="both")
    ax.set_xlabel("Custo ajustado (R$)", fontsize=8)
    ax.set_ylabel("Custo previsto (R$)", fontsize=8)
    ax.set_title("Qualidade do ajuste", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "both")
    fig.tight_layout()
    return fig


def _fig_cost_by_scenario(df_all):
    d = agg.cost_by_scenario(df_all)
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.bar(d["nome"], d["custo_total_previsto"], color="#174680")
    ax.ticklabel_format(style="plain", axis="y")
    plt.setp(ax.get_xticklabels(), rotation=22, ha="right", fontsize=7)
    ax.set_title("Custo total previsto por cenário (R$)", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "y")
    fig.tight_layout()
    return fig


def _fig_alerts_by_scenario(df_all, scenarios):
    rows = []
    for s in scenarios:
        d = df_all[df_all["cenario"] == s.id]
        rows.append((s.nome, int((d["status_alerta"] == "Imediato").sum()),
                     int((d["status_alerta"] == "Preditivo").sum())))
    dd = pd.DataFrame(rows, columns=["nome", "Imediato", "Preditivo"])
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    ax.bar(dd["nome"], dd["Imediato"], color="#dc2626", label="Imediato")
    ax.bar(dd["nome"], dd["Preditivo"], bottom=dd["Imediato"], color="#d97706", label="Preditivo")
    ax.legend(fontsize=8, frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=22, ha="right", fontsize=7)
    ax.set_title("Alertas por cenário", fontsize=10, color="#0f2c50", loc="left")
    _ax(ax, "y")
    fig.tight_layout()
    return fig


# ─────────────────────────────── Blocos reutilizáveis ────────────────────────────


def _header(story, ss, titulo, subtitulo, generated_at, filtros_txt):
    story.append(Paragraph("VISTOPRED · SIMULADOR ANALÍTICO PMAV", ss["VPEyebrow"]))
    story.append(Paragraph(titulo, ss["VPTitle"]))
    story.append(Paragraph(subtitulo, ss["VPSub"]))
    story.append(Paragraph(f"Gerado em {generated_at}", ss["VPSmall"]))
    if filtros_txt:
        story.append(Paragraph(f"Filtros aplicados: {filtros_txt}", ss["VPSmall"]))
    story.append(Spacer(1, 8))


def _kpi_table(kpis):
    rows = [
        ["Indicador", "Valor"],
        ["Custo total previsto", format_brl(kpis["custo_total_previsto"])],
        ["Custo total ajustado", format_brl(kpis["custo_total_ajustado"])],
        ["Sistemas avaliados", format_number(kpis["n_sistemas"])],
        ["Ativos", format_number(kpis["n_ativos"])],
        ["Registros", format_number(kpis["n_registros"])],
        ["Alertas imediatos", format_number(kpis["alertas_imediatos"])],
        ["Alertas preditivos", format_number(kpis["alertas_preditivos"])],
        ["Sistema mais crítico", str(kpis["sistema_mais_critico"])],
        ["Maior custo previsto", str(kpis["sistema_maior_custo"])],
    ]
    return _table(rows, col_widths=[9 * cm, 7.5 * cm])


def _model_table(model):
    c = model.coefficients
    rows = [
        ["Modelo", "Valor"],
        ["Intercepto (b0)", format_number(c["intercept"], 2)],
        ["Periodicidade (b1)", format_number(c["periodicidade_meses"], 2)],
        ["Criticidade (b2)", format_number(c["criticidade"], 2)],
        ["Frequência (b3)", format_number(c["frequencia_prevista"], 2)],
        ["Horizonte (b4)", format_number(c["horizonte_ano"], 2)],
        ["R²", format_percent(model.r2)],
        ["RMSE", format_brl(model.rmse)],
        ["Observações (n)", format_number(model.n)],
        ["Motor", model.engine],
    ]
    return _table(rows, col_widths=[9 * cm, 7.5 * cm])


def _ranking_table(df, limit=12):
    r = agg.system_ranking(df).head(limit)
    rows = [["Sistema", "Custo previsto", "Crit. média", "Alertas", "Score"]]
    for _, x in r.iterrows():
        rows.append([str(x["sistema"]), format_brl(x["custo_previsto"]),
                     format_number(x["criticidade_media"], 2), format_number(x["alertas"]),
                     format_number(x["score"], 2)])
    return _table(rows, col_widths=[5.5 * cm, 4 * cm, 2.6 * cm, 2.2 * cm, 2.2 * cm])


def _alerts_table(df, limit=15):
    a = df[df["status_alerta"] != "Normal"].copy()
    if a.empty:
        return None, 0
    a["_o"] = a["status_alerta"].map({"Imediato": 0, "Preditivo": 1})
    a = a.sort_values(["_o", "criticidade_projetada"]).head(limit)
    rows = [["Tipo", "Sistema · Subsistema", "Ativo", "Ano", "Ação sugerida"]]
    for x in a.itertuples(index=False):
        rows.append([x.status_alerta, f"{x.sistema} · {x.subsistema}", x.nome_ativo,
                     str(x.horizonte_ano), x.acao_sugerida])
    return _table(rows, col_widths=[1.8 * cm, 4.6 * cm, 3.6 * cm, 1.1 * cm, 5.4 * cm], align_right_from=None), len(a)


# ─────────────────────────── Relatório da simulação atual ─────────────────────────


def build_simulation_report(df, scenario: Scenario, kpis, model, filtros_txt, generated_at) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.8 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            title="Relatório de Simulação PMAV", author="VistoPred")
    ss = _styles()
    story = []
    _header(story, ss, "Relatório de Simulação",
            f"Cenário: {scenario.nome}", generated_at, filtros_txt)

    story.append(Paragraph("Resumo executivo", ss["VPH2"]))
    story.append(Paragraph(_rich(agg.executive_summary(df, scenario, kpis)), ss["VPBody"]))

    story.append(Paragraph("Indicadores (KPIs)", ss["VPH2"]))
    story.append(_kpi_table(kpis))

    story.append(Paragraph("Custo e alertas por sistema", ss["VPH2"]))
    story.append(_fig_image(_fig_cost_by_system(df)))
    story.append(_fig_image(_fig_alerts_by_system(df)))

    story.append(Paragraph("Ranking de sistemas prioritários", ss["VPH2"]))
    story.append(_ranking_table(df))

    alerts_tbl, n_alerts = _alerts_table(df)
    if alerts_tbl is not None:
        story.append(Paragraph(f"Alertas (top {n_alerts})", ss["VPH2"]))
        story.append(alerts_tbl)

    story.append(Paragraph("Modelo estatístico", ss["VPH2"]))
    story.append(_model_table(model))
    story.append(Spacer(1, 4))
    story.append(_fig_image(_fig_coefficients(model), width_cm=10))
    story.append(_fig_image(_fig_fit_scatter(df), width_cm=10))

    story.append(Spacer(1, 6))
    story.append(Paragraph(DISCLAIMER, ss["VPSmall"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ─────────────────────── Relatório completo (Simulação Total) ─────────────────────


def _comparativo(df_all, models, scenarios):
    rows = [["Cenário", "Custo previsto", "Imediatos", "Preditivos", "R²"]]
    dados = []
    for s in scenarios:
        d = df_all[df_all["cenario"] == s.id]
        custo = float(d["custo_previsto"].sum())
        imed = int((d["status_alerta"] == "Imediato").sum())
        pred = int((d["status_alerta"] == "Preditivo").sum())
        r2 = models[s.id].r2 if s.id in models else 0.0
        rows.append([s.nome, format_brl(custo), format_number(imed), format_number(pred),
                     format_percent(r2)])
        dados.append({"id": s.id, "nome": s.nome, "custo": custo, "imediatos": imed, "preditivos": pred})
    return _table(rows, col_widths=[5.5 * cm, 4.2 * cm, 2.4 * cm, 2.4 * cm, 2 * cm]), dados


def _robustez(df_all, scenarios):
    """Sistemas com alerta em vários cenários (prioridade 'à prova de cenário')."""
    contagem = {}
    for s in scenarios:
        d = df_all[df_all["cenario"] == s.id]
        sistemas = d[d["status_alerta"] != "Normal"]["sistema"].unique()
        for sis in sistemas:
            contagem[sis] = contagem.get(sis, 0) + 1
    limiar = ceil(len(scenarios) / 2)
    robustos = sorted([(s, n) for s, n in contagem.items() if n >= limiar],
                      key=lambda x: -x[1])
    return robustos, limiar


def build_full_report(df_all, models, scenarios, filtros_txt, generated_at) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.8 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            title="Relatório Completo PMAV — Simulação Total", author="VistoPred")
    ss = _styles()
    story = []
    _header(story, ss, "Simulação Total — Relatório Completo",
            "Comparativo dos cenários para apoio à decisão", generated_at, filtros_txt)

    comp_tbl, dados = _comparativo(df_all, models, scenarios)
    story.append(Paragraph("Comparativo entre cenários", ss["VPH2"]))
    story.append(comp_tbl)

    story.append(Paragraph("Visão gráfica", ss["VPH2"]))
    story.append(_fig_image(_fig_cost_by_scenario(df_all)))
    story.append(_fig_image(_fig_alerts_by_scenario(df_all, scenarios)))

    # Faixa de custo e robustez
    custos = [d["custo"] for d in dados] or [0.0]
    menor = min(dados, key=lambda d: d["custo"]) if dados else {"nome": "—", "custo": 0}
    maior = max(dados, key=lambda d: d["custo"]) if dados else {"nome": "—", "custo": 0}
    robustos, limiar = _robustez(df_all, scenarios)

    story.append(Paragraph("Faixa de custo e robustez", ss["VPH2"]))
    faixa = (f"O custo total previsto varia de <b>{format_brl(menor['custo'])}</b> "
             f"(cenário {menor['nome']}) a <b>{format_brl(maior['custo'])}</b> "
             f"(cenário {maior['nome']}) — uma diferença de "
             f"<b>{format_brl(maior['custo'] - menor['custo'])}</b> entre o melhor e o pior caso.")
    story.append(Paragraph(faixa, ss["VPBody"]))
    if robustos:
        lst = ", ".join(f"{s} ({n}/{len(scenarios)} cenários)" for s, n in robustos[:8])
        story.append(Paragraph(
            f"<b>Sistemas críticos em múltiplos cenários</b> (alerta em ≥ {limiar} dos "
            f"{len(scenarios)}): {lst}. São prioridades <b>robustas</b> — merecem ação "
            "independentemente do cenário que se concretize.", ss["VPBody"]))
    else:
        story.append(Paragraph("Nenhum sistema apresentou alertas recorrentes entre os cenários.",
                               ss["VPBody"]))

    # Recomendação consolidada
    story.append(Paragraph("Recomendação ao profissional de manutenção", ss["VPH2"]))
    total_imed = sum(d["imediatos"] for d in dados)
    rec = []
    if total_imed > 0:
        rec.append("Priorizar a correção dos pontos de <b>criticidade 0 (risco iminente)</b>, "
                   "presentes já no cenário Base.")
    if robustos:
        rec.append("Programar manutenção preventiva nos <b>sistemas críticos recorrentes</b> "
                   "listados acima, por serem robustos a diferentes cenários.")
    rec.append("Usar a <b>faixa de custo</b> entre cenários para dimensionar o orçamento "
               "(provisão para o cenário severo, meta no cenário Base).")
    rec.append("Reavaliar periodicidades do PMAV onde a criticidade projetada se aproxima de 0 "
               "(alertas preditivos).")
    for r in rec:
        story.append(Paragraph("• " + r, ss["VPBody"]))

    story.append(Spacer(1, 6))
    story.append(Paragraph(DISCLAIMER, ss["VPSmall"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
