"""
Generates an editable Draw.io (.drawio) System Architecture & End-to-End Data Flow Diagram
for CodeDEE based on the team's draft, incorporating:
1. VS Code Extension Client (IDE Front-End) <-> LSP (Language Server Protocol / JSON-RPC) <-> CodeDEE Local Engine
2. Tree-sitter CST -> Graph Builder (CFG, DFG, Call Graph, Import Graph)
3. Dual-Lens Streams:
   - Maintainability Stream (8 ISO 25010 Metrics -> Exceed Threshold?)
   - Security Stream (Taint Walker -> Candidate Detected? -> Program Slicer + ChromaDB RAG -> LLM Neural Oracle -> Confirmed Flaw?)
4. On-Demand Auto-Fix & Multi-Gate Verification with Bounded Retry Loop (Max Retries <= 3, as advised by Advisor)
5. Return path back to VS Code Extension (Diagnostics & Diff Viewer -> Developer)
"""

import pathlib
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).parent.parent
VIZ_DIR = ROOT / "visualizations"
VIZ_DIR.mkdir(parents=True, exist_ok=True)
OUT_DRAWIO = VIZ_DIR / "CodeDEE_System_Architecture_Diagram.drawio"


def add_box(root, cid, label, x, y, w, h, fill="#1e293b", stroke="#64748b", font_color="#f8fafc", shape="rounded", parent="1", font_size=11, bold=False):
    if shape == "diamond":
        style = f"rhombus;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.8;fontColor={font_color};fontFamily=Helvetica;fontSize={font_size};"
    elif shape == "actor":
        style = f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor={fill};strokeColor={stroke};fontColor={font_color};fontFamily=Helvetica;fontSize={font_size};"
    elif shape == "cylinder":
        style = f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=10;fillColor={fill};strokeColor={stroke};strokeWidth=1.8;fontColor={font_color};fontFamily=Helvetica;fontSize={font_size};"
    elif shape == "container":
        style = f"swimlane;whiteSpace=wrap;html=1;startSize=28;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontColor={font_color};fontFamily=Helvetica;fontSize=12;fontStyle=1;rounded=1;arcSize=6;"
    else:
        fstyle = "1" if bold else "0"
        style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.8;fontColor={font_color};fontFamily=Helvetica;fontSize={font_size};fontStyle={fstyle};"

    cell = ET.SubElement(root, "mxCell", id=cid, value=label, style=style, vertex="1", parent=parent)
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})
    return cell


def add_edge(root, eid, src, tgt, label="", stroke="#94a3b8", dashed=False, exit_xy=None, entry_xy=None, waypoints=None):
    dash_str = "dashed=1;dashPattern=6 6;" if dashed else ""
    exit_str = f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;" if exit_xy else ""
    entry_str = f"entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;" if entry_xy else ""
    style = (
        f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        f"{exit_str}{entry_str}{dash_str}strokeColor={stroke};strokeWidth=1.8;"
        f"fontColor=#e2e8f0;fontFamily=Helvetica;fontSize=10;labelBackgroundColor=#0f172a;"
    )
    cell = ET.SubElement(root, "mxCell", id=eid, value=label, style=style, edge="1", parent="1", source=src, target=tgt)
    geom = ET.SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})
    if waypoints:
        arr = ET.SubElement(geom, "Array", attrib={"as": "points"})
        for wx, wy in waypoints:
            ET.SubElement(arr, "mxPoint", x=str(wx), y=str(wy))
    return cell


