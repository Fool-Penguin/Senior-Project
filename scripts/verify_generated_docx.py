import pathlib
import sys
import docx

sys.stdout.reconfigure(encoding="utf-8")

DOCX_PATH = pathlib.Path(__file__).parent.parent / "docs" / "draft_paper" / "CodeDEE_Senior_Project_1_Proposal_Report.docx"
doc = docx.Document(DOCX_PATH)

print(f"Generated DOCX Verification:")
print(f" - Total paragraphs: {len(doc.paragraphs)}")
print(f" - Total tables: {len(doc.tables)}")
print(f" - Total sections: {len(doc.sections)}")

headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading") or p.style.name.startswith("CHAP")]
print(f"\nHeadings in generated document ({len(headings)}):")
for h in headings[:25]:
    print(f"  * {h}")
print(f"  ... and {len(headings) - 25} more headings.")

print(f"\nTables in generated document ({len(doc.tables)}):")
for i, tbl in enumerate(doc.tables):
    hdr = [c.text.strip() for c in tbl.rows[0].cells]
    print(f"  * Table {i+1}: {len(tbl.rows)} rows x {len(tbl.columns)} cols | Header: {hdr[:3]}")

# Check References and AI statement at the end
ref_paras = [p.text for p in doc.paragraphs if p.style.name == "REF : Reference Num"]
print(f"\nReferences count: {len(ref_paras)}")
for r in ref_paras[:5]:
    print(f"  {r[:75]}...")

# Check AI statement
ai_paras = [p.text for p in doc.paragraphs if "Generative Artificial Intelligence" in p.text or "Student Verification" in p.text]
print(f"\nAI Statement detected: {len(ai_paras) > 0}")
