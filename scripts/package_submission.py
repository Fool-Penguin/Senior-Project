"""
CodeDEE - Senior Project I Submission Package Generator
Collects all final verified submission deliverables into an organized turn-in folder:
submission_package_senior_project_1/
"""

import sys
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
TARGET_DIR = ROOT / "submission_package_senior_project_1"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

DOCS_DIR = ROOT / "docs" / "draft_paper"
VIZ_DIR = ROOT / "visualizations"
BENCH_DIR = ROOT / "benchmarks_full_scale" / "runs" / "revised_prompt" / "results" / "qwen2_5-coder_14b"

FILES_TO_COPY = [
    # 1. Official Reports
    (DOCS_DIR / "CodeDEE_Senior_Project_1_Proposal_Report.pdf", "CodeDEE_Senior_Project_1_Proposal_Report.pdf"),
    (DOCS_DIR / "CodeDEE_Senior_Project_1_Proposal_Report.docx", "CodeDEE_Senior_Project_1_Proposal_Report.docx"),
    (DOCS_DIR / "CodeDEE_Senior_Project_1_Proposal_Full_Draft.md", "CodeDEE_Senior_Project_1_Proposal_Full_Draft.md"),
    
    # 2. Presentation Deck
    (DOCS_DIR / "CodeDEE_Senior_Project_1_Presentation.pptx", "CodeDEE_Senior_Project_1_Presentation.pptx"),
    
    # 3. Interactive Web Tools
    (VIZ_DIR / "codedee_presentation_rehearsal_deck.html", "codedee_presentation_rehearsal_deck.html"),
    (VIZ_DIR / "codedee_evaluation_rag_dashboard.html", "codedee_evaluation_rag_dashboard.html"),
    
    # 4. Publication Figures (300 DPI)
    (VIZ_DIR / "figure_4_1_codedee_architecture.png", "figures/figure_4_1_codedee_architecture.png"),
    (VIZ_DIR / "figure_4_2_multigate_verifier.png", "figures/figure_4_2_multigate_verifier.png"),
    (VIZ_DIR / "cwe_languages_breakdown.png", "figures/cwe_languages_breakdown.png"),
    (BENCH_DIR / "confusion_matrix_qwen2_5-coder_14b.png", "figures/confusion_matrix_qwen2_5-coder_14b.png"),
]

README_CONTENT = """# CodeDEE: Senior Project I (Proposal Phase) Submission Package

**Faculty of Information and Communication Technology, Mahidol University**  
**Academic Year 2026**

---

## 1. Project Metadata
* **Project Title:** CodeDEE: An In-Editor Dual-Lens Engine for Continuous Maintainability and Neuro-Symbolic Security Program Repair
* **Project Category:** Software Engineering, Program Analysis, Cybersecurity & Applied Generative AI
* **Target Programming Languages:** Python, JavaScript, TypeScript
* **Student Investigators:**
  * Ongsa [LASTNAME] (Student ID: [STUDENT_ID])
  * Thanadon [LASTNAME] (Student ID: [STUDENT_ID])
  * [BROOK_NAME] [LASTNAME] (Student ID: [STUDENT_ID])
* **Project Advisor:** Assoc. Prof. Dr. Kookaip [ADVISOR_LASTNAME]

---

## 2. Package Contents & Deliverables

| File / Folder | Description |
| :--- | :--- |
| `CodeDEE_Senior_Project_1_Proposal_Report.pdf` | **Primary Deliverable:** Formatted Mahidol ICT Proposal Report (11 sections, 7 tables, 28 IEEE refs, Level 4 AI disclosure). |
| `CodeDEE_Senior_Project_1_Proposal_Report.docx` | Editable Microsoft Word document populated from the official 2026 `.dotx` template. |
| `CodeDEE_Senior_Project_1_Presentation.pptx` | 16-Slide Widescreen Proposal Defense Deck with full speaker scripts inside Speaker Notes. |
| `codedee_presentation_rehearsal_deck.html` | Standalone interactive rehearsal teleprompter with a 15-minute countdown timer and 12-question defense matrix. |
| `codedee_evaluation_rag_dashboard.html` | Interactive analytics dashboard visualizing empirical results across 9 models and 957 samples. |
| `figures/` | High-resolution (300 DPI) architectural diagrams (Figures 4.1 & 4.2) and benchmark confusion matrices. |

---

## 3. Key Empirical Findings (Senior Project I Benchmark)
* **Dataset Scale:** 957 verified vulnerability instances across 26 CWE classes (JS: 423, PY: 355, TS: 179).
* **Dense Knowledge Base:** 84 curated CWE remediation records embedded in ChromaDB via Sentence-T5.
* **Top Performing Model:** `qwen2.5-coder:14b` achieved **59.27% Forced-CWE accuracy** at **4.64s latency**, matching the 32B model while running on consumer GPUs within 16 GB VRAM.
* **In-Editor Performance:** Dual-lens parsing, graph generation, maintainability evaluation, and taint walking execute in **< 6 milliseconds** per file.

---

## 4. How to Run the Prototype Demo
To execute the live sub-second dual-lens demonstration in your terminal:
```bash
python scripts/demo_scan.py
```
To run the automated unit test suite (13/13 passing in 4.51s):
```bash
python -m pytest codedee/tests/
```
"""

def package_submission():
    print("=" * 70)
    print("CodeDEE: Packaging Senior Project I Deliverables")
    print(f"Target Directory: {TARGET_DIR}")
    print("=" * 70)
    
    (TARGET_DIR / "figures").mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    for src, rel_dest in FILES_TO_COPY:
        dest = TARGET_DIR / rel_dest
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            size_kb = dest.stat().st_size / 1024
            print(f"[+] Copied: {rel_dest:45s} ({size_kb:.1f} KB)")
            copied_count += 1
        else:
            print(f"[-] Warning: Source not found: {src}")
            
    # Write README
    readme_path = TARGET_DIR / "README.md"
    readme_path.write_text(README_CONTENT, encoding="utf-8")
    print(f"[+] Generated: README.md ({readme_path.stat().st_size / 1024:.1f} KB)")
    
    print("\n" + "=" * 70)
    print(f"SUCCESS: Packaging complete! {copied_count} files organized in {TARGET_DIR.name}")
    print("=" * 70)

if __name__ == "__main__":
    package_submission()
