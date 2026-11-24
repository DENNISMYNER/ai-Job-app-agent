"""PDF (ReportLab) and DOCX (python-docx) rendering of CVs and cover letters."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.core.config import get_settings
from app.security.files import resolve_inside


def generated_dir() -> Path:
    d = resolve_inside(get_settings().documents_dir, "generated")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _styles():
    ss = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name", parent=ss["Title"], fontSize=20, spaceAfter=2, alignment=0),
        "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=9.5, textColor="#444444", spaceAfter=4),
        "h": ParagraphStyle("h", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=2, textColor="#1f3a5f"),
        "b": ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=12.5),
        "bul": ParagraphStyle("bul", parent=ss["Normal"], fontSize=9.5, leading=12.5, leftIndent=12, bulletIndent=2),
        "role": ParagraphStyle("role", parent=ss["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold", spaceBefore=4),
    }


def _dates(a: str, b: str) -> str:
    return " – ".join(x for x in (a, b) if x)


def render_cv(cv) -> None:
    c = cv.content
    base = f"cv_{cv.id}_v{cv.version}"
    pdf_path, docx_path = generated_dir() / f"{base}.pdf", generated_dir() / f"{base}.docx"
    st = _styles()
    e = escape
    flow = [Paragraph(e(c["name"] or "Your Name"), st["name"])]
    if c["headline"]:
        flow.append(Paragraph(e(c["headline"]), st["sub"]))
    contact = " | ".join(x for x in [c["contact"]["email"], c["contact"]["phone"], c["contact"]["location"], *c["links"].values()] if x)
    if contact:
        flow.append(Paragraph(e(contact), st["sub"]))
    flow.append(HRFlowable(width="100%", color="#1f3a5f"))
    if c["summary"]:
        flow += [Paragraph("PROFILE", st["h"]), Paragraph(e(c["summary"]), st["b"])]
    if c["skills"]:
        flow += [Paragraph("SKILLS", st["h"]), Paragraph(e(", ".join(c["skills"])), st["b"])]
    if c["experience"]:
        flow.append(Paragraph("EXPERIENCE", st["h"]))
        for x in c["experience"]:
            flow.append(Paragraph(e(f"{x['title']} — {x['company']}  ({_dates(x['start_date'], x['end_date'])})"), st["role"]))
            flow += [Paragraph(e(b), st["bul"], bulletText="•") for b in x["bullets"]]
    if c["education"]:
        flow.append(Paragraph("EDUCATION", st["h"]))
        for x in c["education"]:
            line = ", ".join(v for v in [x["degree"], x["field"], x["institution"]] if v)
            flow.append(Paragraph(e(f"{line} ({_dates(x['start_date'], x['end_date'])})".replace(" ()", "")), st["b"]))
    if c["certifications"]:
        flow.append(Paragraph("CERTIFICATIONS", st["h"]))
        flow += [Paragraph(e(f"{x['name']}" + (f" — {x['issuer']}" if x["issuer"] else "")), st["b"]) for x in c["certifications"]]
    if c["languages"]:
        flow += [Paragraph("LANGUAGES", st["h"]),
                 Paragraph(e(", ".join(f"{x['language']}" + (f" ({x['proficiency']})" if x["proficiency"] else "") for x in c["languages"])), st["b"])]
    SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                      title=cv.title, author=c["name"]).build(flow)

    d = Document()
    d.styles["Normal"].font.size = Pt(10.5)
    d.add_heading(c["name"] or "Your Name", 0)
    if c["headline"]:
        d.add_paragraph(c["headline"])
    if contact:
        d.add_paragraph(contact)
    if c["summary"]:
        d.add_heading("Profile", 2)
        d.add_paragraph(c["summary"])
    if c["skills"]:
        d.add_heading("Skills", 2)
        d.add_paragraph(", ".join(c["skills"]))
    if c["experience"]:
        d.add_heading("Experience", 2)
        for x in c["experience"]:
            p = d.add_paragraph()
            p.add_run(f"{x['title']} — {x['company']}").bold = True
            p.add_run(f"  ({_dates(x['start_date'], x['end_date'])})")
            for b in x["bullets"]:
                d.add_paragraph(b, style="List Bullet")
    if c["education"]:
        d.add_heading("Education", 2)
        for x in c["education"]:
            d.add_paragraph(", ".join(v for v in [x["degree"], x["field"], x["institution"]] if v) + (f" ({_dates(x['start_date'], x['end_date'])})" if x["end_date"] or x["start_date"] else ""))
    if c["certifications"]:
        d.add_heading("Certifications", 2)
        for x in c["certifications"]:
            d.add_paragraph(x["name"] + (f" — {x['issuer']}" if x["issuer"] else ""), style="List Bullet")
    if c["languages"]:
        d.add_heading("Languages", 2)
        d.add_paragraph(", ".join(f"{x['language']}" + (f" ({x['proficiency']})" if x["proficiency"] else "") for x in c["languages"]))
    d.save(str(docx_path))
    cv.pdf_path, cv.docx_path = pdf_path.name, docx_path.name


def render_letter_pdf(letter, name: str = "") -> None:
    path = generated_dir() / f"letter_{letter.id}_v{letter.version}.pdf"
    st = _styles()
    flow = []
    for para in letter.content.split("\n\n"):
        flow += [Paragraph(escape(para).replace("\n", "<br/>"), st["b"]), Spacer(1, 6)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
                      title=letter.title, author=name).build(flow or [Paragraph(" ", st["b"])])
    letter.pdf_path = path.name


def generated_file(name: str) -> Path:
    return resolve_inside(get_settings().documents_dir, "generated", name)
