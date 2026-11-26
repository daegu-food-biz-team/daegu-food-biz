"""Server-side, print-ready Korean PDF for the existing Streamlit district report.

No browser API key or user-provided HTML is embedded in the PDF. The report is
built from the current validated regional data and the selected draft/AI text.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether

_FONT_REGISTERED = False


def _fonts():
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        # The `fonts-nanum` Linux package is installed via packages.txt in Streamlit Cloud.
        bases = [
            ("/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf"),
            ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        ]
        for normal, bold in bases:
            if Path(normal).is_file():
                pdfmetrics.registerFont(TTFont("ReportKorean", normal))
                pdfmetrics.registerFont(TTFont("ReportKoreanBold", bold if Path(bold).is_file() else normal))
                pdfmetrics.registerFontFamily("ReportKorean", normal="ReportKorean", bold="ReportKoreanBold")
                _FONT_REGISTERED = True
                break
        if not _FONT_REGISTERED:
            raise RuntimeError("PDF 한글 글꼴을 찾지 못했습니다. packages.txt에 fonts-nanum을 추가해야 합니다.")
    return "ReportKorean", "ReportKoreanBold"


def _styled_text(s: str) -> str:
    # Treat Gemini text as plain text; only allow tightly controlled bold markup.
    # Some Korean fonts lack Unicode mathematical minus; normalize before embedding.
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    escaped = html.escape(s, quote=False)
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)


def make_report_pdf(*, unit: str, report_text: str, mode: str, bottleneck: str,
                    confidence: str, as_of: str = "2025년 말", survey_note: str = "") -> bytes:
    """Return an embedded-Korean-font PDF ready for download and printing."""
    normal, bold = _fonts()
    ink = colors.HexColor("#17191C")
    muted = colors.HexColor("#636B74")
    blue = colors.HexColor("#214F9B")
    orange = colors.HexColor("#995019")

    def style(name, *, size=10, leading=17, font=None, color=ink, before=0, after=0, left=0):
        return ParagraphStyle(name, fontName=font or normal, fontSize=size, leading=leading,
                              textColor=color, alignment=TA_LEFT, wordWrap='CJK',
                              spaceBefore=before, spaceAfter=after, leftIndent=left,
                              allowWidows=0, allowOrphans=0)

    ss = {
        'kicker': style('kicker', size=9, leading=12, color=muted, after=8),
        'title': style('title', size=22, leading=31, font=bold, after=5),
        'meta': style('meta', size=10, leading=16, color=muted, after=10),
        'status': style('status', size=11, leading=17, font=bold, color=orange if bottleneck == '생존 병목' else blue, after=10),
        'section': style('section', size=12.5, leading=19, font=bold, before=15, after=7),
        'body': style('body', size=10, leading=17, after=7),
        'bullet': style('bullet', size=10, leading=17, after=6, left=12),
        'small': style('small', size=9, leading=15, color=muted, after=6),
    }
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=49, rightMargin=49,
                                 topMargin=45, bottomMargin=49, title=f'{unit} 동별 분석 보고서',
                                 author='DAEGU FOOD BIZ TEAM')
    story = [
        Paragraph('DAEGU FOOD BIZ  /  동별 외식 상권 진단', ss['kicker']),
        Paragraph(html.escape(unit), ss['title']),
        Paragraph(f'분석 보고서 ({html.escape(mode)})  ·  기준 {html.escape(as_of)}', ss['meta']),
        Paragraph(f'병목 유형  {html.escape(bottleneck)}   |   모델 확신도  {html.escape(confidence)}', ss['status']),
        HRFlowable(width='100%', thickness=0.6, color=colors.HexColor('#D5DAE0'), spaceAfter=12),
        Paragraph('대구 정체 동 65곳과 비교한 상대적 진단입니다. 개별 점포의 성공 확률이나 정책 효과를 뜻하지 않습니다.', ss['small'])
    ]

    paragraph = []

    def flush():
        if paragraph:
            story.append(Paragraph(_styled_text(' '.join(paragraph)), ss['body']))
            paragraph.clear()

    for raw in report_text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = re.match(r'^(?:#{1,5}\s+|\d{1,2}\s*/\s*)(.+)$', line)
        if heading:
            flush()
            story.append(Paragraph(_styled_text(heading.group(1)), ss['section']))
        elif re.match(r'^\s*(?:[-*•]|\d+[.)])\s+', line):
            flush()
            story.append(Paragraph('•  '+_styled_text(re.sub(r'^\s*(?:[-*•]|\d+[.)])\s+', '', line)), ss['bullet']))
        else:
            paragraph.append(line)
    flush()

    if survey_note and '현장 조사' not in report_text and '현장조사' not in report_text:
        story += [Paragraph('현장 조사', ss['section']), Paragraph(_styled_text(survey_note), ss['body'])]

    story += [Spacer(1, 9), HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#D5DAE0')),
              Spacer(1, 10), Paragraph('분석 자료의 한계와 실제 정책 적용 조건은 원본 데이터 및 현장 조사로 재확인해야 합니다.', ss['small'])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#E1E4E8'))
        canvas.line(49, 35, A4[0]-49, 35)
        canvas.setFont(normal, 8)
        canvas.setFillColor(muted)
        canvas.drawString(49, 24, 'DAEGU FOOD BIZ · 동별 분석 보고서')
        canvas.drawRightString(A4[0]-49, 24, str(doc.page))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
