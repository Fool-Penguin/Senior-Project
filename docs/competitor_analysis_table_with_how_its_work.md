# Competitor Analysis Table for Security

| Tool | Python | JavaScript | TypeScript | AST | Tree-sitter | Taint Graph | Datalog / Code DB | Function | File | Repo | CWE | CVE (Source) | OWASP Web | OWASP LLM (2025) | Auto-Fix |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bandit** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **ESLint (Security)** | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Semgrep OSS** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **Snyk Code** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **GitHub CodeQL** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **SonarQube for IDE (SonarLint)** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ (Local) / ✅ (Server)* | ❌ | ✅ | ✅ | ❌ (Local) / ✅ (Server)* | ✅ | ❌ | ✅ | ❌ | ⚠️ (Rule-based) |
| **CodeDEE (Our Work)** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |

---

> *\*หมายเหตุ SonarQube for IDE (SonarLint):* ในโหมด Standalone (ทำงานใน IDE เครื่องตนเอง) จะทำงานเฉพาะ AST Pattern Matching เท่านั้น ไม่รองรับ Taint Analysis; การวิเคราะห์ Inter-procedural Taint Analysis ทำงานได้เฉพาะบน SonarQube Server (Developer Edition ขึ้นไป) แล้วส่งผลลัพธ์ผ่าน Connected Mode มาแสดงใน IDE เท่านั้น

---

# 🎯 โจทย์เดียวกัน: เปรียบเทียบเทคนิคต่างๆ บนฟังก์ชัน SQL Injection เดียวกัน

### 📌 โค้ดฟังก์ชันเป้าหมาย (The Target Vulnerable Function):
```python
import sqlite3
from flask import Flask, request

app = Flask(__name__)

@app.route("/api/user/login")
def user_login():
    # 1. รับข้อมูลจากภายนอก
    username = request.args.get("username")
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # 2. จุดอันตราย: นำตัวแปรมาต่อสตริงเข้า SQL Query ตรงๆ
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    
    # 3. จุดประหารคำสั่ง SQL
    cursor.execute(query)
    return cursor.fetchall()
```

---

### 1. AST (Abstract Syntax Tree) — ตรวจจับรูปทรงกิ่งไม้ของ Syntax
- **เครื่องมือ:** Bandit (Python), ESLint (JavaScript)
- **วิธีที่ AST มองฟังก์ชันนี้:**
  AST จะแปลงบรรทัด `query = f"..."` เป็นกิ่งก้าน Node ของ Object:
  ```python
  # สิ่งที่ AST Parser สร้างขึ้นมาในหน่วยความจำ:
  Assign(
    targets=[Name(id='query')],
    value=JoinedStr(values=[
      Constant(value="SELECT id, role, email FROM accounts WHERE username = '"),
      FormattedValue(value=Name(id='username')),
      Constant(value="'")
    ])
  )
  ```
- **โค้ดที่ AST ใช้ตรวจจับ (Bandit Rule B608):**
  ```python
  import ast

  class AstSqlDetector(ast.NodeVisitor):
      def visit_Assign(self, node):
          # ตรวจดูว่าในคำสั่ง Assign มีการต่อข้อความ (JoinedStr) ที่มีคีย์เวิร์ด SQL หรือไม่
          if isinstance(node.value, ast.JoinedStr):
              for part in node.value.values:
                  if isinstance(part, ast.Constant) and "SELECT" in str(part.value):
                      print(f"[!] AST ตรวจพบความเสี่ยง SQL Injection ที่บรรทัด {node.lineno}")
          self.generic_visit(node)
  ```
- **ข้อจำกัดเชิงโค้ดของ AST:**  
  AST ตรวจเจอเพราะเห็นคำว่า `"SELECT"` อยู่ในกิ่ง `JoinedStr` เท่านั้น **แต่มันไม่รู้ว่า `username` มาจากไหน**  
  *ถ้าเราเปลี่ยนเป็น `username = "admin"` (ตัวแปรค่าคงที่ที่ปลอดภัย 100%) AST ก็ยังคงเตือนเหมือนเดิม เกิดเป็น False Positive*

---

