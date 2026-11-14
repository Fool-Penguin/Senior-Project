"""
CodeDEE: Senior Project Proposal Report Generator
Injects the complete 6 chapters, tables, references, and front matter from
CodeDEE_Senior_Project_1_Proposal_Full_Draft.md into the official Mahidol ICT
Word Template (ICT_Final_SPDocument_MS_Word_Template_2026.dotx).
"""

import io
import os
import pathlib
import re
import sys
import zipfile

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).parent.parent
SENIOR_DOC_DIR = ROOT / "Senior_Documentation"
DRAFT_DIR = ROOT / "docs" / "draft_paper"
TEMPLATE_PATH = SENIOR_DOC_DIR / "ICT_Final_SPDocument_MS_Word_Template_2026.dotx"
DRAFT_MD_PATH = DRAFT_DIR / "CodeDEE_Senior_Project_1_Proposal_Full_Draft.md"
OUTPUT_DOCX_PATH = DRAFT_DIR / "CodeDEE_Senior_Project_1_Proposal_Report.docx"


def load_template_as_docx(dotx_path: pathlib.Path) -> docx.Document:
    """Load a Word .dotx template into an in-memory .docx Document object."""
    with zipfile.ZipFile(dotx_path, "r") as z_in:
        docx_bytes = io.BytesIO()
        with zipfile.ZipFile(docx_bytes, "w") as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    content = content.replace(
                        b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
                        b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                    )
                z_out.writestr(item, content)

    docx_bytes.seek(0)
    return docx.Document(docx_bytes)


def add_markdown_inlines(paragraph, text: str):
    """Parses **bold**, *italic*, and `code` inline tokens."""
    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("*") and token.endswith("*"):
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(30, 30, 30)
        else:
            paragraph.add_run(token)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Sets cell internal padding in dxa."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_shading(cell, color_hex="F2F2F2"):
    """Sets background shading of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)


def style_academic_table(table):
    """Applies clean horizontal academic borders (APA/IEEE standard)."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>\n'
        f'  <w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>\n'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f"</w:tblBorders>"
    )
    tblPr.append(borders)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER


def build_word_table_from_markdown(doc, table_md_rows, target_p):
    """Converts a Markdown table string into a styled Word table inserted before target_p."""
    parsed_rows = []
    for r in table_md_rows:
        stripped = r.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            stripped = stripped[1:-1]
        cells = [c.strip() for c in stripped.split("|")]
        if not all(re.match(r"^:?-+:?$", c) for c in cells):
            parsed_rows.append(cells)

    if not parsed_rows:
        return

    num_rows = len(parsed_rows)
    num_cols = max(len(r) for r in parsed_rows)

    table = doc.add_table(rows=num_rows, cols=num_cols)
    style_academic_table(table)

    for row_idx, row_data in enumerate(parsed_rows):
        row = table.rows[row_idx]
        is_header = row_idx == 0
        for col_idx in range(num_cols):
            cell = row.cells[col_idx]
            cell_text = row_data[col_idx] if col_idx < len(row_data) else ""
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)

            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.0

            if is_header:
                set_cell_shading(cell, "EAEAEA")
                run = p.add_run(cell_text)
                run.bold = True
                run.font.name = "Times New Roman"
                run.font.size = Pt(10)
            else:
                add_markdown_inlines(p, cell_text)
                for run in p.runs:
                    if not run.font.name:
                        run.font.name = "Times New Roman"
                    if not run.font.size:
                        run.font.size = Pt(9.5)

    # Insert before target paragraph
    target_p._p.addprevious(table._tbl)


