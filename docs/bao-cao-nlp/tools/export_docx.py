"""Xuất báo cáo LaTeX sang DOCX (chạy sau khi đã biên dịch main.pdf bằng XeLaTeX + Biber).

Các bước:
1. Biên dịch riêng từng hình TikZ/pgfplots thành PNG (lớp standalone, cùng kiểu khối với preamble).
2. Tạo bản LaTeX phẳng cho Pandoc: gộp \\input, thay hình bằng PNG, thay \\ref và \\cite bằng số
   lấy từ main.aux / main.bbl (giống hệt bản PDF), thêm số "Hình x.y." / "Bảng x.y." vào chú thích.
3. Pandoc -> DOCX với reference.docx (Times New Roman 13, lề theo mẫu).
4. python-docx: thêm trang bìa, mục lục (trường TOC), danh mục tài liệu tham khảo lấy từ PDF.

Cách dùng (từ thư mục docs/bao-cao-nlp):
    python tools/export_docx.py --pandoc <đường dẫn pandoc> --xelatex <đường dẫn xelatex>
Cần: pymupdf, python-docx.
"""

import argparse
import re
import subprocess
from pathlib import Path

import pymupdf
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build-docx"
CHAPTERS = ["modau", "chuong1", "chuong2", "chuong3", "chuong4", "ketluan", "phuluc"]

STANDALONE_HEAD = r"""\documentclass[tikz,border=6pt]{standalone}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\setmonofont{Courier New}[Scale=0.95]
\usepackage{amsmath,amssymb,xcolor,pifont}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\definecolor{AccentBlue}{HTML}{1F4E79}
\definecolor{AccentLightBlue}{HTML}{DEEAF6}
\definecolor{AccentGray}{HTML}{A6A6A6}
\definecolor{AccentDarkGray}{HTML}{333333}
\usetikzlibrary{positioning,arrows.meta,fit,calc,shapes.geometric,shapes.misc,backgrounds}
\newcommand{\IB}{Index Beast}
\newcommand{\code}[1]{\texttt{#1}}
\tikzset{
  blk/.style={draw, rounded corners=2pt, fill=AccentLightBlue!60, align=center, font=\small, minimum height=8mm, inner sep=4pt},
  dat/.style={draw, cylinder, shape border rotate=90, aspect=0.18, fill=AccentGray!20, align=center, font=\small, minimum height=10mm, inner sep=3pt},
  dec/.style={draw, diamond, aspect=2.2, fill=white, align=center, font=\small, inner sep=1pt},
  arr/.style={-{Stealth[length=2.2mm]}, line width=0.6pt},
  grp/.style={draw, dashed, rounded corners=3pt, inner sep=6pt}
}
\begin{document}
"""


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def labels_from_aux() -> dict[str, str]:
    aux = read("main.aux")
    out = {}
    for key, num in re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux):
        out[key] = num
    return out


def cite_numbers() -> dict[str, int]:
    bbl = read("main.bbl")
    keys = re.findall(r"\\entry\{([^}]+)\}", bbl)
    return {k: i + 1 for i, k in enumerate(keys)}


def build_figures(xelatex: str) -> dict[str, str]:
    """Trả về {label hình: tên file png} cho mọi figure chứa tikzpicture."""
    BUILD.mkdir(exist_ok=True)
    result = {}
    n = 0
    for ch in CHAPTERS:
        text = read(f"chapters/{ch}.tex")
        for fig in re.finditer(r"\\begin\{figure\}.*?\\end\{figure\}", text, re.S):
            body = fig.group(0)
            m = re.search(r"\\begin\{tikzpicture\}.*\\end\{tikzpicture\}", body, re.S)
            lab = re.search(r"\\label\{([^}]+)\}", body)
            if not m or not lab:
                continue
            n += 1
            name = f"fig{n:02d}"
            (BUILD / f"{name}.tex").write_text(STANDALONE_HEAD + m.group(0) + "\n\\end{document}\n", encoding="utf-8")
            subprocess.run([xelatex, "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"], cwd=BUILD,
                           check=True, stdout=subprocess.DEVNULL)
            doc = pymupdf.open(BUILD / f"{name}.pdf")
            doc[0].get_pixmap(dpi=220).save(BUILD / f"{name}.png")
            result[lab.group(1)] = f"{name}.png"
    return result


