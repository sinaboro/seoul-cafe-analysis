r"""프로젝트 교안 PDF 빌더 (서울 커피 상권 분석)

guide/*.md 가 원고다. 파일 이름 순서(00, 01, ...)대로 묶어 서울커피상권분석_프로젝트교안.pdf 를 만든다.

    pip install reportlab
    python tools/build_guide.py                                  # 교안 PDF
    python tools/build_guide.py "C:\Users\M\Desktop\공부자료"   # 만든 뒤 그 폴더에도 복사

그림은 guide/images 에서 먼저 찾고, 없으면 분석 스크립트가 만든 images 폴더에서 찾는다.
필요한 글꼴: 맑은 고딕, Consolas (둘 다 Windows 기본).

원고 문법 (보통 마크다운 + 아래 몇 가지)
  ![그림 설명](../images/x.png)            그림 (본문 폭에 맞춰 넣고 아래에 설명을 단다)
  <!-- file: tools/... -->                 바로 아래 코드 상자를 그 파일 내용으로 채운다
  **[PS]** 설명                            명령을 치는 곳 표시 (PowerShell)
"""

import glob
import os
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "guide" / "images"
INSTRUCTOR = "김대철"
REPO = "github.com/sinaboro/seoul-cafe-analysis"

# 교안별 설정
GUIDES = {
    "guide": dict(
        src=ROOT / "guide",
        out=ROOT / "서울커피상권분석_프로젝트교안.pdf",
        title="서울 커피 상권 분석",
        cover_sub=["NumPy · pandas · seaborn 으로 분석하고", "FastAPI + HTML/CSS/JS 로 대시보드 서비스 만들기"],
        cover_tools="Open API · pandas 병합 · seaborn 시각화 · NumPy 점수화 · FastAPI · Chart.js",
        cover_course="프로젝트 안내 교안 · 혼자 진행하는 학생용 · 실제 서울시 공공데이터",
        cover_env="실습 환경  Python 3.12 · VS Code · 서울 열린데이터광장 인증키(무료)",
        accent="#6F4E37",
    ),
}
CFG = GUIDES["guide"]  # build() 에서 바꾼다


# ---------------------------------------------------------------- 글꼴
def find_font(names, dirs):
    """여러 폴더에서 글꼴 파일을 찾는다. names 는 후보 파일 이름(와일드카드 가능) 목록."""
    for d in dirs:
        if not d:
            continue
        for name in names:
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                return hits[0]
    raise SystemExit(f"글꼴을 찾을 수 없습니다: {names}")


font_dirs = [str(ROOT / "tools" / "fonts"), "C:/Windows/Fonts"]
FONTS = {
    "Body": TTFont("Body", find_font(["malgun.ttf"], font_dirs)),
    "BodyB": TTFont("BodyB", find_font(["malgunbd.ttf"], font_dirs)),
    "Mono": TTFont("Mono", find_font(["consola.ttf"], font_dirs)),
    "MonoB": TTFont("MonoB", find_font(["consolab.ttf"], font_dirs)),
    "Sym": TTFont("Sym", find_font(["seguisym.ttf"], font_dirs)),  # ✔ ← 같은 기호
}
for font in FONTS.values():
    pdfmetrics.registerFont(font)
pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyB", italic="Body", boldItalic="BodyB")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="MonoB", italic="Mono", boldItalic="MonoB")

MISSING = set()  # 어느 글꼴에도 없는 글자 (빌드 끝에 알려 준다)


def has_glyph(font_name, ch):
    return ord(ch) in FONTS[font_name].face.charToGlyph


def fallback(text, main, other):
    """main 글꼴에 없는 글자를 other(없으면 기호 글꼴)로 바꿔 그린다. text 는 이미 escape 된 문자열."""
    out = []
    for ch in text:
        if ch == "️":  # 이모지 모양 선택자(눈에 안 보이는 글자)는 버린다
            continue
        if ord(ch) < 128 or has_glyph(main, ch):
            out.append(ch)
        elif has_glyph(other, ch):
            out.append(f'<font name="{other}">{ch}</font>')
        elif has_glyph("Sym", ch):
            out.append(f'<font name="Sym">{ch}</font>')
        else:
            MISSING.add(ch)
            out.append("?")
    return "".join(out)


