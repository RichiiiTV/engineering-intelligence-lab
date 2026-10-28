"""Regenerate the owned M3 golden PDF with ReportLab (authoring only)."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

root = Path(__file__).resolve().parents[2]
path = root / "output/pdf/synthetic-maintenance-note.pdf"
path.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
c.setTitle("Synthetic inspection maintenance note - EIL golden fixture")
c.setAuthor("Engineering Intelligence Lab - generated demo data")
width, height = A4


def header(title, page):
    c.setFillColor(colors.HexColor("#17324d"))
    c.rect(0, height - 118, width, 118, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(44, height - 64, title)
    c.setFont("Helvetica", 10)
    c.drawString(44, height - 88, "ENGINEERING INTELLIGENCE LAB | SYNTHETIC DEMO EVIDENCE")
    c.setFillColor(colors.HexColor("#506070"))
    c.setFont("Helvetica", 9)
    c.drawString(44, 38, "Generated fixture. No company data. Not an operational instruction.")
    c.drawRightString(width - 44, 38, f"Page {page} of 2")


header("Inspection maintenance note", 1)
c.setFillColor(colors.HexColor("#17324d"))
c.setFont("Helvetica-Bold", 14)
c.drawString(44, height - 165, "Scope and record identity")
c.setFont("Helvetica", 11)
for index, line in enumerate(
    [
        "Record: DEMO-MNT-2026-010. Revision 1. Generated for M3 testing.",
        "This note is fictional evidence for a synthetic inspection investigation.",
        "Use structured inspection measurements to determine which station changed.",
        "The note describes a maintenance event, not a proven incident root cause.",
        "",
        "Routine checks for S01, S02 and S04 showed no recorded setpoint change.",
        "The illumination and exposure adjustment record is on page 2.",
    ]
):
    c.drawString(44, height - 197 - index * 22, line)
c.showPage()
header("Illumination and exposure record", 2)
c.setFillColor(colors.HexColor("#17324d"))
c.setFont("Helvetica-Bold", 14)
c.drawString(44, height - 165, "S03 adjustment - 10 October 2026")
c.setFont("Helvetica", 11)
for index, line in enumerate(
    [
        "Station S03 received an illumination program and camera exposure change",
        "at 2026-10-10T00:00:00. The recorded settings below are synthetic.",
        "Inspect illumination uniformity and verify camera exposure against the CSV.",
    ]
):
    c.drawString(44, height - 196 - index * 20, line)
table = Table(
    [
        ["Station", "Parameter", "Before", "After"],
        ["S03", "Illumination setpoint (lux)", "600", "340"],
        ["S03", "Camera exposure (microseconds)", "2400", "800"],
    ],
    colWidths=[65, 245, 95, 95],
    rowHeights=[30, 32, 32],
)
table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eef4")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#17324d")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#aab8c4")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
table.wrapOn(c, width, height)
table.drawOn(c, 44, height - 370)
c.setFont("Helvetica-Bold", 12)
c.drawString(44, height - 410, "Interpretation limits")
c.setFont("Helvetica", 11)
for index, line in enumerate(
    [
        "A simultaneous false-ejection increase may be associated with these changes.",
        "Correlation does not establish causation. Sensor alignment, product variation",
        "and other operational changes remain alternative explanations.",
        "Do not treat the settings table as a measurement of actual illumination.",
    ]
):
    c.drawString(44, height - 437 - index * 20, line)
c.save()
print(path)
