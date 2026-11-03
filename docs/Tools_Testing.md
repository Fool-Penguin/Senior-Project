# คู่มือการรันคำสั่งทดสอบเครื่องมือแต่ละตัว (Tools Testing Guide)

คู่มือนี้รวบรวมคำสั่งจริง (CLI Commands) สำหรับรันสแกนและทดสอบ Benchmark เปรียบเทียบเครื่องมือทั้ง 5 ค่ายบนเครื่องของคุณ พร้อมไฟล์โค้ดตัวอย่างที่เตรียมไว้ในโปรเจกต์

---

## สารบัญคำสั่งด่วน (Quick Navigation)
1. [Bandit (Python AST)](#1-bandit-python-ast)
2. [ESLint (JavaScript/TypeScript AST)](#2-eslint-javascripttypescript-ast)
3. [Semgrep OSS (Tree-sitter CST)](#3-semgrep-oss-tree-sitter-cst)
4. [Snyk Code (DeepCode AI Taint Graph)](#4-snyk-code-deepcode-ai-taint-graph)
5. [GitHub CodeQL (Datalog / Relational Code DB)](#5-github-codeql-datalog--relational-code-db)
6. [CodeLens AI (Senior Project Benchmark Runner)](#6-codelens-ai-senior-project-benchmark-runner)

---

## 1. Bandit (Python AST)
ตรวจจับข้อบกพร่องและคำสั่งอันตรายใน Python ด้วยการตรวจ AST Nodes ตรงๆ

### การติดตั้ง (ถ้ายังไม่มี):
```powershell
pip install bandit
```

### คำสั่งรันสแกน (Run Commands):
```powershell
# รันสแกนไฟล์ Benchmark รวมช่องโหว่ (snyk_capability_matrix_test.py)
bandit -r "Security_CWE/snyk_capability_matrix_test.py"

# หรือรันสแกนไฟล์ชุดทดสอบละเอียดเปรียบเทียบ Vulnerable vs Remediated
bandit -r "Security_CWE/security_competitor_test_cases.py"
```

### สิ่งที่คาดหวังจากผลลัพธ์:
- จะแสดง Issue เช่น `[B608: hardcoded_sql_expressions]` สำหรับ SQL Injection, `[B602: subprocess_popen_with_shell_equals_true]` สำหรับ Command Injection และ `[B403: blacklist]` สำหรับ Pickle

---

## 2. ESLint (JavaScript/TypeScript AST)
ตรวจจับ Code Quality และความปลอดภัยระดับ Syntax ผ่าน `eslint-plugin-security`

### คำสั่งรันสแกน (Run Commands):
```powershell
# เข้าไปที่โฟลเดอร์ Security_CWE
cd "d:\4th-year\Senior-Project\Security_CWE"

# วิธีที่ 1: รันผ่าน npx ตรงๆ
npx eslint security_competitor_test_cases.js

# วิธีที่ 2: รันผ่าน npm script
npm run lint
```

### สิ่งที่คาดหวังจากผลลัพธ์:
- จะแสดง Warning ทั้งหมด 5 จุด (5 warnings) ครอบคลุม:
  - `security/detect-child-process` (บรรทัดที่เรียก `child_process.exec`)
  - `security/detect-non-literal-fs-filename` (บรรทัดที่เรียก `fs.readFileSync` ด้วยตัวแปร)
  - `security/detect-object-injection` (บรรทัดที่เข้าถึง Object ด้วยตัวแปร)
  - `security/detect-eval-with-expression` (บรรทัดที่เรียก `eval()`)

---

## 3. Semgrep OSS (Tree-sitter CST)
ตรวจจับช่องโหว่ด้วย Pattern Matching ความเร็วสูงระดับ Tree-sitter

### การติดตั้ง:
```powershell
pip install semgrep
```

### คำสั่งรันสแกน (Run Commands):
```powershell
# รันสแกนไฟล์ Benchmark ด้วย Ruleset มาตรฐานอัตโนมัติ (--config auto)
semgrep scan --config auto "Security_CWE\snyk_capability_matrix_test.py"

# หรือรันสแกนทั้งโฟลเดอร์ Security_CWE
semgrep scan --config auto "Security_CWE"
```

### สิ่งที่คาดหวังจากผลลัพธ์:
- ตรวจพบประมาณ **20 Code Findings** ครอบคลุม:
  - `python.flask.security.injection.tainted-sql-string` (SQLi)
  - `python.lang.security.audit.subprocess-shell-true` (Command Injection)
  - `generic.secrets.security.detected-stripe-api-key` (Secret Leak)
  - `python.flask.security.open-redirect` (Open Redirect)

---

## 4. Snyk Code (DeepCode AI Taint Graph)
สแกน Taint Dataflow จาก Source ไปยัง Sink เชื่อมโยงข้ามไฟล์

### การติดตั้งและล็อกอิน:
```powershell
npm install -g snyk
snyk auth
```

### คำสั่งรันสแกน (Run Commands):
```powershell
# รันสแกนไฟล์ Benchmark ผ่าน Snyk Code (SAST)
snyk code test "Security_CWE\snyk_capability_matrix_test.py"

# หรือรันสแกนโฟลเดอร์ Cross-File เพื่อดูการลากเส้นทางข้ามไฟล์
snyk code test "Security_CWE\cross_file_demo"
```

### สิ่งที่คาดหวังจากผลลัพธ์:
- ตรวจพบ **14 Open Issues** ในหมวด Classical Web (SQLi, Command Injection, XSS, Path Traversal, SSRF)
- จะแสดง Data Flow Path บรรทัดต่อบรรทัดอย่างละเอียด
- **ผลต่อ OWASP LLM 2025:** จะรายงาน 0 Issues (ตรวจไม่พบช่องโหว่ AI/Agentic)

---

## 5. GitHub CodeQL (Datalog / Relational Code DB)
สร้างฐานข้อมูลเชิงสัมพันธ์ของโค้ด แล้วรัน Query ตรรกะ QL เพื่อหาเส้นทาง Taint Reachability

### ขั้นตอนที่ 1: สร้าง Database จาก Source Code
*(ตอนนี้โฟลเดอร์เปลี่ยนชื่อเป็น `Security_CWE` แล้ว สามารถชี้ไปที่โฟลเดอร์ตรงๆ ได้เลย)*
```powershell
# สร้าง Database ชื่อ 'codeql_db' จากโฟลเดอร์ Security_CWE
codeql database create "codeql_db" --language=python --source-root="Security_CWE" --overwrite
```

### ขั้นตอนที่ 2: รันการสแกนความปลอดภัยด้วยชุด Security Queries
```powershell
# รันสแกนและบันทึกผลออกมาเป็นไฟล์ CSV
codeql database analyze "codeql_db" codeql/python-queries --format=csv --output="codeql_results.csv"

# หรือรันสแกนและแสดงผลลัพธ์เป็นตารางบน Terminal ทันที
codeql database analyze "codeql_db" codeql/python-queries --format=table
```

### ขั้นตอนที่ 3: ทดลองรัน Query เดี่ยว (Custom QL Query)
```powershell
# รันไฟล์คำสั่ง QL ตัวอย่างที่เราเขียนไว้
codeql query run "demo_codeql_queries\find_execute_calls.ql" --database="codeql_db"
```

### สิ่งที่คาดหวังจากผลลัพธ์:
- ตรวจพบช่องโหว่ความแม่นยำสูงใน [codeql_results.csv](file:///d:/4th-year/Senior-Project/codeql_results.csv):
  - `PathInjection.ql` (CWE-022)
  - `CommandInjection.ql` (CWE-078)
  - `SqlInjection.ql` (CWE-089)
  - `ReflectedXss.ql` (CWE-079)
  - `UnsafeDeserialization.ql` (CWE-502)

---

## 6. CodeLens AI (Senior Project Benchmark Runner)
รันชุดทดสอบเชิงประจักษ์ (Execution Test) เปรียบเทียบความแตกต่างระหว่าง **Vulnerable Functions** (โค้ดที่ถูกแฮกได้) กับ **Remediated Functions** (โค้ดที่ใส่ Guardrails ของเราแล้วปลอดภัย)

### คำสั่งรันการทดสอบ (Run Commands):
```powershell
# รันการทดสอบ Execute โค้ดจริงและพิสูจน์การทำงานของ Guardrail
python "Security_CWE/run_security_tests.py"

# หรือรันแบบ Interactive Shell (ป้อน Payload ทดสอบเอง)
python "Security_CWE/interactive_security_tester.py"
```

### สิ่งที่ระบบจะพิสูจน์ให้เห็น:
1. **CWE-089 (SQL Injection):** โค้ดเดิมโดนขโมยข้อมูล แต่โค้ดที่แก้แล้วใช้ Parameterization ปลอดภัย 100%
2. **CWE-022 (Path Traversal):** โค้ดเดิมอ่านไฟล์ข้าม Tenant ได้ แต่โค้ดที่แก้แล้วติด Sandbox Guardrail
3. **OWASP LLM06 (Excessive Agency):** โค้ดเดิมปล่อยให้ AI สั่งลบไฟล์อัตโนมัติ แต่โค้ดที่แก้แล้วมี **Human-in-the-Loop (HITL) Gate** ดักจับและบล็อกการทำงาน