def flatten(figs: dict[str, str]) -> str:
    labels = labels_from_aux()
    cites = cite_numbers()
    parts = []
    for ch in CHAPTERS:
        text = read(f"chapters/{ch}.tex")
        if ch == "phuluc":
            letters = iter("ABCDEFGHIJ")
            text = re.sub(r"\\section\{([^}]*)\}", lambda m: "\\section*{" + next(letters) + ". " + m.group(1) + "}", text)
            text = re.sub(r"\\subsection\{", r"\\subsection*{", text)
        parts.append(text)
    for fm in ["loicamon", "phancong", "viettat"]:
        parts.insert(0, read(f"frontmatter/{fm}.tex")) if False else None
    body = "\n\n".join(parts)

    # Hình TikZ -> ảnh
    def fig_sub(m):
        block = m.group(0)
        lab = re.search(r"\\label\{([^}]+)\}", block)
        if lab and lab.group(1) in figs:
            cap = re.search(r"\\caption\{(.*)\}\s*(?:\\fignote\{.*\}\s*)?\\label", block, re.S)
            note = re.search(r"\\fignote\{(.*?)\}\s*\\label", block, re.S)
            caption = cap.group(1) if cap else ""
            return ("\\begin{figure}\n\\centering\n\\includegraphics[width=0.95\\textwidth]{"
                    + str((BUILD / figs[lab.group(1)]).as_posix()) + "}\n\\caption{" + caption + "}\n\\label{"
                    + lab.group(1) + "}\n\\end{figure}\n" + ("\n\\emph{" + note.group(1) + "}\n" if note else ""))
        return block

    body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", fig_sub, body, flags=re.S)

    # Số cho chú thích hình/bảng/đoạn mã (theo main.aux)
    def cap_number(env, prefix):
        def sub(m):
            block = m.group(0)
            lab = re.search(r"\\label\{([^}]+)\}", block)
            if not lab or lab.group(1) not in labels:
                return block
            return re.sub(r"\\caption\{", lambda _: "\\caption{" + f"{prefix} {labels[lab.group(1)]}. ", block, count=1)
        return sub

    body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", cap_number("figure", "Hình"), body, flags=re.S)
    body = re.sub(r"\\begin\{table\}.*?\\end\{table\}", cap_number("table", "Bảng"), body, flags=re.S)

    def lst_sub(m):
        opts = m.group(1)
        lab = re.search(r"label=\{?([^},\]]+)", opts)
        cap = re.search(r"caption=\{(.*?)\}", opts)
        num = labels.get(lab.group(1).strip(), "") if lab else ""
        head = f"\n\\emph{{Đoạn mã {num}. {cap.group(1) if cap else ''}}}\n\n" if cap else "\n"
        return head + "\\begin{verbatim}"

    body = re.sub(r"\\begin\{lstlisting\}\[(.*?)\]\n", lst_sub, body)
    body = body.replace("\\end{lstlisting}", "\\end{verbatim}")

    # \ref và \cite -> số
    body = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels.get(m.group(1), "??"), body)

    def cite_sub(m):
        nums = [cites.get(k.strip()) for k in m.group(1).split(",")]
        return "[" + ", ".join(str(x) for x in nums if x) + "]"

    body = re.sub(r"~?\\cite\{([^}]+)\}", lambda m: " " + cite_sub(m), body)

    # Macro riêng -> dạng Pandoc hiểu
    body = re.sub(r"\\nolinkurl\{([^}]*)\}", lambda m: "\\texttt{" + m.group(1).replace("_", "\\_") + "}", body)
    body = body.replace("\\IB{}", "Index Beast").replace("\\IB", "Index Beast")
    body = re.sub(r"\\unnumberedchapter\{([^}]*)\}", r"\\chapter*{\1}", body)
    body = re.sub(r"\\plainheading\{([^}]*)\}", r"\\section*{\1}", body)
    body = re.sub(r"\\tablenote\{(.*?)\}\n", r"\\emph{\1}\n", body)
    body = re.sub(r"\\resizebox\{[^}]*\}\{!\}\{%", "", body)
    body = body.replace("\\printbibliography[heading=bibintoc,title={TÀI LIỆU THAM KHẢO}]", "")
    body = re.sub(r"\\renewcommand\{\\the(section|table|lstlisting)\}\{[^\n]*\}\n", "", body)
    body = body.replace("\\ding{51}", "✓").replace("\\Large\\ding{110}", "")
    body = re.sub(r"\\toprule|\\midrule|\\bottomrule", r"\\hline", body)
    body = re.sub(r">\{\\(?:raggedright|centering)\\arraybackslash\}", "", body)

    head = r"""\documentclass{report}
\newcommand{\code}[1]{\texttt{#1}}
\begin{document}
"""
    return head + body + "\n\\end{document}\n"


