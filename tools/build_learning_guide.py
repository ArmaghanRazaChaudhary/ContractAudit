from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "Contract_Audit_RAG_Learning_Guide.md"
OUTPUT = ROOT / "docs" / "Contract_Audit_RAG_Learning_Guide.pdf"


def register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("GuideSans", regular))
        pdfmetrics.registerFont(TTFont("GuideSans-Bold", bold))
        return "GuideSans", "GuideSans-Bold"
    return "Helvetica", "Helvetica-Bold"


BODY_FONT, BOLD_FONT = register_fonts()


class GuideDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title="Contract Audit RAG: Beginner's Learning Guide",
            author="Contract Audit RAG Project",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        self.addPageTemplates(PageTemplate(id="guide", frames=frame, onPage=draw_page))
        self._bookmark_counter = 0

    def beforeDocument(self) -> None:
        self._bookmark_counter = 0

    def afterFlowable(self, flowable: Flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        if flowable.style.name not in {"GuideH1", "GuideH2"}:
            return
        level = 0 if flowable.style.name == "GuideH1" else 1
        text = flowable.getPlainText()
        key = f"heading-{self._bookmark_counter}"
        self._bookmark_counter += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def draw_page(canvas: object, doc: GuideDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    if doc.page > 1:
        canvas.drawString(20 * mm, 10 * mm, "Contract Audit RAG Learning Guide")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", rf'<font name="{BOLD_FONT}">\1</font>', escaped)
    return escaped


def styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=sample["Title"],
            fontName=BOLD_FONT,
            fontSize=24,
            leading=29,
            textColor=colors.HexColor("#17324D"),
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=sample["Normal"],
            fontName=BODY_FONT,
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#4B5D6B"),
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "GuideH1",
            parent=sample["Heading1"],
            fontName=BOLD_FONT,
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#17324D"),
            spaceBefore=12,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "GuideH2",
            parent=sample["Heading2"],
            fontName=BOLD_FONT,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#24577A"),
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "GuideH3",
            parent=sample["Heading3"],
            fontName=BOLD_FONT,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#334E60"),
            spaceBefore=7,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "GuideBody",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.4,
            leading=13.2,
            textColor=colors.HexColor("#20262B"),
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet",
            parent=sample["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.2,
            leading=12.8,
            leftIndent=14,
            firstLineIndent=-7,
            bulletIndent=6,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "GuideCode",
            parent=sample["Code"],
            fontName="Courier",
            fontSize=7.2,
            leading=9.2,
            leftIndent=7,
            rightIndent=7,
            borderColor=colors.HexColor("#CCD5DB"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#F3F6F8"),
            spaceBefore=4,
            spaceAfter=7,
        ),
    }


def wrap_code(lines: list[str]) -> str:
    wrapped: list[str] = []
    for line in lines:
        chunks = textwrap.wrap(
            line,
            width=96,
            subsequent_indent="    ",
            replace_whitespace=False,
            drop_whitespace=False,
        )
        wrapped.extend(chunks or [""])
    return "\n".join(wrapped)


def markdown_flowables(markdown: str) -> list[Flowable]:
    style = styles()
    flowables: list[Flowable] = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False
    first_heading = True

    def flush_paragraph() -> None:
        if paragraph:
            flowables.append(Paragraph(inline_markup(" ".join(paragraph)), style["body"]))
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                flowables.append(Preformatted(wrap_code(code), style["code"]))
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if not line:
            flush_paragraph()
            continue
        if line == "---":
            flush_paragraph()
            flowables.append(Spacer(1, 5))
            continue
        if line.startswith("# "):
            flush_paragraph()
            text = line[2:]
            if first_heading:
                flowables.append(Spacer(1, 45 * mm))
                flowables.append(Paragraph(inline_markup(text), style["title"]))
                first_heading = False
            else:
                flowables.append(PageBreak())
                flowables.append(Paragraph(inline_markup(text), style["h1"]))
            continue
        if line.startswith("## "):
            flush_paragraph()
            text = line[3:]
            if not any(isinstance(item, TableOfContents) for item in flowables):
                flowables.append(Paragraph(inline_markup(text), style["subtitle"]))
                flowables.append(Spacer(1, 35 * mm))
                flowables.append(Paragraph("Table of Contents", style["h1"]))
                toc = TableOfContents()
                toc.levelStyles = [
                    ParagraphStyle(
                        "TOC1",
                        fontName=BODY_FONT,
                        fontSize=9,
                        leading=13,
                        leftIndent=0,
                        firstLineIndent=0,
                    ),
                    ParagraphStyle(
                        "TOC2",
                        fontName=BODY_FONT,
                        fontSize=8,
                        leading=11,
                        leftIndent=12,
                        firstLineIndent=0,
                    ),
                ]
                flowables.extend([toc, PageBreak()])
            else:
                flowables.append(Paragraph(inline_markup(text), style["h2"]))
            continue
        if line.startswith("### "):
            flush_paragraph()
            flowables.append(Paragraph(inline_markup(line[4:]), style["h3"]))
            continue
        if re.match(r"^[-*] ", line):
            flush_paragraph()
            flowables.append(
                Paragraph(inline_markup(line[2:]), style["bullet"], bulletText="\u2022")
            )
            continue
        if re.match(r"^\d+\. ", line):
            flush_paragraph()
            number, text = line.split(". ", 1)
            flowables.append(
                Paragraph(inline_markup(text), style["bullet"], bulletText=f"{number}.")
            )
            continue
        paragraph.append(line)
    flush_paragraph()
    return flowables


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    document = GuideDocTemplate(str(OUTPUT))
    document.multiBuild(markdown_flowables(markdown))
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
