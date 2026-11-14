"""
CodeDEE - Publication-Quality Architectural Diagram Generator
Generates high-resolution 300 DPI figures for the Senior Project Report and Presentation:
- Figure 4.1: CodeDEE Dual-Lens Architecture Pipeline
- Figure 4.2: Closed-Loop Multi-Gate APR Verifier Flowchart
"""

import sys
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
VIZ_DIR = ROOT / "visualizations"
VIZ_DIR.mkdir(parents=True, exist_ok=True)

# Academic Color Palette
COLOR_NAVY = "#0F172A"
COLOR_SLATE = "#1E293B"
COLOR_LIGHT_BG = "#F8FAFC"
COLOR_BORDER = "#CBD5E1"
COLOR_CYAN = "#0E7490"
COLOR_BLUE = "#2563EB"
COLOR_GREEN = "#16A34A"
COLOR_RED = "#DC2626"
COLOR_AMBER = "#D97706"

def generate_figure_4_1():
    """Generates Figure 4.1: CodeDEE Dual-Lens Architecture Pipeline Diagram."""
    fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
    ax.set_facecolor(COLOR_LIGHT_BG)
    fig.patch.set_facecolor(COLOR_LIGHT_BG)

    # Box Helper Function
    def draw_box(x, y, w, h, title, subtitle, bg_color, border_color, title_color="#FFFFFF", text_color="#1E293B"):
        # Shadow
        shadow = patches.FancyBboxPatch((x + 0.08, y - 0.08), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                        facecolor="#E2E8F0", edgecolor="none", zorder=1)
        ax.add_patch(shadow)
        # Main box
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg_color, edgecolor=border_color, linewidth=1.5, zorder=2)
        ax.add_patch(rect)
        # Title bar or Text
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", va="center", fontsize=11, fontweight="bold",
                color=title_color, zorder=3)
        if subtitle:
            ax.text(x + w / 2, y + h / 2 - 0.15, subtitle, ha="center", va="center", fontsize=9,
                    color=text_color, zorder=3, multialignment="center")

    def draw_arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(facecolor=COLOR_CYAN, edgecolor=COLOR_CYAN, width=1.5, headwidth=7, shrink=0.05),
                    zorder=4)
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + 0.15, label, ha="center", va="center", fontsize=8, fontweight="bold",
                    color=COLOR_CYAN, zorder=5, bbox=dict(boxstyle="square,pad=0.1", fc=COLOR_LIGHT_BG, ec="none"))

    # Stage 1: IDE & Tree-sitter
    draw_box(0.5, 4.8, 3.2, 2.4, "Stage 1: In-Editor Source Parsing",
             "Tree-sitter Concrete Syntax Tree (CST)\n• Python, JavaScript, TypeScript\n• Sub-millisecond incremental re-parsing\n• Resilient to in-progress syntax errors",
             "#FFFFFF", COLOR_BLUE, COLOR_BLUE)

    # Stage 2: Intermediate Graphs
    draw_box(4.5, 4.8, 3.2, 2.4, "Stage 2: Intermediate Graph Modeling",
             "In-Memory Graph Construction (NetworkX)\n• Control-Flow Graph (CFG)\n• Data-Flow Graph (DFG / Def-Use)\n• Inter-Procedural Call Graph (CG)",
             "#FFFFFF", COLOR_BLUE, COLOR_BLUE)

    draw_arrow(3.8, 6.0, 4.4, 6.0, "CST AST")

    # Lens 1: Maintainability Engine
    draw_box(8.5, 5.8, 5.0, 2.0, "Lens 1: Maintainability Engine (ISO/IEC 25010)",
             "8-Metric Software Quality Suite\n• McCabe Cyclomatic Complexity  • Campbell Cognitive Complexity\n• Sizing: SLOC, Halstead Volume, Maintainability Index (MI)\n• Modularity: Efferent (Ce), Afferent (Ca), Instability (I)",
             "#F0FDF4", COLOR_GREEN, COLOR_GREEN)

    draw_arrow(7.8, 6.6, 8.4, 6.6, "CFG + AST")

    # Lens 2: Security Audit Pipeline
    draw_box(8.5, 3.2, 5.0, 2.2, "Lens 2: Neuro-Symbolic Security Engine",
             "Deterministic Taint + Dense RAG + Local SLMs\n• Symbolic Taint Walker (26 CWE Classes)\n• ChromaDB Vector Store (84 Remediation Exemplars)\n• Local Neural Oracle (Ollama: Qwen2.5-Coder-14B)",
             "#FEF2F2", COLOR_RED, COLOR_RED)

    draw_arrow(7.8, 5.4, 8.4, 4.4, "DFG + CG")

    # Stage 4: Multi-Gate Verifier
    draw_box(4.5, 0.8, 4.0, 2.6, "Stage 4: Closed-Loop Multi-Gate APR Verifier",
             "4-Gate Verification Sandbox\nGate 1: AST Syntax Validity (Error nodes == 0)\nGate 2: Symbolic Taint Removal (Flow eliminated)\nGate 3: Regression Test Execution (Pass existing tests)\nGate 4: Maintainability Guard (ΔCC ≤ 0)",
             "#FFFBEB", COLOR_AMBER, COLOR_AMBER)

    draw_arrow(11.0, 3.1, 8.6, 2.0, "Candidate Fixes")

    # Stage 5 & 6: VS Code Integration
    draw_box(0.5, 0.8, 3.2, 2.6, "Stage 5 & 6: In-Editor Delivery",
             "VS Code Extension Client (LSP)\n• Real-Time Maintainability Highlights\n• Precise Vulnerability Squigglies\n• Verified 1-Click Interactive Patch Apply\n• Sub-Second Loopback IPC Server",
             "#F8FAFC", COLOR_NAVY, COLOR_NAVY)

    draw_arrow(4.4, 2.1, 3.8, 2.1, "Verified Patches")
    draw_arrow(11.0, 5.7, 2.1, 3.5, "Real-Time Metric Badges")

    ax.set_xlim(0, 14.0)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    plt.tight_layout()
    out_path = VIZ_DIR / "figure_4_1_codedee_architecture.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[+] Successfully generated Figure 4.1 at: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


