# CodeDEE: Senior Project I (Proposal Phase) Submission Package

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
