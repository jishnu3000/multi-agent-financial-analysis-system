"""
PDF report generation.

Function:
    generate_pdf_report – render a markdown analyst report as a ReportLab PDF.
"""

import os
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _escape(text: str) -> str:
    """Escape XML/HTML special characters for ReportLab ``Paragraph``."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_pdf_report(
    ticker: str, report_content: str, stock_data: Dict[str, Any]
) -> str:
    """Render the markdown analyst report as a PDF using ReportLab Platypus.

    Handled markdown constructs:
    * ``#`` / ``##`` / ``###`` headings.
    * ``**bold**`` inline markup → ``<b>`` tags.
    * ``- `` / ``* `` list items → bullet paragraphs.
    * Plain text → Normal paragraphs.

    Output path: ``reports/stock_report_<TICKER>_<YYYYMMDD_HHMMSS>.pdf``

    Args:
        ticker:         Upper-case ticker symbol.
        report_content: Full markdown text of the report.
        stock_data:     Raw stock data dict (reserved for future chart embedding).

    Returns:
        Relative path to the generated PDF file.

    Raises:
        Exception: If ReportLab fails to build the document.
    """
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