# ---------------------------------------------------------------- 색과 스타일
NAVY = colors.HexColor("#1f3a5f")
BLUE = colors.HexColor("#03588C")
LIGHT = colors.HexColor("#eef3f8")
CODE_BG = colors.HexColor("#f6f8fa")
OUT_BG = colors.HexColor("#fbfbf3")
GREY = colors.HexColor("#6b7280")

# 명령을 치는 곳 표시([PS])의 색과 풀이
WHERE = {"PS": ("#1d5fa8", "PowerShell (또는 VS Code 터미널)")}
# 코드 상자의 왼쪽 띠 색 (언어별)
EDGE = {
    "powershell": "#1d5fa8", "bash": "#2e7d32", "sh": "#2e7d32", "sql": "#b9770e",
    "python": "#03588C", "text": "#9aa3ad", "json": "#9aa3ad", "yaml": "#03588C", "html": "#03588C",
    "markdown": "#8e44ad", "dockerfile": "#1d63ed",
    "jsx": "#1aa3c8", "javascript": "#c9a400", "js": "#c9a400", "css": "#8e44ad",
    "dax": "#E0A800", "m": "#3E7C59", "powerquery": "#3E7C59",
}

S = {}
S["body"] = ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=15.5, spaceAfter=4.5)
S["bullet"] = ParagraphStyle("bullet", parent=S["body"], leftIndent=13, bulletIndent=3, spaceAfter=2)
S["bullet2"] = ParagraphStyle("bullet2", parent=S["bullet"], leftIndent=26, bulletIndent=16)
S["h1"] = ParagraphStyle("h1", fontName="BodyB", fontSize=18, leading=24, textColor=colors.white)
S["h2"] = ParagraphStyle("h2", fontName="BodyB", fontSize=13.5, leading=19, textColor=NAVY,
                         spaceBefore=12, spaceAfter=5, keepWithNext=1)
S["h3"] = ParagraphStyle("h3", fontName="BodyB", fontSize=11, leading=16, textColor=BLUE,
                         spaceBefore=8, spaceAfter=3, keepWithNext=1)
S["h4"] = ParagraphStyle("h4", fontName="BodyB", fontSize=9.8, leading=15, textColor=colors.HexColor("#374151"),
                         spaceBefore=5, spaceAfter=2, keepWithNext=1)
S["where"] = ParagraphStyle("where", fontName="BodyB", fontSize=8.2, leading=11, spaceBefore=3,
                            spaceAfter=1.5, keepWithNext=1)
S["cell"] = ParagraphStyle("cell", fontName="Body", fontSize=8.6, leading=12.5)
S["cellh"] = ParagraphStyle("cellh", parent=S["cell"], fontName="BodyB", textColor=colors.white)
S["quote"] = ParagraphStyle("quote", parent=S["body"], fontSize=9.1, leading=14.2, spaceAfter=2)
S["caption"] = ParagraphStyle("caption", fontName="Body", fontSize=8.4, leading=12, alignment=1,
                              textColor=GREY, spaceBefore=3, spaceAfter=10)
S["toc1"] = ParagraphStyle("toc1", fontName="BodyB", fontSize=10, leading=16.5, leftIndent=0)
S["toc2"] = ParagraphStyle("toc2", fontName="Body", fontSize=8.6, leading=12.6, leftIndent=16,
                           textColor=colors.HexColor("#374151"))

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
TEXT_W = PAGE_W - 2 * MARGIN