def render_content_blocks(doc, lines, target_p, is_references_section=False):
    """Renders structured Markdown lines into Word before target_p."""
    idx = 0
    n = len(lines)

    while idx < n:
        line = lines[idx].rstrip()

        # Empty line
        if not line:
            idx += 1
            continue

        # Page breaks
        if "<div style='page-break-after: always;'></div>" in line:
            p = target_p.insert_paragraph_before()
            p.add_run().add_break(WD_BREAK.PAGE)
            idx += 1
            continue

        # Chapter Number
        if re.match(r"^# CHAPTER \d+", line):
            p = target_p.insert_paragraph_before(line.replace("# ", "").strip(), style="CHAP : Number")
            idx += 1
            continue

        # Level 1 Heading (e.g. # INTRODUCTION)
        if line.startswith("# ") and not line.startswith("# CHAPTER"):
            p = target_p.insert_paragraph_before(line.replace("# ", "").strip(), style="Heading 1")
            idx += 1
            continue

        # Level 2 Heading (e.g. ## 1.1 Problem Statement)
        if line.startswith("## "):
            p = target_p.insert_paragraph_before(line.replace("## ", "").strip(), style="Heading 2")
            idx += 1
            continue

        # Level 3 Heading (e.g. ### 1.1.1 The Pre-Commit...)
        if line.startswith("### "):
            p = target_p.insert_paragraph_before(line.replace("### ", "").strip(), style="Heading 3")
            idx += 1
            continue

        # Level 4 Heading (e.g. #### ...)
        if line.startswith("#### "):
            p = target_p.insert_paragraph_before(line.replace("#### ", "").strip(), style="Heading 4")
            idx += 1
            continue

        # Table Caption & Table Block
        if line.startswith("Table ") and ":" in line:
            p_cap = target_p.insert_paragraph_before(line.strip(), style="TBL : Caption")
            p_cap.paragraph_format.space_before = Pt(8)
            p_cap.paragraph_format.space_after = Pt(4)
            idx += 1

            # Check if following lines are markdown table
            table_lines = []
            while idx < n and (lines[idx].strip().startswith("|") or not lines[idx].strip()):
                if lines[idx].strip().startswith("|"):
                    table_lines.append(lines[idx].strip())
                idx += 1

            if table_lines:
                build_word_table_from_markdown(doc, table_lines, target_p)
                p_spacer = target_p.insert_paragraph_before()
                p_spacer.paragraph_format.space_after = Pt(6)
            continue

        # Markdown Table without explicit Table X.Y caption line
        if line.startswith("|"):
            table_lines = []
            while idx < n and (lines[idx].strip().startswith("|") or not lines[idx].strip()):
                if lines[idx].strip().startswith("|"):
                    table_lines.append(lines[idx].strip())
                idx += 1
            if table_lines:
                build_word_table_from_markdown(doc, table_lines, target_p)
                p_spacer = target_p.insert_paragraph_before()
                p_spacer.paragraph_format.space_after = Pt(6)
            continue

        # Bullet List Items
        if line.startswith("* ") or line.startswith("- "):
            clean_item = line[2:].strip()
            p = target_p.insert_paragraph_before(style="List Paragraph")
            add_markdown_inlines(p, clean_item)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            idx += 1
            continue

        # Numbered List Items
        num_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if num_match:
            num = num_match.group(1)
            item_text = num_match.group(2)
            if is_references_section:
                try:
                    p = target_p.insert_paragraph_before(style="REF : Reference Num")
                except Exception:
                    p = target_p.insert_paragraph_before(style="List Paragraph")
                add_markdown_inlines(p, f"{num}.\t{item_text}")
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.15
            else:
                p = target_p.insert_paragraph_before(style="List Paragraph")
                add_markdown_inlines(p, f"{num}.  {item_text}")
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.25
            idx += 1
            continue

        # Code Block
        if line.startswith("```"):
            idx += 1
            code_lines = []
            while idx < n and not lines[idx].startswith("```"):
                code_lines.append(lines[idx])
                idx += 1
            idx += 1  # Skip closing ```

            code_text = "\n".join(code_lines)
            p = target_p.insert_paragraph_before(code_text, style="CODE : TXT")
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Inches(0.4)
            continue

        # Visual / Figure Callout with embedded high-resolution graphics
        if "Figure " in line and any(f"Figure {k}" in line for k in ["4.1", "4.2", "5.1"]):
            img_path = None
            img_width = Inches(6.0)
            if "Figure 4.1" in line:
                img_path = ROOT / "visualizations" / "figure_4_1_codedee_architecture.png"
                img_width = Inches(6.0)
            elif "Figure 4.2" in line:
                img_path = ROOT / "visualizations" / "figure_4_2_multigate_verifier.png"
                img_width = Inches(5.8)
            elif "Figure 5.1" in line:
                img_path = ROOT / "benchmarks_full_scale" / "runs" / "revised_prompt" / "results" / "qwen2_5-coder_14b" / "confusion_matrix_qwen2_5-coder_14b.png"
                img_width = Inches(5.2)

            if img_path and img_path.exists():
                p_img = target_p.insert_paragraph_before()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(4)
                run = p_img.add_run()
                run.add_picture(str(img_path), width=img_width)

            clean_caption = line.strip().strip("*[]_")
            p = target_p.insert_paragraph_before(clean_caption, style="IMG : Caption")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(12)
            idx += 1
            continue

        if line.startswith("[Figure ") or line.startswith("Figure "):
            p = target_p.insert_paragraph_before(line.strip().strip("*[]_"), style="IMG : Caption")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(8)
            idx += 1
            continue

        # Standard Paragraph Text
        p = target_p.insert_paragraph_before(style="TXT : Paragraph")
        add_markdown_inlines(p, line)
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.first_line_indent = Inches(0.5)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        idx += 1


