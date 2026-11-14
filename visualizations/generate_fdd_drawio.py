"""
Generates an editable Draw.io (.drawio) Functional Decomposition Diagram (FDD)
for CodeDEE following strict Software Engineering FDD standards:
- Level 0: System Root (1.0 CodeDEE System)
- Level 1: 6 Cohesive Functional Subsystems (1.1 - 1.6)
- Level 2: 24 Action-oriented Functional Modules (1.1.1 - 1.6.4)
- Orthogonal top-down tree layout (no arrowheads, verb-noun labels, color-coded tiers)
"""

import pathlib
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).parent.parent
VIZ_DIR = ROOT / "visualizations"
VIZ_DIR.mkdir(parents=True, exist_ok=True)
OUT_DRAWIO = VIZ_DIR / "CodeDEE_Functional_Decomposition_Diagram.drawio"

FDD_TREE = {
    "id": "root",
    "code": "0.0",
    "title": "CodeDEE System\n(Code Maintainability & Security Analysis and Repair)",
    "children": [
        {
            "id": "sub1",
            "code": "1.0",
            "title": "Code Ingestion &\nGraph Modeling",
            "color": "#1e3a8a",
            "border": "#3b82f6",
            "children": [
                ("1.1", "Normalize Source\nFile & Language"),
                ("1.2", "Parse Concrete\nSyntax Tree (CST)"),
                ("1.3", "Build Control-Flow\nGraph (CFG)"),
                ("1.4", "Build Data-Flow &\nCall Graphs (DFG/CG)"),
            ],
        },
        {
            "id": "sub2",
            "code": "2.0",
            "title": "Maintainability\nAnalysis",
            "color": "#065f46",
            "border": "#10b981",
            "children": [
                ("2.1", "Compute Function-Level\nMetrics (CC, Cog, PC, SLOC)"),
                ("2.2", "Compute File-Level\nMetrics (SLOC, Ce/Ca, CD)"),
                ("2.3", "Detect Duplicated\nCode Blocks"),
                ("2.4", "Evaluate ISO 25010\nMetric Thresholds"),
            ],
        },
        {
            "id": "sub3",
            "code": "3.0",
            "title": "Symbolic Security\nPre-Screening",
            "color": "#7c2d12",
            "border": "#f97316",
            "children": [
                ("3.1", "Identify Untrusted\nTaint Sources"),
                ("3.2", "Identify Sensitive\nExecution Sinks"),
                ("3.3", "Trace Source-to-Sink\nTaint Propagation"),
                ("3.4", "Extract Enclosing\nFunction Slice"),
            ],
        },
        {
            "id": "sub4",
            "code": "4.0",
            "title": "RAG & Neural Vulnerability\nVerification",
            "color": "#581c87",
            "border": "#a855f7",
            "children": [
                ("4.1", "Retrieve Top-K CWE Rules &\nSanitizers (ChromaDB RAG)"),
                ("4.2", "Verify Contextual\nSanitization (LLM Oracle)"),
                ("4.3", "Classify Confirmed CWE &\nCalibrate Contextual Risk"),
                ("4.4", "Generate Technical\nVulnerability Explanation"),
            ],
        },
        {
            "id": "sub5",
            "code": "5.0",
            "title": "Automated Repair &\nMulti-Gate Verification",
            "color": "#881337",
            "border": "#f43f5e",
            "children": [
                ("5.1", "Synthesize Candidate\nCode Patches (LLM)"),
                ("5.2", "Verify Syntax & Function\nInterface (Gates 1-2)"),
                ("5.3", "Verify Taint Neutralization &\nSAST Cleanliness (Gates 3, 5)"),
                ("5.4", "Verify Maintainability\nNon-Regression (Gate 4)"),
            ],
        },
        {
            "id": "sub6",
            "code": "6.0",
            "title": "Developer IDE\nInteraction (VS Code)",
            "color": "#0f766e",
            "border": "#14b8a6",
            "children": [
                ("6.1", "Monitor Workspace &\nEditor File Events"),
                ("6.2", "Render Maintainability &\nSecurity Diagnostics"),
                ("6.3", "Display Side-by-Side\nVerified Patch Diff"),
                ("6.4", "Apply Selected Patch\nto Source File"),
            ],
        },
    ],
}