def inline(text):
    """**굵게**, `코드`, [글](링크), *기울임* 을 ReportLab 마크업으로 바꾼다."""
    text = re.sub(r"\[([^\]]+)\]\((?!\s)[^)]*\)", r"\1", text)  # [글](링크) → 글
    # **굵게** 를 먼저 표시해 둔다. (굵은 글 안에 `코드` 가 있어도 깨지지 않게)
    text = re.sub(r"\*\*(.+?)\*\*", "\x01\\1\x02", text)
    parts = re.split(r"(``.+?``|`[^`]+`)", text)
    out = []
    for p in parts:
        if p.startswith("``") and p.endswith("``") and len(p) > 4:  # ``  ` `` → 글자 ` 하나
            code = fallback(escape(p[2:-2].strip()), "Mono", "Body")
            out.append(f'<font name="Mono" color="#b5245e">{code}</font>')
            continue
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            code = fallback(escape(p[1:-1]), "Mono", "Body")
            out.append(f'<font name="Mono" color="#b5245e">{code}</font>')
            continue
        p = re.sub(r"\*\*(.+?)\*\*", "\x01\\1\x02", p)  # **굵게**
        p = re.sub(r"(?<![\*\w])\*([^*\s][^*]*?)\*(?![\*\w])", r"\1", p)  # *기울임* → 그냥 글
        p = fallback(escape(p), "Body", "Mono")
        p = p.replace("\\", '<font name="Mono">\\</font>')  # 맑은 고딕은 \ 를 ₩ 로 그린다
        out.append(p)
    return "".join(out).replace("\x01", "<b>").replace("\x02", "</b>")