def populate_full_report():
    print(f"Loading template: {TEMPLATE_PATH}")
    doc = load_template_as_docx(TEMPLATE_PATH)
    print("Template loaded successfully!")

    print(f"Reading master full draft: {DRAFT_MD_PATH}")
    content = DRAFT_MD_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Identify major section boundaries in the markdown text
    markers = {
        "cover": 2,
        "ack": 32,
        "abstract": 46,
        "ch1": 113,
        "ch2": 178,
        "ch3": 311,
        "ch4": 392,
        "ch5": 559,
        "ch6": 680,
        "refs": 733,
        "ai": 750,
        "end": len(lines),
    }

    for i, line in enumerate(lines):
        l = line.strip()
        if l.startswith("## ACKNOWLEDGEMENTS"):
            markers["ack"] = i
        elif l.startswith("## ABSTRACT"):
            markers["abstract"] = i
        elif l.startswith("# CHAPTER 1"):
            markers["ch1"] = i
        elif l.startswith("# CHAPTER 2"):
            markers["ch2"] = i
        elif l.startswith("# CHAPTER 3"):
            markers["ch3"] = i
        elif l.startswith("# CHAPTER 4"):
            markers["ch4"] = i
        elif l.startswith("# CHAPTER 5"):
            markers["ch5"] = i
        elif l.startswith("# CHAPTER 6"):
            markers["ch6"] = i
        elif l.startswith("# REFERENCES"):
            markers["refs"] = i
        elif l.startswith("# AI USAGE"):
            markers["ai"] = i

    print("Found section boundaries:")
    for k, v in markers.items():
        print(f"  {k:10s} -> line {v}")

    # 1. Update Cover Page
    print("\n[1/6] Updating Cover Page...")
    doc.paragraphs[1].text = "CODEDEE: AN IN-EDITOR DUAL-LENS ENGINE FOR CONTINUOUS"
    doc.paragraphs[2].text = "MAINTAINABILITY AND NEURO-SYMBOLIC SECURITY PROGRAM REPAIR"
    doc.paragraphs[7].text = "Mr. Ongsa [LASTNAME]\t[STUDENT_ID]"
    doc.paragraphs[8].text = "Mr. Thanadon [LASTNAME]\t[STUDENT_ID]"
    doc.paragraphs[9].text = "Mr. [BROOK_NAME] [LASTNAME]\t[STUDENT_ID]"
    doc.paragraphs[15].text = "Assoc. Prof. Dr. Kookaip [ADVISOR_LASTNAME]"
    doc.paragraphs[17].text = ""
    doc.paragraphs[18].text = ""
    doc.paragraphs[33].text = "2026"

    # 2. Update Acknowledgements
    print("[2/6] Updating Acknowledgements...")
    doc.paragraphs[36].text = "ACKNOWLEDGEMENTS"
    p_ack = doc.paragraphs[37]
    p_ack.text = (
        "We express our profound and sincere gratitude to our senior project advisor, "
        "Assoc. Prof. Dr. Kookaip, for his invaluable guidance, technical insight, and steadfast support "
        "throughout the conceptualization, system architecture design, and empirical evaluation of CodeDEE. "
        "His rigorous critical feedback and high academic standards were instrumental in shaping our "
        "neuro-symbolic methodology and experimental framework.\n\n"
        "We also extend our sincere appreciation to the faculty members of the Faculty of Information and "
        "Communication Technology, Mahidol University, for providing the foundational academic education, "
        "research environment, and computing resources necessary to conduct this work.\n\n"
        "Finally, we thank our families and peers for their continuous encouragement and patience throughout "
        "the intensive development and experimental execution of Senior Project I."
    )
    p_ack.style = "TXT : Paragraph"
    doc.paragraphs[38].text = "Mr. Ongsa [LASTNAME]\nMr. Thanadon [LASTNAME]\nMr. [BROOK_NAME] [LASTNAME]"
    doc.paragraphs[38].style = "ACK : Name List"

    # 3. Update Abstract
    print("[3/6] Updating Abstract...")
    doc.paragraphs[45].text = "Mr. Ongsa [LASTNAME]\t ITCS/B"
    doc.paragraphs[46].text = "Mr. Thanadon [LASTNAME]\t ITCS/B"
    doc.paragraphs[47].text = "Mr. [BROOK_NAME] [LASTNAME]\t ITCS/B"
    doc.paragraphs[51].text = "PROJECT ADVISOR: Assoc. Prof. Dr. Kookaip [ADVISOR_LASTNAME]"
    doc.paragraphs[52].text = "PROJECT co-ADVISOR: -"
    doc.paragraphs[54].text = "ABSTRACT"

    abstract_body = (
        "Modern web software development relies heavily on continuous integration and rapid release cycles across "
        "Python, JavaScript, and TypeScript. However, modern developers face an acute 'pre-commit visibility gap' and "
        "debilitating static analysis alert fatigue: existing static application security testing (SAST) and maintainability "
        "linters generate unranked alerts with false-positive rates frequently exceeding 30%, while offering zero actionable, "
        "context-aware repairs. Conversely, emerging Large Language Model (LLM) code assistants produce hallucinated, non-compilable, "
        "or syntactically malformed patches when ungrounded by symbolic program analysis.\n\n"
        "To bridge this divide, this capstone project presents CodeDEE, an in-editor dual-lens analysis and neuro-symbolic automated program "
        "repair engine. CodeDEE operates directly within the developer's pre-commit workflow. Lens 1 evaluates software maintainability "
        "under ISO/IEC 25010 by extracting Concrete Syntax Trees (CST) via tree-sitter to compute an eight-metric maintainability suite—including "
        "McCabe Cyclomatic Complexity, Campbell Cognitive Complexity, Efferent/Afferent Coupling, and Halstead Volume—at sub-second latency. "
        "Lens 2 introduces a neuro-symbolic security audit pipeline: a symbolic AST taint walker detects potential sources and sinks across 26 "
        "Common Weakness Enumeration (CWE) classes and queries a dense ChromaDB vector knowledge base populated with verified CWE remediation patterns. "
        "The retrieved context grounds local Small Language Models (SLMs) running private on-device inference via Ollama.\n\n"
        "In Senior Project I (Semester 1), we curated and cleaned a 957-sample empirical benchmark across JavaScript (423), Python (355), and "
        "TypeScript (179) spanning 26 vulnerability classes, and systematically evaluated nine local SLMs across two operational regimes: "
        "Forced-CWE classification and Standard Triage. Under forced classification, Qwen2.5-Coder-14B achieved top-tier accuracy (59.27%) at 4.64s latency, "
        "matching the 32B model while running on consumer GPUs within 16 GB VRAM. Under realistic standard triage, conservative models exhibited 32–37% "
        "CWE-NONE triage responses due to single-file taint truncation, demonstrating the critical necessity of inter-procedural call graphs planned "
        "for Semester 2. This report establishes the theoretical foundations, architectural methodology, empirical benchmark, and execution plan "
        "for the complete CodeDEE engine."
    )
    doc.paragraphs[56].text = abstract_body
    doc.paragraphs[87].text = (
        "KEYWORDS : Software Maintainability / Concrete Syntax Tree / Neuro-Symbolic Program Repair / "
        "Small Language Models / Static Taint Analysis / Common Weakness Enumeration / Retrieval-Augmented Generation / Developer Tooling"
    )

    # 4. Map Anchors and Remove Dummy Body Paragraphs
    print("[4/6] Collecting section anchors and clearing dummy paragraphs...")
    to_remove = []
    anchors = []

    for p in doc.paragraphs[116:]:
        has_sect = p._p.pPr is not None and len(p._p.pPr.xpath("./w:sectPr")) > 0
        if has_sect:
            anchors.append(p)
            p.text = ""  # Keep sectPr intact
        else:
            to_remove.append(p)

    print(f"Found {len(anchors)} section anchors. Removing {len(to_remove)} dummy template paragraphs...")
    for p in to_remove:
        p._p.getparent().remove(p._p)

    # 5. Render Each Chapter into Its Respective Section
    print("[5/6] Injecting full chapter content, tables, and back matter...")

    # Anchor 0: Chapter 1 & Chapter 2 (Section 3)
    print("  -> Injecting Chapter 1 & 2 before Anchor 0...")
    ch1_lines = lines[markers["ch1"] : markers["ch2"]]
    render_content_blocks(doc, ch1_lines, anchors[0], is_references_section=False)

    p_break = anchors[0].insert_paragraph_before()
    p_break.add_run().add_break(WD_BREAK.PAGE)

    ch2_lines = lines[markers["ch2"] : markers["ch3"]]
    render_content_blocks(doc, ch2_lines, anchors[0], is_references_section=False)

    # Anchor 1: Chapter 3 (Section 4)
    print("  -> Injecting Chapter 3 before Anchor 1...")
    ch3_lines = lines[markers["ch3"] : markers["ch4"]]
    render_content_blocks(doc, ch3_lines, anchors[1], is_references_section=False)

    # Anchor 2: Chapter 4 (Section 5)
    print("  -> Injecting Chapter 4 before Anchor 2...")
    ch4_lines = lines[markers["ch4"] : markers["ch5"]]
    render_content_blocks(doc, ch4_lines, anchors[2], is_references_section=False)

    # Anchor 3: Chapter 5 (Section 6)
    print("  -> Injecting Chapter 5 before Anchor 3...")
    ch5_lines = lines[markers["ch5"] : markers["ch6"]]
    render_content_blocks(doc, ch5_lines, anchors[3], is_references_section=False)

    # Anchor 4: Chapter 6 (Section 7)
    print("  -> Injecting Chapter 6 before Anchor 4...")
    ch6_lines = lines[markers["ch6"] : markers["refs"]]
    render_content_blocks(doc, ch6_lines, anchors[4], is_references_section=False)

    # Anchor 5: References (Section 8)
    print("  -> Injecting References before Anchor 5...")
    p_ref_title = anchors[5].insert_paragraph_before("REFERENCES", style="BIO : Title")
    p_ref_title.paragraph_format.space_before = Pt(24)
    p_ref_title.paragraph_format.space_after = Pt(18)
    refs_lines = lines[markers["refs"] + 1 : markers["ai"]]
    render_content_blocks(doc, refs_lines, anchors[5], is_references_section=True)

    # Anchor 6: AI Usage Statement (Section 9)
    print("  -> Injecting AI Usage Statement before Anchor 6...")
    p_ai_title = anchors[6].insert_paragraph_before("AI USAGE ACKNOWLEDGMENT STATEMENT", style="BIO : Title")
    p_ai_title.paragraph_format.space_before = Pt(24)
    p_ai_title.paragraph_format.space_after = Pt(18)
    ai_lines = lines[markers["ai"] + 1 : markers["end"]]
    render_content_blocks(doc, ai_lines, anchors[6], is_references_section=False)

    # 6. Save Output Document
    print(f"\n[6/6] Saving populated report to: {OUTPUT_DOCX_PATH}")
    doc.save(OUTPUT_DOCX_PATH)
    file_size_kb = OUTPUT_DOCX_PATH.stat().st_size / 1024
    print(f"SUCCESS: Senior Project Report successfully generated! File size: {file_size_kb:.1f} KB")


if __name__ == "__main__":
    populate_full_report()