def generate_drawio():
    mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="codedee-fdd", name="CodeDEE FDD")
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1600",
        dy="1000",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth="1650",
        pageHeight="950",
        background="#0f172a",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Root Node (Level 0)
    root_w, root_h = 340, 64
    root_x, root_y = 655, 40
    root_style = (
        "rounded=1;whiteSpace=wrap;html=1;fillColor=#1e293b;strokeColor=#f8fafc;"
        "strokeWidth=2;fontColor=#ffffff;fontFamily=Helvetica;fontSize=13;fontStyle=1;"
    )
    c_root = ET.SubElement(
        root,
        "mxCell",
        id="node_root",
        value=f"{FDD_TREE['code']} {FDD_TREE['title']}",
        style=root_style,
        vertex="1",
        parent="1",
    )
    ET.SubElement(
        c_root,
        "mxGeometry",
        x=str(root_x),
        y=str(root_y),
        width=str(root_w),
        height=str(root_h),
        attrib={"as": "geometry"},
    )

    # Level 1 & Level 2 positioning
    col_start_x = 50
    col_gap = 260
    sub_w, sub_h = 220, 60
    sub_y = 160

    leaf_w, leaf_h = 205, 58
    leaf_start_y = 270
    leaf_gap_y = 80

    for idx, sub in enumerate(FDD_TREE["children"]):
        sub_x = col_start_x + idx * col_gap
        sub_id = f"node_{sub['id']}"
        sub_style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={sub['color']};"
            f"strokeColor={sub['border']};strokeWidth=2;fontColor=#ffffff;"
            "fontFamily=Helvetica;fontSize=12;fontStyle=1;"
        )
        c_sub = ET.SubElement(
            root,
            "mxCell",
            id=sub_id,
            value=f"{sub['code']} {sub['title']}",
            style=sub_style,
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            c_sub,
            "mxGeometry",
            x=str(sub_x),
            y=str(sub_y),
            width=str(sub_w),
            height=str(sub_h),
            attrib={"as": "geometry"},
        )

        # Orthogonal Line from Root to Subsystem (No Arrowhead per FDD standard)
        edge_root_sub = ET.SubElement(
            root,
            "mxCell",
            id=f"edge_root_{sub['id']}",
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                "jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
                "entryX=0.5;entryY=0;entryDx=0;entryDy=0;endArrow=none;"
                "strokeColor=#94a3b8;strokeWidth=2;"
            ),
            edge="1",
            parent="1",
            source="node_root",
            target=sub_id,
        )
        ET.SubElement(edge_root_sub, "mxGeometry", relative="1", attrib={"as": "geometry"})

        # Level 2 Leaves (Vertical Comb / Bus under each Level 1 Subsystem)
        leaf_x = sub_x + 22
        for l_idx, (l_code, l_title) in enumerate(sub["children"]):
            leaf_y = leaf_start_y + l_idx * leaf_gap_y
            leaf_id = f"node_{sub['id']}_{l_idx}"
            leaf_style = (
                "rounded=1;whiteSpace=wrap;html=1;fillColor=#1e293b;"
                f"strokeColor={sub['border']};strokeWidth=1.5;fontColor=#f1f5f9;"
                "fontFamily=Helvetica;fontSize=11;fontStyle=0;"
            )
            c_leaf = ET.SubElement(
                root,
                "mxCell",
                id=leaf_id,
                value=f"<b>{l_code}</b> {l_title}",
                style=leaf_style,
                vertex="1",
                parent="1",
            )
            ET.SubElement(
                c_leaf,
                "mxGeometry",
                x=str(leaf_x),
                y=str(leaf_y),
                width=str(leaf_w),
                height=str(leaf_h),
                attrib={"as": "geometry"},
            )

            # Vertical drop-line from Level 1 left-bottom spine into Level 2 left edge
            edge_sub_leaf = ET.SubElement(
                root,
                "mxCell",
                id=f"edge_{sub['id']}_{l_idx}",
                style=(
                    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                    "jettySize=auto;html=1;exitX=0.04;exitY=1;exitDx=0;exitDy=0;"
                    "entryX=0;entryY=0.5;entryDx=0;entryDy=0;endArrow=none;"
                    f"strokeColor={sub['border']};strokeWidth=1.5;"
                ),
                edge="1",
                parent="1",
                source=sub_id,
                target=leaf_id,
            )
            ET.SubElement(edge_sub_leaf, "mxGeometry", relative="1", attrib={"as": "geometry"})

    xml_bytes = ET.tostring(mxfile, encoding="utf-8", xml_declaration=True)
    OUT_DRAWIO.write_bytes(xml_bytes)
    print(f"Saved Draw.io FDD file: {OUT_DRAWIO}")


if __name__ == "__main__":
    generate_drawio()