def references_from_pdf() -> list[str]:
    doc = pymupdf.open(ROOT / "main.pdf")
    text = ""
    started = False
    for page in doc:
        t = page.get_text()
        if "TÀI LIỆU THAM KHẢO" in t and re.search(r"^\[1\]", t, re.M):
            started = True
        if started:
            if "PHỤ LỤC" in t.split("\n")[0:3] or (started and "Tổ chức mã nguồn" in t and "[" not in t[:20]):
                break
            text += t
    text = text.split("TÀI LIỆU THAM KHẢO", 1)[-1]
    text = re.sub(r"\n\d+\n", "\n", text)
    items = re.split(r"\n(?=\[\d+\])", "\n" + text)
    refs = [" ".join(x.split()) for x in items if re.match(r"\s*\[\d+\]", x)]
    return refs


def make_reference_docx(pandoc: str) -> Path:
    ref = BUILD / "reference.docx"
    subprocess.run([pandoc, "-o", str(ref), "--print-default-data-file", "reference.docx"], check=True)
    doc = Document(ref)
    for style_name, size, bold in [("Normal", 13, False), ("Body Text", 13, False), ("First Paragraph", 13, False),
                                   ("Heading 1", 16, True), ("Heading 2", 14, True), ("Heading 3", 13, True),
                                   ("Title", 18, True), ("Caption", 12, False), ("Image Caption", 12, False),
                                   ("Table Caption", 12, False), ("Compact", 12, False)]:
        try:
            st = doc.styles[style_name]
        except KeyError:
            continue
        st.font.name = "Times New Roman"
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman") if st.element.rPr is not None and st.element.rPr.rFonts is not None else None
        st.font.size = Pt(size)
        st.font.bold = bold
        if style_name.startswith("Heading"):
            from docx.shared import RGBColor
            st.font.color.rgb = RGBColor(0, 0, 0)
        pf = st.paragraph_format
        if style_name in ("Normal", "Body Text", "First Paragraph"):
            pf.line_spacing = 1.5
            pf.space_after = Pt(6)
            pf.first_line_indent = Cm(1.2)
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if style_name in ("Caption", "Image Caption", "Table Caption"):
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
            st.font.italic = True
        if style_name == "Heading 1":
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(3), Cm(3.5)
        s.left_margin, s.right_margin = Cm(3.5), Cm(2)
        s.page_height, s.page_width = Cm(29.7), Cm(21)
    doc.save(ref)
    return ref