### 2. Tree-sitter (Concrete Syntax Tree - CST) — แปลงเป็นโครงสร้างความเร็วสูงและจับคู่ Pattern
- **เครื่องมือ:** Semgrep OSS, CodeLens AI (งานวิจัยของเรา)
- **วิธีที่ Tree-sitter มองฟังก์ชันนี้:**
  Tree-sitter สร้าง Concrete Syntax Tree (CST) ที่เก็บทุก Token รวมถึงตำแหน่ง Byte Offset ในไฟล์อย่างละเอียด:
  ```text
  (function_definition
    name: (identifier) @user_login
    body: (block
      (assignment
        left: (identifier) @var_query
        right: (format_string
          (string_content) @sql_prefix
          (interpolation (identifier) @param)
          (string_content) @sql_suffix))
      (expression_statement
        (call
          function: (attribute object: (identifier) attribute: (identifier))
          arguments: (argument_list (identifier))))))
  ```
- **โค้ดสืบค้น Pattern ของ Tree-sitter (Semgrep YAML):**
  Tree-sitter รองรับการเขียน Pattern จับโครงสร้างได้ทันที:
  ```yaml
  pattern: |
    $QUERY = f"SELECT ... WHERE ... = '{$PARAM}'"
    ...
    $CURSOR.execute($QUERY)
  ```
- **ความเจ๋งของ Tree-sitter ที่เหนือกว่า AST:**
  1. **Incremental Parsing:** หากโปรแกรมเมอร์กำลังพิมพ์แก้โค้ดในบรรทัด `query` ตัว Tree-sitter จะใช้เวลาเพียง **0.05 มิลลิวินาที** ในการวิเคราะห์เฉพาะจุดที่มีการเปลี่ยนแปลง โดยไม่ต้องรื้อ Parse ทั้งฟังก์ชันใหม่
  2. **คำนวณ Complexity ทันที:** ในขณะเดียวกัน Tree-sitter จะตรวจนับ Decision Nodes และ Nesting Blocks เพื่อคำนวณคะแนน Cognitive/Cyclomatic Complexity ของฟังก์ชันนี้ได้แบบ Real-time บน Editor

---

### 3. Taint Graph — นักสืบแกะรอยการไหลของข้อมูลเปื้อนพิษ (Source to Sink)
- **เครื่องมือ:** Snyk Code
- **วิธีที่ Taint Graph มองฟังก์ชันนี้:**
  Taint Graph ไม่ได้สนใจแค่ตัวหนังสือว่ามีคำว่า `SELECT` หรือไม่ แต่มันสนใจ **"พฤติกรรมการเดินทางของข้อมูล (Dataflow)"**:
  ```mermaid
  flowchart LR
      Source["request.args.get('username')<br><b>[SOURCE: เปื้อนพิษ/Tainted]</b>"] 
      -->|ไหลเข้าสู่ตัวแปร| Var["username"]
      -->|ประกอบร่างเข้า String| Query["query = f'SELECT ... {username}'"]
      -->|ส่งเป็นพารามิเตอร์| Sink["cursor.execute(query)<br><b>[SINK: ประหารคำสั่งอันตราย]</b>"]
  ```
- **การตัดสินใจของ Taint Engine:**
  1. **ตรวจสอบ Source:** พบว่าข้อมูลมาจาก HTTP Request (`request.args.get`) ถือเป็นข้อมูลที่ไม่น่าเชื่อถือ (Tainted)
  2. **ตรวจสอบ Sanitizer:** ข้อมูล `username` ผ่านฟังก์ชันแปลงเป็นตัวเลข หรือผ่าน Parameterization หรือไม่? $\rightarrow$ **คำตอบคือ "ไม่ผ่าน"**
  3. **ตรวจสอบ Sink:** ข้อมูลเปื้อนพิษไหลตรงเข้าสู่ `cursor.execute()` ซึ่งเป็น Database Execution Sink
  4. **สรุปผล:** Snyk สั่งยิง Alert **"High Severity SQL Injection (CWE-89)"** พร้อมลากเส้นทางให้ดู 3 ขั้นตอน

---