def generate_figure_4_2():
    """Generates Figure 4.2: Closed-Loop Multi-Gate Verifier Flowchart."""
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)
    ax.set_facecolor(COLOR_LIGHT_BG)
    fig.patch.set_facecolor(COLOR_LIGHT_BG)

    def draw_node(x, y, w, h, text, color, shape_type="round"):
        if shape_type == "round":
            p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                       fc=color, ec=COLOR_BORDER, lw=1.5, zorder=2)
        elif shape_type == "diamond":
            p = patches.Polygon([[x + w/2, y], [x + w, y + h/2], [x + w/2, y + h], [x, y + h/2]],
                                fc=color, ec=COLOR_BORDER, lw=1.5, zorder=2)
        ax.add_patch(p)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=9, fontweight="bold",
                color="#FFFFFF" if color not in ["#FFFFFF", "#F8FAFC", "#FEF3C7"] else "#1E293B",
                multialignment="center", zorder=3)

    def draw_arrow(x1, y1, x2, y2, text=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(facecolor=COLOR_CYAN, edgecolor=COLOR_CYAN, width=1.5, headwidth=6, shrink=0.05),
                    zorder=4)
        if text:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx + 0.15, my, text, fontsize=8, fontweight="bold", color=COLOR_RED if text=="Fail" else COLOR_GREEN,
                    zorder=5)

    # Start: Neural Oracle Patch Generation
    draw_node(0.5, 2.7, 2.2, 1.4, "Local SLM Oracle\n(Qwen2.5-Coder-14B)\nGenerates Candidate Patches", COLOR_NAVY)

    # Gate 1: AST Syntax
    draw_node(3.2, 2.7, 1.8, 1.4, "Gate 1: AST Validity\nTree-sitter Syntax Check\n(Error nodes == 0)", "#1E3A8A")
    draw_arrow(2.7, 3.4, 3.2, 3.4)

    # Gate 2: Taint Removal
    draw_node(5.5, 2.7, 1.8, 1.4, "Gate 2: Taint Removal\nSymbolic Taint Walker\n(Sink flow severed)", "#0369A1")
    draw_arrow(5.0, 3.4, 5.5, 3.4, "Pass")

    # Gate 3: Regression Guard
    draw_node(7.8, 2.7, 1.8, 1.4, "Gate 3: Regression\nTest Sandbox Execution\n(Zero test regressions)", "#047857")
    draw_arrow(7.3, 3.4, 7.8, 3.4, "Pass")

    # Gate 4: Maintainability Guard
    draw_node(10.1, 2.7, 1.8, 1.4, "Gate 4: Maintainability\nISO/IEC 25010 Check\n(ΔCC ≤ 0 Complexity)", "#B45309")
    draw_arrow(9.6, 3.4, 10.1, 3.4, "Pass")

    # Discard Bin
    draw_node(5.5, 0.4, 4.0, 1.0, "REJECT & DISCARD PATCH\n(Re-sample from Oracle or Flag for Manual Review)", COLOR_RED)

    # Fail Arrows to Discard
    draw_arrow(4.1, 2.6, 5.5, 1.5, "Fail")
    draw_arrow(6.4, 2.6, 6.8, 1.5, "Fail")
    draw_arrow(8.7, 2.6, 8.2, 1.5, "Fail")
    draw_arrow(11.0, 2.6, 9.5, 1.5, "Fail")

    # Final Approved Patch Node
    draw_node(10.1, 5.0, 1.8, 1.2, "100% VERIFIED PATCH\nPresented to Developer\n(In-Editor 1-Click Diff)", COLOR_GREEN)
    draw_arrow(11.0, 4.2, 11.0, 4.9, "Pass All 4")

    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 6.8)
    ax.axis("off")

    plt.tight_layout()
    out_path = VIZ_DIR / "figure_4_2_multigate_verifier.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[+] Successfully generated Figure 4.2 at: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    generate_figure_4_1()
    generate_figure_4_2()