def add_field(paragraph, instr: str):
    run = paragraph.add_run()
    for tag, text in (("begin", None), (None, instr), ("separate", None), (None, "Nhấn F9 để cập nhật mục lục"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
            run._r.append(el)
        elif text == instr:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = instr
            run._r.append(el)
        else:
            t = OxmlElement("w:t")
            t.text = text
            run._r.append(t)


def finish_docx(path: Path, refs: list[str]):
    doc = Document(path)
    body = doc.element.body
    first = body[0]

    def para_before(text="", size=13, bold=False, center=True, space_before=0, italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(space_before)
        if text:
            r = p.add_run(text)
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.italic = italic
            r.font.name = "Times New Roman"
        first.addprevious(p._p)
        return p

    meta = read("metadata.tex")
    get = lambda k: re.search(r"\\newcommand\{\\" + k + r"\}\{(.*)\}", meta).group(1).replace("\\#", "#")
    para_before("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG")
    para_before("KHOA CÔNG NGHỆ THÔNG TIN", bold=True)
    p = para_before(space_before=18)
    p.add_run().add_picture(str(ROOT / "assets" / "ictu_logo.png"), width=Cm(4))
    para_before("BÁO CÁO DỰ ÁN", 24, True, space_before=24)
    para_before("HỌC PHẦN XỬ LÝ NGÔN NGỮ TỰ NHIÊN", 19, True)
    para_before("Đề tài:", 13, True, center=False, space_before=24)
    for line in get("coverTitle").split("\\\\"):
        para_before(line, 16, True)
    para_before(f"Tên nhóm:\t{get('groupName')}", 14, True, center=False, space_before=18)
    para_before(f"Sinh viên thực hiện:\t{get('memberOne')}", 14, True, center=False)
    for k in ("memberTwo", "memberThree", "memberFour"):
        para_before(f"\t{get(k)}", 14, True, center=False)
    para_before(f"Giảng viên hướng dẫn:\t{get('instructorName')}", 14, True, center=False)
    p = para_before("THÁI NGUYÊN, NĂM 2026", 14, True, space_before=72)
    p.add_run().add_break(WD_BREAK.PAGE)

    # Phần đầu: lời cảm ơn, phân công, viết tắt được Pandoc chuyển riêng (front.docx) và chèn trước mục lục.
    p = para_before("MỤC LỤC", 16, True)
    add_field(para_before(center=False), 'TOC \\o "1-3" \\h \\z \\u')
    para_before().add_run().add_break(WD_BREAK.PAGE)

    # Tài liệu tham khảo: đặt trước phụ lục
    target = None
    for p in doc.paragraphs:
        if p.text.strip().upper() == "PHỤ LỤC" and p.style.name.startswith("Heading"):
            target = p
            break
    anchor = target._p if target is not None else None
    h = doc.add_paragraph("TÀI LIỆU THAM KHẢO", style="Heading 1")
    items = [h]
    for r in refs:
        q = doc.add_paragraph(r)
        q.paragraph_format.first_line_indent = Cm(-0.9)
        q.paragraph_format.left_indent = Cm(0.9)
        q.paragraph_format.line_spacing = 1.15
        q.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        items.append(q)
    if anchor is not None:
        for it in items:
            anchor.addprevious(it._p)

    doc.save(path)


def number_chapters(path: Path):
    """Pandoc ghi "1 TÊN" cho chương có số: đổi thành "CHƯƠNG 1. TÊN"; mục giữ dạng "1.1 Tên" -> "1.1. Tên"."""
    doc = Document(path)
    for p in doc.paragraphs:
        if not p.style.name.startswith("Heading") or not p.runs:
            continue
        m = re.match(r"^(\d+(?:\.\d+)*)\s+", p.text)
        if not m:
            continue
        num = m.group(1)
        label = f"CHƯƠNG {num}. " if p.style.name == "Heading 1" else f"{num}. "
        full = p.text[m.end():]
        for r in p.runs[1:]:
            r.text = ""
        p.runs[0].text = label + full
    doc.save(path)


def format_tables(path: Path):
    doc = Document(path)
    # Bảng: khung lưới, chữ 11
    for t in doc.tables:
        tblPr = t._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "4")
            el.set(qn("w:color"), "000000")
            borders.append(el)
        tblPr.append(borders)
        for row in t.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.first_line_indent = Cm(0)
                    para.paragraph_format.line_spacing = 1.0
                    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for run in para.runs:
                        run.font.size = Pt(11)
    doc.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pandoc", default="pandoc")
    ap.add_argument("--xelatex", default="xelatex")
    ap.add_argument("--output", default=str(ROOT / "BaoCao_NLP_IndexBeast.docx"))
    a = ap.parse_args()
    BUILD.mkdir(exist_ok=True)
    figs = build_figures(a.xelatex)
    flat = flatten(figs)
    (BUILD / "flat.tex").write_text(flat, encoding="utf-8")
    front = "\\documentclass{report}\n\\newcommand{\\code}[1]{\\texttt{#1}}\n\\begin{document}\n" + "\n".join(
        re.sub(r"\\unnumberedchapter\{([^}]*)\}", r"\\chapter*{\1}", read(f"frontmatter/{f}.tex"))
        for f in ("loicamon", "phancong", "viettat")) + "\n\\end{document}\n"
    front = re.sub(r">\{\\(?:raggedright|centering)\\arraybackslash\}", "", front)
    (BUILD / "front.tex").write_text(front, encoding="utf-8")
    ref = make_reference_docx(a.pandoc)
    out = Path(a.output)
    subprocess.run([a.pandoc, str(BUILD / "flat.tex"), "-f", "latex", "-o", str(out), f"--reference-doc={ref}",
                    "--number-sections", "--top-level-division=chapter"], check=True)
    number_chapters(out)
    subprocess.run([a.pandoc, str(BUILD / "front.tex"), "-f", "latex", "-o", str(BUILD / "front.docx"),
                    f"--reference-doc={ref}"], check=True)
    finish_docx(out, references_from_pdf())
    merge_front(out, BUILD / "front.docx")
    format_tables(out)
    print("Wrote", out)


def merge_front(main_path: Path, front_path: Path):
    """Chèn phần đầu (lời cảm ơn, phân công, viết tắt) sau trang bìa, trước mục lục."""
    main = Document(main_path)
    front = Document(front_path)
    toc_heading = next(p for p in main.paragraphs if p.text.strip() == "MỤC LỤC")
    for el in list(front.element.body):
        if el.tag.endswith("sectPr"):
            continue
        toc_heading._p.addprevious(el)
    br = main.add_paragraph()
    br.add_run().add_break(WD_BREAK.PAGE)
    toc_heading._p.addprevious(br._p)
    main.save(main_path)


if __name__ == "__main__":
    main()