### 4. Datalog / Relational Code DB — แปลงโค้ดเป็นตารางฐานข้อมูล แล้วค้นหาบั๊กเหมือนเขียน SQL
- **เครื่องมือ:** GitHub CodeQL
- **เข้าใจง่ายๆ ใน 3 สเต็ป:**

  **สเต็ปที่ 1: แปลงโค้ดให้กลายเป็นตาราง (Table)**  
  CodeQL จะอ่านโค้ดฟังก์ชัน `user_login` แล้วเอาไปบันทึกลงตารางฐานข้อมูล คล้ายๆ ตาราง Excel ในเครื่อง:

  | ตัวแปร / คำสั่ง (Node) | ประเภทของข้อมูล | ไหลต่อไปที่ไหน? (Flows Into) |
  | :--- | :--- | :--- |
  | `request.args.get("username")` | **Source (รับจากเว็บ)** | ตัวแปร `username` |
  | `username` | Untrusted String | ตัวแปร `query` |
  | `query` | SQL String ต่อเอง | คำสั่ง `cursor.execute()` |
  | `cursor.execute()` | **Sink (คำสั่งรันฐานข้อมูล)** | *สิ้นสุดการเดินทาง* |

  **สเต็ปที่ 2: เขียนคำสั่งสืบค้น (Query)**  
  แทนที่คนต้องมานั่งไล่โค้ดทีละบรรทัด CodeQL จะใช้ภาษา QL (Datalog) สั่งค้นหาในตารางเหมือนเราเขียนคำสั่ง SQL สั้นๆ ว่า:
  > *"ในตาราง มีเส้นทางไหนไหมที่เริ่มต้นจาก **Source (รับจากเว็บ)** แล้วไหลไปลงเอยที่ **Sink (คำสั่งรันฐานข้อมูล)** โดยที่ระหว่างทางไม่เคยผ่านการล้างค่า?"*

  **สเต็ปที่ 3: ชี้เป้าช่องโหว่**  
  ระบบค้นพบว่า: จากแถวที่ 1 $\rightarrow$ แถวที่ 2 $\rightarrow$ แถวที่ 3 เชื่อมถึงกันหมด! CodeQL จึงสรุปทันทีว่าฟังก์ชันนี้มีช่องโหว่ **SQL Injection (CWE-89)**

- **ทำไมมันถึงช้า?**  
  เพราะก่อนที่มันจะค้นหาบั๊กได้ มันต้องรันคำสั่ง Compile/Extract โค้ดทั้งหมดทั้งโปรเจกต์ มาบันทึกใส่ตารางฐานข้อมูลก้อนนี้ให้เสร็จก่อนนั่นเอง

---

# 🛠️ เปรียบเทียบผลลัพธ์ Auto-Fix บนฟังก์ชัน SQL Injection นี้

| เครื่องมือ | มี Auto-Fix ไหม? | ผลลัพธ์ตอนกด Auto-Fix บนฟังก์ชันนี้ |
| :--- | :---: | :--- |
| **Bandit** | ❌ **ไม่มี** | ไม่มีปุ่มแก้โค้ด พ่นแค่ข้อความเตือนใน Terminal ให้โปรแกรมเมอร์ไปแก้มือเอง |
| **ESLint** | ❌ **แก้ไม่ได้** | ฟังก์ชันนี้เป็น SQL Injection ซึ่งต้องเปลี่ยนโครงสร้างคำสั่ง ESLint ทำได้แค่แก้พวกเครื่องหมายวรรคตอน จึงแก้ไม่ได้ |
| **Semgrep OSS** | ⚠️ **แก้ไม่สมบูรณ์** | ใช้ฟิลด์ Search & Replace ในไฟล์ YAML แทนที่คำได้แค่จุดที่ตรง Regex แต่อาจทำให้ฟังก์ชันเกิด Syntax Error หรือรันคำสั่ง SQL ไม่ผ่าน |
| **Snyk Code** | 💰 **มี (DeepCode AI)** | สร้าง Git Diff แสดงให้ดูบน VS Code:<br>`- query = f"SELECT ... WHERE username = '{username}'"`<br>`+ cursor.execute("SELECT ... WHERE username = ?", (username,))`<br>*(แต่ต้องจ่ายเงินซื้อ Enterprise Plan ถึงจะกดปุ่ม Apply Fix ได้)* |
| **GitHub CodeQL** | 💰 **มี (Copilot Autofix)** | สั่งให้ Copilot บนเซิร์ฟเวอร์ส่ง Commit เข้าไปแก้โค้ดใน Pull Request บน GitHub ให้อัตโนมัติ *(แต่ต้องซื้อ License GHAS ระดับองค์กร)* |
| **CodeLens AI** | ** มี (1-Click Fix)** | เขียน Refactor โค้ดให้ใหม่ทั้งฟังก์ชัน: เปลี่ยนไปใช้ Parameterized Query + ใส่ `with sqlite3.connect` ป้องกัน Connection Leak ให้เสร็จสรรพใน 1 วินาที *(ฟรี 100%)* |