def disp_width(s):
    """화면 폭: 한글·한자는 2칸, 나머지는 1칸."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


# ---------------------------------------------------------------- 코드 상자
def code_table(text, lang):
    """코드 한 줄을 표의 한 행으로 만든다. → 쪽이 넘어가도 자연스럽게 나뉜다."""
    text = text.expandtabs(4)
    lines = text.split("\n")
    avail = TEXT_W - 14
    cols = max([disp_width(line) for line in lines] + [1])
    size = max(min(8.2, avail / (cols * 0.55)), 6.8)  # 긴 줄이 있으면 글자를 조금 줄인다
    max_cols = int(avail / (size * 0.55))
    st = ParagraphStyle("c", fontName="Mono", fontSize=size, leading=size * 1.38)
    comment_mark = {"bash": "#", "sh": "#", "powershell": "#", "yaml": "#", "python": "#",
                    "dockerfile": "#", "gitignore": "#", "conf": "#", "sql": "--",
                    "jsx": "//", "javascript": "//", "js": "//", "dax": "//", "m": "//"}.get(lang)

    def markup(s):
        body = fallback(escape(s).replace(" ", "&nbsp;"), "Mono", "Body")  # 빈칸을 먼저 바꾼다 (<font name=...> 안의 빈칸은 그대로 두려고)
        if comment_mark and s.strip().startswith(comment_mark):  # 줄 전체가 주석이면 초록색
            return f'<font color="#2e7d32">{body}</font>'
        if comment_mark and f" {comment_mark} " in s and lang != "dockerfile":  # 줄 끝 주석
            code, _, note = s.partition(f" {comment_mark} ")
            code = fallback(escape(code).replace(" ", "&nbsp;"), "Mono", "Body")
            note = fallback(escape(f" {comment_mark} " + note).replace(" ", "&nbsp;"), "Mono", "Body")
            return f'{code}<font color="#2e7d32">{note}</font>'
        return body

    data = []
    for line in lines:
        while disp_width(line) > max_cols:  # 그래도 길면 줄을 나눈다
            cut, w = 0, 0
            for i, c in enumerate(line):
                w += 2 if unicodedata.east_asian_width(c) in "WF" else 1
                if w > max_cols:
                    cut = i
                    break
            data.append([Paragraph(markup(line[:cut]) or "&nbsp;", st)])
            line = "  " + line[cut:]
        data.append([Paragraph(markup(line) or "&nbsp;", st)])
    is_output = lang in ("text", "json")
    t = Table(data, colWidths=[TEXT_W], splitByRow=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), OUT_BG if is_output else CODE_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, colors.HexColor(EDGE.get(lang, "#9aa3ad"))),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
    ]))
    t.spaceAfter = 7
    return t


def quote_box(lines):
    """> 로 시작하는 인용 문단을 왼쪽 띠가 있는 상자로 그린다."""
    inner = []
    para = []

    def flush():
        if para:
            inner.append(Paragraph(inline(" ".join(para)), S["quote"]))
            para.clear()

    for line in lines:
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("- "):
            flush()
            inner.append(Paragraph(inline(s[2:]), S["quote"], bulletText="•"))
        else:
            para.append(s)
    flush()
    t = Table([[inner]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7e8")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#e8890c")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    t.spaceBefore, t.spaceAfter = 3, 7
    return [t]


def md_table(rows):
    """마크다운 표를 그린다. 머리 줄이 비어 있으면(| | |) 머리 없는 표로 그린다."""
    rows = [[c.strip().replace("\x00", "|") for c in r.replace("\\|", "\x00").strip().strip("|").split("|")]
            for r in rows]  # \| 는 칸 구분이 아니라 글자 |
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    has_head = any(c for c in rows[0])
    if not has_head:
        rows = rows[1:]
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]

    def plain(c):
        return re.sub(r"[`*]|\]\([^)]*\)", "", c)

    widths = [max(disp_width(plain(r[i])) for r in rows) for i in range(ncol)]
    widths = [min(max(w, 5), 58) + 3 for w in widths]
    total = sum(widths)
    colw = [TEXT_W * w / total for w in widths]
    data = [[Paragraph(inline(c), S["cellh"] if (i == 0 and has_head) else S["cell"]) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=colw, repeatRows=1 if has_head else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3df")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if has_head:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT])]
    else:
        style += [("BACKGROUND", (0, 0), (0, -1), LIGHT)]
    t.setStyle(TableStyle(style))
    t.spaceBefore, t.spaceAfter = 2, 8
    return [t]


def figure(path, caption):
    """![설명](../images/x.png) → 본문 폭에 맞춘 그림 + 설명. 둘이 쪽 사이에서 떨어지지 않게 묶는다."""
    src = IMG_DIR / Path(path).name
    if not src.exists():                                  # 분석 그래프는 프로젝트의 images 폴더에 있다
        src = ROOT / "images" / Path(path).name
    iw, ih = ImageReader(str(src)).getSize()
    w = TEXT_W if Path(path).name.startswith("fig_") else TEXT_W * 0.86  # 화면 캡처는 조금 작게
    h = w * ih / iw
    if h > 115 * mm:  # 너무 길면 높이에 맞춘다
        h = 115 * mm
        w = h * iw / ih
    img = Image(str(src), width=w, height=h)
    img.hAlign = "CENTER"
    parts = [Spacer(1, 4), img]
    parts.append(Paragraph(f"[그림] {inline(caption)}", S["caption"]) if caption else Spacer(1, 8))
    return KeepTogether(parts)


class ChapterBanner(Flowable):
    """장 제목 띠. 목차와 책갈피에도 등록된다."""

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.para = Paragraph(inline(text), S["h1"])

    def wrap(self, aw, ah):
        self.para.wrap(aw - 24, ah)
        self.height = self.para.height + 26
        return aw, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 0, TEXT_W, self.height, 4, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(CFG["accent"]))
        c.rect(0, 0, 6, self.height, fill=1, stroke=0)
        self.para.drawOn(c, 16, 12)


# ---------------------------------------------------------------- 문서 템플릿
class GuideDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN + 6, bottomMargin=MARGIN, title=f"{CFG['title']} 학습 교안",
                         author=INSTRUCTOR, subject=CFG["cover_course"])
        frame = Frame(MARGIN, MARGIN, TEXT_W, PAGE_H - 2 * MARGIN - 6, id="f",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate("cover", [frame], onPage=self.cover),
                               PageTemplate("body", [frame], onPageEnd=self.decorate)])
        self.chapter = ""

    def beforeDocument(self):
        self.chapter = ""

    def afterFlowable(self, f):
        if isinstance(f, ChapterBanner):
            self.chapter = re.sub(r"<[^>]+>", "", f.text)
            key = f"ch{self.page}{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(self.chapter, key, level=0)
            if self.chapter != "목차":
                self.notify("TOCEntry", (0, escape(self.chapter), self.page, key))
        elif isinstance(f, Paragraph) and f.style.name == "h2":
            text = f.getPlainText()
            key = f"h2{self.page}{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=1)
            # 부록의 소절과 장마다 반복되는 '학습 목표·정리·확인 문제' 는 목차에서 뺀다 (목차를 짧게)
            if not self.chapter.startswith("부록") and text not in ("학습 목표", "정리", "확인 문제"):
                self.notify("TOCEntry", (1, escape(text), self.page, key))

    def decorate(self, c, doc):
        """본문 쪽의 머리말·꼬리말"""
        c.saveState()
        c.setFont("Body", 7.5)
        c.setFillColor(GREY)
        c.drawString(MARGIN, PAGE_H - MARGIN + 2, self.chapter)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 2, f"{CFG['title']} 학습 교안")
        c.setStrokeColor(colors.HexColor("#d1d9e3"))
        c.setLineWidth(0.5)
        c.line(MARGIN, PAGE_H - MARGIN - 1, PAGE_W - MARGIN, PAGE_H - MARGIN - 1)
        c.line(MARGIN, MARGIN - 7, PAGE_W - MARGIN, MARGIN - 7)
        c.drawString(MARGIN, MARGIN - 16, f"강사 {INSTRUCTOR}")
        c.drawCentredString(PAGE_W / 2, MARGIN - 16, str(doc.page))
        c.drawRightString(PAGE_W - MARGIN, MARGIN - 16, REPO)
        c.restoreState()

    def cover(self, c, doc):
        """표지"""
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H * 0.42, PAGE_W, PAGE_H * 0.58, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(CFG["accent"]))
        c.rect(0, PAGE_H * 0.42 - 6, PAGE_W, 6, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#f0a500"))
        c.roundRect(MARGIN + 4, PAGE_H - 70 * mm, 34 * mm, 9 * mm, 3, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("BodyB", 11)
        c.drawCentredString(MARGIN + 4 + 17 * mm, PAGE_H - 70 * mm + 3 * mm, "학습 교안")
        c.setFont("BodyB", 40)
        c.drawString(MARGIN + 4, PAGE_H - 98 * mm, CFG["title"])
        c.setFont("BodyB", 19)
        for i, line in enumerate(CFG["cover_sub"]):
            c.drawString(MARGIN + 4, PAGE_H - (114 + i * 10) * mm, line)
        c.setFont("Body", 11.5)
        c.setFillColor(colors.HexColor("#d6e2f0"))
        c.drawString(MARGIN + 4, PAGE_H - 141 * mm, CFG["cover_tools"])
        c.drawString(MARGIN + 4, PAGE_H - 149 * mm, CFG["cover_course"])
        c.setFillColor(NAVY)
        c.setFont("BodyB", 15)
        c.drawString(MARGIN + 4, 70 * mm, f"강사  {INSTRUCTOR}")
        c.setFont("Body", 10.5)
        c.setFillColor(colors.HexColor("#374151"))
        c.drawString(MARGIN + 4, 60 * mm, f"작성일  {date.today():%Y.%m.%d}")
        c.drawString(MARGIN + 4, 52 * mm, CFG["cover_env"])
        c.drawString(MARGIN + 4, 44 * mm, f"실습 저장소  https://{REPO}")
        c.setFont("Body", 8.5)
        c.setFillColor(GREY)
        c.drawString(MARGIN + 4, 28 * mm,
                     "교안의 숫자와 그래프는 서울시 상권분석서비스 실제 데이터(2024년 3분기 ~ 2026년 2분기)로 만들었습니다.")
        c.drawString(MARGIN + 4, 22 * mm, "새 분기 데이터를 받으면 숫자가 달라질 수 있습니다. 출처: 서울 열린데이터광장 (공공누리 제1유형)")
        c.restoreState()


# ---------------------------------------------------------------- 마크다운 → 흐름
BLOCK_START = re.compile(r"^(#|@@|>|```|\||- |\d+\. |-{3,}$|!\[|<!--|\*\*\[PS\]\*\*)")


def parse(text):
    flow = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or re.fullmatch(r"-{3,}", s):  # 빈 줄과 가로줄(---)은 건너뛴다
            i += 1
            continue
        m_where = re.fullmatch(r"\*\*\[(PS)\]\*\*(.*)", s)
        m_img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if s.startswith("<!--"):  # 주석(파일 끼워 넣기 표시 등)은 PDF 에 넣지 않는다
            while "-->" not in lines[i]:
                i += 1
        elif m_img:
            flow.append(figure(m_img.group(2), m_img.group(1)))
        elif s.startswith("# "):
            flow += [NextPageTemplate("body"), PageBreak(), ChapterBanner(s[2:]), Spacer(1, 10)]
        elif s.startswith("## "):
            flow += [CondPageBreak(35 * mm), Paragraph(inline(s[3:]), S["h2"])]
        elif s.startswith("### "):
            flow += [CondPageBreak(25 * mm), Paragraph(inline(s[4:]), S["h3"])]
        elif s.startswith("#### "):
            flow += [CondPageBreak(20 * mm), Paragraph(inline(s[5:]), S["h4"])]
        elif s == "@@toc":
            toc = TableOfContents()
            toc.levelStyles = [S["toc1"], S["toc2"]]
            toc.dotsMinLevel = 0
            flow.append(toc)
        elif m_where:
            # 명령을 치는 곳 표시: 색 이름표로 그리고, 아래 코드 상자와 떨어지지 않게 한다.
            color, name = WHERE[m_where.group(1)]
            rest = inline(m_where.group(2).strip())
            tag = f'<font color="{color}">■ [{m_where.group(1)}] {name}</font>'
            flow += [CondPageBreak(22 * mm),
                     Paragraph(tag + (f'&nbsp;&nbsp;<font name="Body" color="#6b7280">{rest}</font>' if rest else ""),
                               S["where"])]
        elif s.startswith("```"):
            lang = (s[3:].split() or ["text"])[0]
            buf = []
            i += 1
            while not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            indent = min((len(b) - len(b.lstrip()) for b in buf if b.strip()), default=0)
            flow.append(code_table("\n".join(b[indent:] for b in buf), lang))
        elif s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:])
                i += 1
            flow += quote_box(buf)
            continue
        elif s.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                buf.append(lines[i])
                i += 1
            flow += md_table(buf)
            continue
        elif s.startswith("- "):
            lvl = "bullet2" if line.startswith("  ") else "bullet"
            flow.append(Paragraph(inline(s[2:]), S[lvl], bulletText="•" if lvl == "bullet" else "–"))
        elif re.match(r"^\d+\. ", s):
            n, rest = s.split(". ", 1)
            flow.append(Paragraph(inline(rest), S["bullet"], bulletText=f"{n}."))
        else:
            para = [s]
            while i + 1 < len(lines) and lines[i + 1].strip() and not BLOCK_START.match(lines[i + 1].strip()):
                i += 1
                para.append(lines[i].strip())
            flow.append(Paragraph(inline(" ".join(para)), S["body"]))
        i += 1
    return flow


# ---------------------------------------------------------------- 원고 모으기
INCLUDE = re.compile(r"(<!-- file: (\S+) -->)\n\n```(\w*)\n(.*?)```", re.DOTALL)


def sync_includes(md_path):
    """<!-- file: 경로 --> 바로 아래 코드 상자를 그 파일의 내용으로 채우고, 바뀌었으면 md 를 고쳐 쓴다."""
    text = md_path.read_text(encoding="utf-8")

    def fill(m):
        body = (ROOT / m.group(2)).read_text(encoding="utf-8").rstrip("\n")
        return f"{m.group(1)}\n\n```{m.group(3)}\n{body}\n```"

    new = INCLUDE.sub(fill, text)
    if new != text:
        md_path.write_text(new, encoding="utf-8")
        print("  원고 갱신:", md_path.relative_to(ROOT))
    return new


def manuscript():
    parts = ["# 목차\n\n@@toc\n"]
    for md in sorted(CFG["src"].glob("*.md")):
        parts.append(sync_includes(md))
    return "\n\n".join(parts)


def build(key, copy_to):
    global CFG
    CFG = GUIDES[key]
    MISSING.clear()
    story = [NextPageTemplate("cover"), Spacer(1, 1)] + parse(manuscript())
    doc = GuideDoc(CFG["out"])
    doc.multiBuild(story)
    print("완료:", CFG["out"].relative_to(ROOT), f"({doc.page}쪽)")
    if MISSING:
        print("  글꼴에 없는 글자:", " ".join(sorted(MISSING)), [hex(ord(c)) for c in sorted(MISSING)])
    for dest in copy_to:
        shutil.copy(CFG["out"], Path(dest) / CFG["out"].name)
        print("  복사:", Path(dest) / CFG["out"].name)


def main():
    args = sys.argv[1:]
    keys = [a for a in args if a in GUIDES] or list(GUIDES)
    copy_to = [a for a in args if a not in GUIDES]
    for key in keys:
        build(key, copy_to)


if __name__ == "__main__":
    main()