def generate_architecture_drawio():
    mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="codedee-sys-arch", name="CodeDEE System Architecture")
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1800",
        dy="1150",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth="1850",
        pageHeight="1100",
        background="#0f172a",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # =========================================================================
    # SWIMLANE / CONTAINER 1: VS Code Extension Client (IDE Front-End)
    # =========================================================================
    add_box(root, "lane_vscode", "1. VS Code Extension Client (IDE Front-End)", 40, 40, 290, 960, fill="#0f172a", stroke="#38bdf8", shape="container")

    add_box(root, "dev_actor", "Developer", 65, 110, 45, 80, fill="#1e293b", stroke="#38bdf8", shape="actor")
    add_box(root, "src_code", "<b>Source Code</b><br/>(Python, JS, TS)", 160, 120, 145, 60, fill="#1e293b", stroke="#38bdf8")
    add_box(root, "lsp_client", "<b>Event Listener &amp;<br/>LSP Client</b><br/>(JSON-RPC over stdio/HTTP)", 90, 240, 200, 65, fill="#1e3a8a", stroke="#60a5fa")
    add_box(root, "diag_panel", "<b>Diagnostics &amp; Findings UI</b><br/>• Maintainability Scores<br/>• CWE / Contextual Risk<br/>• Taint Path &amp; Explanation", 80, 560, 220, 95, fill="#1e293b", stroke="#38bdf8")
    add_box(root, "diff_viewer", "<b>Verified Patch Diff Viewer</b><br/>Side-by-Side Code Preview<br/>&amp; One-Click <b>[Apply Fix]</b>", 80, 820, 220, 85, fill="#064e3b", stroke="#10b981")

    # =========================================================================
    # SWIMLANE / CONTAINER 2: CodeDEE Local Analysis Server (Back-End)
    # =========================================================================
    add_box(root, "lane_backend", "2. CodeDEE Local Analysis Engine (Python Back-End Server)", 380, 40, 1420, 960, fill="#0f172a", stroke="#94a3b8", shape="container")

    # Stage 1 & 2: Parsing & Intermediate Graphs
    add_box(root, "treesitter", "<b>Tree-sitter Parser</b><br/>(Error-Tolerant Parser)", 420, 120, 155, 60, fill="#1e293b", stroke="#60a5fa")
    add_box(root, "cst_node", "<b>Concrete Syntax Tree</b><br/>(CST)", 620, 120, 160, 60, fill="#1e293b", stroke="#60a5fa")
    add_box(root, "graph_builder", "<b>Graph Builder</b><br/>(NetworkX Engine)", 830, 120, 155, 60, fill="#1e293b", stroke="#60a5fa")

    add_box(root, "cfg_box", "<b>Control-Flow Graph</b><br/>(CFG)", 1040, 75, 150, 50, fill="#1e293b", stroke="#94a3b8")
    add_box(root, "dfg_box", "<b>Data-Flow Graph</b><br/>(DFG)", 1040, 135, 150, 50, fill="#1e293b", stroke="#94a3b8")
    add_box(root, "cg_box", "<b>Call Graph</b><br/>(CG)", 1040, 195, 150, 50, fill="#1e293b", stroke="#94a3b8")

    # Stream 3A: Maintainability Engine
    add_box(root, "import_res", "<b>Import Resolver &amp;<br/>Import Graph</b><br/>(Coupling Ce / Ca)", 620, 270, 160, 65, fill="#064e3b", stroke="#10b981")
    add_box(root, "calc_maint", "<b>Maintainability Engine</b><br/>Compute 8 ISO 25010 Metrics<br/>(CC, Cognitive, PC, SLOC,<br/>Ce/Ca, Duplications, Comments)", 820, 265, 195, 80, fill="#064e3b", stroke="#10b981")
    add_box(root, "dec_thresh", "Exceed<br/>Threshold?", 860, 390, 115, 80, fill="#064e3b", stroke="#10b981", shape="diamond")

    # Stream 3B: Security Engine (Symbolic + RAG + Neural Oracle)
    add_box(root, "taint_walker", "<b>Symbolic Taint Walker</b><br/>(Source -> Sink Traversal<br/>&amp; Sanitizer Pre-Check)", 1255, 120, 185, 65, fill="#7c2d12", stroke="#f97316")
    add_box(root, "dec_cand", "Candidate<br/>Vulnerability<br/>Detected?", 1282, 225, 130, 90, fill="#7c2d12", stroke="#f97316", shape="diamond")
    add_box(root, "prog_slicer", "<b>Program Slicer</b><br/>(Extract Enclosing<br/>Source/Sink Functions)", 1255, 355, 185, 60, fill="#7c2d12", stroke="#f97316")
    add_box(root, "rag_kb", "<b>ChromaDB RAG<br/>Knowledge Base</b><br/>(84 CWE Rules, Base<br/>Severity &amp; Sanitizers)", 1520, 345, 175, 80, fill="#581c87", stroke="#a855f7", shape="cylinder")
    add_box(root, "llm_oracle", "<b>Neural Oracle (Local LLM)</b><br/>• Contextual Sanitizer Check<br/>• Confirm CWE vs CWE-NONE<br/>• Calibrate Contextual Risk<br/>• Generate Explanation", 1245, 465, 205, 90, fill="#581c87", stroke="#a855f7")
    add_box(root, "dec_confirmed", "Confirmed<br/>Security Flaw?", 1282, 590, 130, 85, fill="#581c87", stroke="#a855f7", shape="diamond")

    # Stage 4: Closed-Loop Auto-Fix & Multi-Gate Verifier (with Bounded Retry)
    add_box(root, "patch_synth", "<b>AI Patch Synthesizer (Local LLM)</b><br/>Generate Security Patch or<br/>Maintainability Refactoring", 990, 595, 215, 75, fill="#881337", stroke="#f43f5e")
    add_box(root, "mg_header", "<b>Multi-Gate In-Memory Verifier</b>", 1005, 705, 185, 42, fill="#881337", stroke="#f43f5e", bold=True)

    add_box(root, "gate1", "<b>Gate 1 &amp; 2:</b><br/>Syntax &amp; Interface<br/>Valid?", 1025, 770, 145, 80, fill="#1e293b", stroke="#f43f5e", shape="diamond", font_size=10)
    add_box(root, "gate2", "<b>Gate 3 &amp; 5:</b><br/>Vulnerability<br/>Neutralized?", 1220, 770, 145, 80, fill="#1e293b", stroke="#f43f5e", shape="diamond", font_size=10)
    add_box(root, "gate3", "<b>Gate 4:</b><br/>Maintainability<br/>Non-Regressed?", 1415, 770, 145, 80, fill="#1e293b", stroke="#f43f5e", shape="diamond", font_size=10)

    add_box(root, "retry_limit", "Retry Count<br/>&lt; Max (k=3)?", 1220, 900, 145, 75, fill="#78350f", stroke="#f59e0b", shape="diamond", font_size=10)

    # =========================================================================
    # EDGES & DATA FLOW CONNECTIONS
    # =========================================================================
    add_edge(root, "e_dev_src", "dev_actor", "src_code", "Writes / Saves")
    add_edge(root, "e_src_lsp", "src_code", "lsp_client")
    add_edge(root, "e_lsp_ts", "lsp_client", "treesitter", "LSP Request (Code)", stroke="#38bdf8", exit_xy=(1, 0.5), entry_xy=(0, 0.5))

    add_edge(root, "e_ts_cst", "treesitter", "cst_node")
    add_edge(root, "e_cst_gb", "cst_node", "graph_builder")

    # Graph Builder to CFG, DFG, CG
    add_edge(root, "e_gb_cfg", "graph_builder", "cfg_box", exit_xy=(1, 0.25), entry_xy=(0, 0.5))
    add_edge(root, "e_gb_dfg", "graph_builder", "dfg_box", exit_xy=(1, 0.5), entry_xy=(0, 0.5))
    add_edge(root, "e_gb_cg", "graph_builder", "cg_box", exit_xy=(1, 0.75), entry_xy=(0, 0.5))

    # Maintainability Stream (3A)
    add_edge(root, "e_cst_imp", "cst_node", "import_res", dashed=True, exit_xy=(0.5, 1), entry_xy=(0.5, 0))
    add_edge(root, "e_cst_maint", "cst_node", "calc_maint", exit_xy=(0.75, 1), entry_xy=(0.25, 0))
    add_edge(root, "e_cfg_maint", "cfg_box", "calc_maint", exit_xy=(0.5, 1), entry_xy=(0.75, 0), waypoints=[(1115, 250), (966, 250)])
    add_edge(root, "e_imp_maint", "import_res", "calc_maint", exit_xy=(1, 0.5), entry_xy=(0, 0.5))
    add_edge(root, "e_maint_thresh", "calc_maint", "dec_thresh")

    # Security Stream (3B)
    add_edge(root, "e_cfg_tw", "cfg_box", "taint_walker", exit_xy=(1, 0.5), entry_xy=(0, 0.25))
    add_edge(root, "e_dfg_tw", "dfg_box", "taint_walker", exit_xy=(1, 0.5), entry_xy=(0, 0.5))
    add_edge(root, "e_cg_tw", "cg_box", "taint_walker", exit_xy=(1, 0.5), entry_xy=(0, 0.75))

    add_edge(root, "e_tw_cand", "taint_walker", "dec_cand")
    add_edge(root, "e_cand_slicer", "dec_cand", "prog_slicer", "Yes", stroke="#f97316")
    add_edge(root, "e_slicer_rag", "prog_slicer", "rag_kb", "Query CWE / Sink", dashed=True, stroke="#a855f7", exit_xy=(1, 0.5), entry_xy=(0, 0.5))
    add_edge(root, "e_slicer_oracle", "prog_slicer", "llm_oracle", "Code Slice &amp; Taint Path")
    add_edge(root, "e_rag_oracle", "rag_kb", "llm_oracle", "Top-K Rules &amp; Sanitizers", stroke="#a855f7", exit_xy=(0.5, 1), entry_xy=(1, 0.5))
    add_edge(root, "e_oracle_conf", "llm_oracle", "dec_confirmed")

    # Clean / Findings Reporting to VS Code Diagnostics Panel
    add_edge(root, "e_thresh_clean", "dec_thresh", "diag_panel", "Report Metrics", stroke="#10b981", exit_xy=(0, 0.5), entry_xy=(1, 0.25), waypoints=[(520, 430), (520, 585)])
    add_edge(root, "e_cand_no", "dec_cand", "diag_panel", "No (Clean)", stroke="#10b981", exit_xy=(0, 0.5), entry_xy=(1, 0.1), waypoints=[(1220, 270), (1220, 500), (520, 500), (520, 570)])
    add_edge(root, "e_conf_report", "dec_confirmed", "diag_panel", "LSP Diagnostics (CWE / Safe)", stroke="#a855f7", exit_xy=(0, 1), entry_xy=(1, 0.5), waypoints=[(1282, 665), (520, 665), (520, 608)])

    # Triggering AI Patch Synthesizer (Maintainability Refactor or Security Fix)
    add_edge(root, "e_thresh_fix", "dec_thresh", "patch_synth", "Yes (Need Refactor)", stroke="#f43f5e", exit_xy=(0.5, 1), entry_xy=(0, 0.5), waypoints=[(918, 632)])
    add_edge(root, "e_conf_fix", "dec_confirmed", "patch_synth", "Yes (Need Security Fix)", stroke="#f43f5e", exit_xy=(0, 0.5), entry_xy=(1, 0.5))

    # Multi-Gate Verification Flow
    add_edge(root, "e_synth_mg", "patch_synth", "mg_header")
    add_edge(root, "e_mg_g1", "mg_header", "gate1")
    add_edge(root, "e_g1_g2", "gate1", "gate2", "Yes", stroke="#10b981")
    add_edge(root, "e_g2_g3", "gate2", "gate3", "Yes (Clean)", stroke="#10b981")

    # Failed Gates -> Bounded Retry Check (k < 3)
    add_edge(root, "e_g1_fail", "gate1", "retry_limit", "No", stroke="#f59e0b", exit_xy=(0.5, 1), entry_xy=(0, 0.5), waypoints=[(1097, 938)])
    add_edge(root, "e_g2_fail", "gate2", "retry_limit", "No (Flaw Remains)", stroke="#f59e0b", exit_xy=(0.5, 1), entry_xy=(0.5, 0))
    add_edge(root, "e_g3_fail", "gate3", "retry_limit", "No (Regressed)", stroke="#f59e0b", exit_xy=(0.5, 1), entry_xy=(1, 0.5), waypoints=[(1487, 938)])

    # Retry Loop back to AI Patch Synthesizer
    add_edge(root, "e_retry_yes", "retry_limit", "patch_synth", "Yes (Retune Prompt w/ Gate Error)", stroke="#f59e0b", exit_xy=(0, 0.5), entry_xy=(0, 0.75), waypoints=[(950, 938), (950, 650)])
    add_edge(root, "e_retry_no", "retry_limit", "diag_panel", "No (Max Retries Reached -> Warn Only)", dashed=True, stroke="#ef4444", exit_xy=(0.5, 1), entry_xy=(0.5, 1), waypoints=[(1292, 990), (460, 990), (460, 680), (190, 680)])

    # Passed All Gates -> VS Code Verified Patch Diff Viewer -> Developer
    add_edge(root, "e_g3_pass", "gate3", "diff_viewer", "Yes (100% Verified Patch via LSP)", stroke="#10b981", exit_xy=(1, 0.5), entry_xy=(1, 0.5), waypoints=[(1620, 810), (1620, 862)])
    add_edge(root, "e_diff_dev", "diff_viewer", "dev_actor", "Reviews &amp; Clicks [Apply]", stroke="#10b981", exit_xy=(0, 0.5), entry_xy=(0.5, 1), waypoints=[(45, 862), (45, 230), (88, 230)])

    xml_bytes = ET.tostring(mxfile, encoding="utf-8", xml_declaration=True)
    OUT_DRAWIO.write_bytes(xml_bytes)
    print(f"Saved System Architecture Draw.io file: {OUT_DRAWIO}")


if __name__ == "__main__":
    generate_architecture_drawio()
