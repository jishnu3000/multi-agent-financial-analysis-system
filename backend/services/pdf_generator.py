"""
PDF report generation.

Function:
    generate_pdf_report – render a markdown analyst report as a ReportLab PDF.
"""

import os
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def _escape(text: str) -> str:
    """Escape XML/HTML special characters for ReportLab ``Paragraph``."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _fmt_currency(val, decimals: int = 2) -> str:
    """Format a numeric value as a dollar string, or return 'N/A'."""
    if val is None:
        return "N/A"
    try:
        return f"${float(val):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_num(val, decimals: int = 2, suffix: str = "") -> str:
    """Format a number with optional suffix, or return 'N/A'."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_large(val) -> str:
    """Human-readable large number (B / M), or return 'N/A'."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if v >= 1_000_000_000:
            return f"${v / 1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"${v / 1_000_000:.2f}M"
        return f"${v:,.0f}"
    except (TypeError, ValueError):
        return "N/A"


def _build_metrics_table(
    stock_data: Dict[str, Any],
    fundamentals: Dict[str, Any],
    technical: Dict[str, Any],
    styles,
):
    """Build a two-column key-metrics table as a ReportLab ``Table``."""

    cell_style = ParagraphStyle(
        "MetricCell", parent=styles["Normal"], fontSize=9, leading=12
    )
    label_style = ParagraphStyle(
        "MetricLabel", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=colors.HexColor("#374151"),
    )

    def row(label: str, value: str):
        return [
            Paragraph(f"<b>{_escape(label)}</b>", label_style),
            Paragraph(_escape(str(value)), cell_style),
        ]

    # ── Price & market data ──────────────────────────────────────────────────
    current_price = stock_data.get("current_price")
    prev_close = stock_data.get("previous_close")
    price_change = stock_data.get("price_change", 0) or 0
    price_chg_pct = stock_data.get("price_change_pct", 0) or 0
    volume = stock_data.get("volume")
    high_52w = stock_data.get("high_52w")
    low_52w = stock_data.get("low_52w")

    # ── Fundamental data ────────────────────────────────────────────────────
    company = fundamentals.get("company_name", "N/A")
    sector = fundamentals.get("sector", "N/A")
    industry = fundamentals.get("industry", "N/A")
    mkt_cap = fundamentals.get("market_cap")
    pe = fundamentals.get("pe_ratio")
    fwd_pe = fundamentals.get("forward_pe")
    pb = fundamentals.get("price_to_book")
    div_yield = fundamentals.get("dividend_yield")
    beta = fundamentals.get("beta")
    avg_vol = fundamentals.get("avg_volume")

    # ── Technical data ───────────────────────────────────────────────────────
    sma50 = technical.get("sma_50")
    rsi14 = technical.get("rsi_14")
    trend = technical.get("trend", "N/A")
    t_strength = technical.get("trend_strength", 0)
    rsi_sig = technical.get("rsi_signal", "N/A")
    support = technical.get("support_level")
    resistance = technical.get("resistance_level")

    sign = "+" if price_change >= 0 else ""
    change_str = (
        f"{sign}{_fmt_currency(price_change)} ({sign}{_fmt_num(price_chg_pct, 2, '%')})"
        if current_price is not None else "N/A"
    )
    div_str = _fmt_num(div_yield * 100, 2, "%") if div_yield else "N/A"
    vol_str = f"{int(volume):,}" if volume else "N/A"
    avg_vol_str = f"{int(avg_vol):,}" if avg_vol else "N/A"

    data = [
        # section header row
        [Paragraph("<b>PRICE &amp; MARKET DATA</b>", label_style),
         Paragraph("<b>TECHNICAL INDICATORS</b>", label_style)],

        row("Current Price",    _fmt_currency(current_price)) +
        row("50-Day SMA",       _fmt_currency(sma50)),

        row("Previous Close",   _fmt_currency(prev_close)) +
        row("RSI (14)",         f"{_fmt_num(rsi14, 2)} – {rsi_sig}"),

        row("Price Change",     change_str) +
        row("Trend",
            f"{trend} ({_fmt_num(t_strength, 2, '%')} strength)"),

        row("52-Week High",     _fmt_currency(high_52w)) +
        row("Support Level",    _fmt_currency(support)),

        row("52-Week Low",      _fmt_currency(low_52w)) +
        row("Resistance Level", _fmt_currency(resistance)),

        row("Volume",           vol_str) +
        row("Avg Volume",       avg_vol_str),

        # blank separator
        [Paragraph("", cell_style), Paragraph("", cell_style),
         Paragraph("", cell_style), Paragraph("", cell_style)],

        # section header row
        [Paragraph("<b>FUNDAMENTAL DATA</b>", label_style),
         Paragraph("", cell_style),
         Paragraph("", cell_style),
         Paragraph("", cell_style)],

        row("Company",         company) +
        row("Sector",          sector),

        row("Industry",        industry) +
        row("Market Cap",      _fmt_large(mkt_cap)),

        row("P/E Ratio",       _fmt_num(pe, 2)) +
        row("Forward P/E",     _fmt_num(fwd_pe, 2)),

        row("Price/Book",      _fmt_num(pb, 2)) +
        row("Dividend Yield",  div_str),

        row("Beta",            _fmt_num(beta, 2)) +
        row("", ""),
    ]

    col_w = [1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch]
    tbl = Table(data, colWidths=col_w, repeatRows=0)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#1a237e")),
                ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
                ("BACKGROUND",  (0, 8), (-1, 8),  colors.HexColor("#1a237e")),
                ("TEXTCOLOR",   (0, 8), (-1, 8),  colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, 7),
                 [colors.HexColor("#f3f4f6"), colors.white]),
                ("ROWBACKGROUNDS", (0, 9), (-1, -1),
                 [colors.HexColor("#f3f4f6"), colors.white]),
                ("GRID",        (0, 0), (-1, -1),
                 0.25, colors.HexColor("#d1d5db")),
                ("TOPPADDING",  (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # span header labels across pairs
                ("SPAN", (0, 0), (1, 0)),
                ("SPAN", (2, 0), (3, 0)),
                ("SPAN", (0, 8), (3, 8)),
            ]
        )
    )
    return tbl


def generate_pdf_report(
    ticker: str,
    report_content: str,
    stock_data: Dict[str, Any],
    fundamentals: Dict[str, Any] = None,
    technical_analysis: Dict[str, Any] = None,
) -> str:
    """Render the markdown analyst report as a PDF using ReportLab Platypus.

    A structured "Key Metrics" table is inserted before the LLM narrative,
    pulling from *stock_data*, *fundamentals*, and *technical_analysis*.

    Handled markdown constructs:
    * ``#`` / ``##`` / ``###`` headings.
    * ``**bold**`` inline markup → ``<b>`` tags.
    * ``- `` / ``* `` list items → bullet paragraphs.
    * Plain text → Normal paragraphs.

    Output path: ``reports/stock_report_<TICKER>_<YYYYMMDD_HHMMSS>.pdf``

    Args:
        ticker:             Upper-case ticker symbol.
        report_content:     Full markdown text of the report.
        stock_data:         Raw OHLCV/summary dict from fetch_stock_data.
        fundamentals:       Dict from fetch_fundamentals.
        technical_analysis: Dict from calculate_technical_indicators.

    Returns:
        Relative path to the generated PDF file.

    Raises:
        Exception: If ReportLab fails to build the document.
    """
    fundamentals = fundamentals or {}
    technical_analysis = technical_analysis or {}
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_report_{ticker}_{timestamp}.pdf"
        filepath = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)

        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1a237e"),
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        story.append(
            Paragraph(
                f"Multi-Agent Financial Analysis System Report: {ticker}",
                title_style,
            )
        )
        story.append(Spacer(1, 0.2 * inch))
        story.append(
            Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * inch))

        # ── Key metrics section ──────────────────────────────────────────────
        story.append(
            Paragraph("Key Metrics", styles["Heading2"])
        )
        story.append(Spacer(1, 0.1 * inch))
        metrics_table = _build_metrics_table(
            stock_data, fundamentals, technical_analysis, styles
        )
        story.append(metrics_table)
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#1a237e")))
        story.append(Spacer(1, 0.2 * inch))
        story.append(
            Paragraph("Analyst Report", styles["Heading2"])
        )
        story.append(Spacer(1, 0.15 * inch))
        # ─────────────────────────────────────────────────────────────────────

        for line in report_content.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1 * inch))
                continue

            if line.startswith("### "):
                story.append(Paragraph(_escape(line[4:]), styles["Heading3"]))
            elif line.startswith("## "):
                story.append(Paragraph(_escape(line[3:]), styles["Heading2"]))
            elif line.startswith("# "):
                story.append(Paragraph(_escape(line[2:]), styles["Heading1"]))
            elif "**" in line:
                parts = line.split("**")
                formatted = "".join(
                    f"<b>{_escape(p)}</b>" if i % 2 == 1 else _escape(p)
                    for i, p in enumerate(parts)
                )
                story.append(Paragraph(formatted, styles["Normal"]))
            elif line.startswith("- ") or line.startswith("* "):
                story.append(
                    Paragraph(f"• {_escape(line[2:])}", styles["Normal"]))
            else:
                story.append(Paragraph(_escape(line), styles["Normal"]))

            story.append(Spacer(1, 0.1 * inch))

        doc.build(story)
        return filepath

    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")
