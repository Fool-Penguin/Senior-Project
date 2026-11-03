# Competitor Analysis & Static Analysis Techniques

## 1. Competitor Comparison Table

| Tool | Python | JavaScript | TypeScript | AST | Tree-sitter | Taint Graph | Datalog / Code DB | Function | File | Repo | CWE | CVE (Source) | OWASP Web | OWASP LLM (2025) | Auto-Fix |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bandit** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **ESLint (Security)** | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Semgrep OSS** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **Snyk Code** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **GitHub CodeQL** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **SonarQube for IDE (SonarLint)** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ (Local) / ✅ (Server)* | ❌ | ✅ | ✅ | ❌ (Local) / ✅ (Server)* | ✅ | ❌ | ✅ | ❌ | ⚠️ (Rule-based) |
| **CodeDEE (Our Work)** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |

> *\*หมายเหตุ SonarQube for IDE (SonarLint):* ในโหมด Standalone (IDE Local) ทำงานเฉพาะ AST Pattern Matching; Taint Analysis ต้องเชื่อมต่อ SonarQube Server (Developer Edition+) เท่านั้น


---

## 2. ฟังก์ชันตัวอย่างที่ใช้ทดสอบ (Target Vulnerable Function)
*(ใช้ฟังก์ชันที่มีช่องโหว่ **SQL Injection (CWE-89)** ชุดเดียวกัน เพื่อเปรียบเทียบกลไกการทำงานของแต่ละเทคนิค)*

```python
import sqlite3
from flask import Flask, request

app = Flask(__name__)

@app.route("/api/user/login")
def user_login():
    username = request.args.get("username")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # จุดอันตราย: การนำตัวแปรภายนอกมาต่อ String เข้า SQL Query
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    
    # จุดเรียกคำสั่งประหาร SQL
    cursor.execute(query)
    return cursor.fetchall()
```

---

## 3. กลไกการทำงาน ข้อดี ข้อเสีย และเหตุผลที่เลือกใช้ในแต่ละเทคนิค

---

### เทคนิคที่ 1: AST (Abstract Syntax Tree Pattern Matching)
**เครื่องมือที่ใช้:** Bandit, ESLint

#### ⚙️ ขั้นตอนการทำงาน (How It Works):
1. **การแปลงโค้ดเป็นโครงสร้างต้นไม้ (AST Parsing):**  
   Parser แปลงโค้ดเป็นโครงสร้างต้นไม้ โดยตัดรายละเอียดเชิงรูปแบบ (เช่น ช่องว่าง, คอมเมนต์) ออกทั้งหมด และจัดกลุ่มเป็น Nodes ตามไวยากรณ์:
   ```text
   [ Root: Module ]
   |
   L- [ Node 1: FunctionDef: user_login ]
      |
      |- [ Node 2: Assign ] -> ตัวแปร: username
      |  L- [ Call ]        -> request.args.get("username")
      |
      |- [ Node 3: Assign ] -> ตัวแปร: query
      |  L- [ JoinedStr ]   -> f"SELECT ... WHERE username = '{username}'"
      |     |- Constant: "SELECT id, role, email FROM accounts WHERE username = '"
      |     |- FormattedValue: Name(username)
      |     L- Constant: "'"
      |
      L- [ Node 4: Expr ]   -> cursor.execute(query)
         L- [ Call ]
            |- func: Attribute(value=Name(cursor), attr="execute")
            L- args: [ Name(query) ]
   ```
2. **การเดินสำรวจโครงสร้าง (Tree Visitor):**  
   ตัวตรวจจับจะเดินไต่ไปตามกิ่งไม้เพื่อเช็คชนิดของโหนด เมื่อเดินมาถึง `Assign (query)` จะตรวจพบโหนด `JoinedStr` (สตริงที่มีการนำค่าตัวแปรมาต่อคำ) และเมื่อเดินมาถึง `Call` จะตรวจพบคำสั่ง `cursor.execute`
3. **การตรวจสอบเงื่อนไขตามกฎ (Rule Matching):**  
   นำข้อมูลที่ตรวจพบไปเทียบกับชุดกฎ (เช่น Bandit Rule `B608: hardcoded_sql_expressions`):
   ```python
   def visit_Assign(self, node):
       if isinstance(node.value, ast.JoinedStr):
           for part in node.value.values:
               # ตรวจหาว่าในสตริงที่ต่อกัน มีคีย์เวิร์ด SQL หรือไม่
               if isinstance(part, ast.Constant) and any(kw in str(part.value).upper() for kw in ["SELECT", "FROM", "WHERE"]):
                   self.report_issue(node, severity="MEDIUM", cwe="CWE-89")
   ```
4. **การแจ้งเตือน (Reporting):**  
   เมื่อพบว่ามีการประกอบ `JoinedStr` ร่วมกับคีย์เวิร์ด `SELECT` และ `WHERE` ระบบจะสั่งยิง Alert ช่องโหว่ **CWE-89 (SQL Injection)** ทันที

#### 💡 การประเมินเทคนิค AST:
- **ข้อดี (Pros):**
  - โครงสร้างเรียบง่าย น้ำหนักเบา (Lightweight) ใช้ทรัพยากรระบบน้อยมาก
  - ประมวลผลได้รวดเร็ว เหมาะสำหรับเขียนกฎตรวจสอบความเรียบร้อยของ Syntax
  - ฝังมากับตัวภาษาอยู่แล้ว (เช่น โมดูล `ast` ใน Python หรือ `espree` ใน JS) ไม่ต้องติดตั้ง Dependency ขนาดใหญ่
- **ข้อเสีย (Cons):**
  - **ไม่มีระบบติดตามการไหลของข้อมูล (No Dataflow Tracking):** ตรวจได้เฉพาะรูปทรงของโหนดตรงหน้า แต่ไม่รู้ว่าค่าในตัวแปรมาจากไหน
  - เกิดข้อผิดพลาดแบบ False Positive สูง (เช่น ถ้าตัวแปรเป็นข้อความคงที่ `username = "admin"` ที่ปลอดภัย AST ก็ยังแจ้งเตือนเพราะเห็นคำว่า SELECT)
- **เหตุผลที่ควรเลือกใช้ (Why & When to use):**
  - เหมาะสำหรับทำ **Linter ตรวจสอบมาตรฐานไวยากรณ์โค้ด (Coding Standards / Style Enforcement)**
  - เหมาะสำหรับตรวจจับคำสั่งต้องห้ามที่ไม่ปลอดภัยในตัวมันเองแบบเด็ดขาด (เช่น ห้ามใช้ `eval()`, ห้ามใช้ `MD5`, ห้ามฮาร์ดโค้ดรหัสผ่าน)

---

### เทคนิคที่ 2: Tree-sitter / CST (Concrete Syntax Tree Pattern Matching)
**เครื่องมือที่ใช้:** Semgrep OSS, CodeLens AI

#### ⚙️ ขั้นตอนการทำงาน (How It Works):
1. **การสร้าง Concrete Syntax Tree (CST Generation):**  
   Tree-sitter แปลงโค้ดให้อยู่ในรูป CST ซึ่งเก็บข้อมูลครบถ้วนทุก Token พร้อมตำแหน่ง Byte Offset ในไฟล์อย่างละเอียด:
   ```text
   function_definition [7, 0] - [17, 27]
     name: identifier [7, 4] - [7, 14] ("user_login")
     body: block [7, 17] - [17, 27]
       assignment [13, 4] - [13, 81]
         left: identifier [13, 4] - [13, 9] ("query")
         right: format_string [13, 12] - [13, 81]
           string_content: "SELECT id, role, email FROM accounts WHERE username = '"
           interpolation: identifier ("username")
           string_content: "'"
       expression_statement [16, 4] - [16, 25]
         call [16, 4] - [16, 25]
           function: attribute
             object: identifier ("cursor")
             attribute: identifier ("execute")
           arguments: argument_list
             identifier ("query")
   ```
2. **การโหลดกฎในรูปแบบโครงสร้าง (Rule Pattern Normalization):**  
   กฎของระบบ (เช่น Semgrep YAML) จะถูกเขียนขึ้นในรูปแบบโค้ดต้นแบบ (Pattern Template):
   ```yaml
   rules:
     - id: python-sql-injection-format-string
       pattern: |
         $QUERY = f"... {$PARAM} ..."
         ...
         $CURSOR.execute($QUERY)
       message: "Detected SQL string formatting concatenated directly into execute()"
   ```
3. **การจับคู่ทางโครงสร้าง (Structural Matching):**  
   Matching Engine นำ Pattern Template ไปทาบกับโครงสร้างต้นไม้ CST:
   - ตรวจพบว่าตัวแปร `$QUERY` ถูกสร้างด้วย `format_string` โดยมี `$PARAM` (`username`) แทรกอยู่
   - ตรวจพบว่าตัวแปร `$QUERY` เดียวกันถูกส่งเข้าคำสั่ง `$CURSOR.execute()`
4. **การแจ้งเตือน (Reporting):**  
   โครงสร้างและตัวแปรที่ผูกกันสอดคล้องกับ Pattern ครบถ้วน ระบบจะสั่งแจ้งเตือน Alert ทันที

#### 💡 การประเมินเทคนิค Tree-sitter / CST:
- **ข้อดี (Pros):**
  - มีความสามารถ **Incremental Parsing:** เมื่อโปรแกรมเมอร์แก้ไขโค้ดเพียงบางบรรทัด ระบบจะ Parse ใหม่เฉพาะโหนดที่มีการเปลี่ยนแปลงในหน่วยความจำ ไม่ต้องเริ่มอ่านทั้งไฟล์ใหม่
  - เก็บโครงสร้างโค้ดครบถ้วนทุกตัวอักษรและพิกัดตำแหน่ง ทำให้สามารถคำนวณตัวชี้วัดความซับซ้อน (Cognitive / Cyclomatic Complexity) ได้แม่นยำ
  - เป็นแกนกลางที่รองรับได้หลากหลายภาษาโปรแกรม (Polyglot: C, Python, Java, JS) ด้วยรูปแบบ API เดียวกัน
- **ข้อเสีย (Cons):**
  - ตัวมันเองเป็นเพียงตัวแกะโครงสร้าง (Parser Engine) ไม่มีความสามารถในการวิเคราะห์ Dataflow ข้ามไฟล์หรือข้ามฟังก์ชันในตัว ต้องเขียน Logic ครอบเพิ่มเติม
- **เหตุผลที่ควรเลือกใช้ (Why & When to use):**
  - **เหมาะที่สุดสำหรับเครื่องมือประเภท Code Editor / IDE Extension** ที่ต้องการการตอบสนองแบบ Real-time ทันทีขณะโปรแกรมเมอร์กำลังพิมพ์โค้ด
  - เหมาะสำหรับงานตรวจสอบโครงสร้างฟังก์ชันและคำนวณคะแนนคุณภาพโค้ด (Quality & Cognitive Complexity Metrics)

---

### เทคนิคที่ 3: Taint Graph (Inter-procedural Dataflow Analysis)
**เครื่องมือที่ใช้:** Snyk Code

#### ⚙️ ขั้นตอนการทำงาน (How It Works):
1. **การระบุจุดรับข้อมูล (Source Identification):**  
   ระบบตรวจสอบคำสั่งที่รับ Input จากภายนอก: `username = request.args.get("username")`  
   $\rightarrow$ ตัวแปร `username` ถูกกำหนดสถานะเป็น **`TAINTED` (ข้อมูลเปื้อนพิษ)**
2. **การติดตามการไหลของข้อมูล (Taint Propagation):**  
   ระบบติดตามการเดินทางของสถานะ `TAINTED` ผ่าน Data Flow Graph:
   ```text
   [Node 1: request.args.get("username")]  (SOURCE: สถานะ TAINTED)
                      │
                      ▼ (ส่งค่าเข้าตัวแปร)
   [Node 2: ตัวแปร username]               (สถานะ: TAINTED)
                      │
                      ▼ (นำไปต่อสตริงใน query)
   [Node 3: ตัวแปร query]                  (สถานะ: TAINTED)
                      │
                      ▼ (ส่งเข้าฟังก์ชัน execute)
   [Node 4: cursor.execute(query)]         (SINK: จุดประหารคำสั่งอันตราย)
   ```
3. **การตรวจสอบตัวล้างมลพิษ (Sanitizer Check):**  
   ตรวจสอบว่าในระหว่าง Node 2 ถึง Node 4 มีการเรียกใช้ฟังก์ชันทำความสะอาดข้อมูลหรือไม่ (เช่น Parameterization หรือ Type Casting)  
   $\rightarrow$ ในฟังก์ชันนี้ไม่มีตัวกรอง ข้อมูลจึงคงสถานะ `TAINTED` ต่อเนื่องไปจนถึงจุดปลายทาง
4. **การแจ้งเตือน (Reporting):**  
   เมื่อสถานะ `TAINTED` เดินทางมาถึง **Sink** (`cursor.execute`) ระบบจะสรุปว่าเป็นช่องโหว่ความปลอดภัย พร้อมแสดงเส้นทางการไหลของข้อมูลแบบเชื่อมโยง

#### 💡 การประเมินเทคนิค Taint Graph:
- **ข้อดี (Pros):**
  - ความแม่นยำสูงมากในการค้นหาช่องโหว่ความปลอดภัยระดับร้ายแรง (CWE Top 25 เช่น SQLi, Command Injection, Path Traversal, SSRF)
  - สามารถลากเส้นติดตามการส่งต่อตัวแปรข้ามฟังก์ชัน ข้ามคลาส และข้ามไฟล์ได้ (Cross-file Inter-procedural Tracking)
  - ลดอัตรา False Positive ได้ดี เพราะวิเคราะห์ครบทั้ง Source, Sanitizer, และ Sink
- **ข้อเสีย (Cons):**
  - ใช้หน่วยความจำและพลังประมวลผลสูง ต้องสร้างกราฟการไหลขนาดใหญ่ ทำให้ทำงานช้ากว่าการตรวจ Syntax ทั่วไป
  - ไม่เหมาะกับการทำงานแบบ Real-time ทุกครั้งที่กดแป้นพิมพ์
- **เหตุผลที่ควรเลือกใช้ (Why & When to use):**
  - เหมาะสำหรับนำไปติดตั้งใน **CI/CD Pipeline** เพื่อสแกนความปลอดภัยทั้งโปรเจกต์ก่อนนำโค้ดขึ้น Production
  - เหมาะสำหรับตรวจสอบโปรเจกต์ขนาดใหญ่ที่มีการรับส่งข้อมูลผ่านหลายเลเยอร์ (Controller $\rightarrow$ Service $\rightarrow$ Repository)

---

### เทคนิคที่ 4: Datalog / Relational Code DB
**เครื่องมือที่ใช้:** GitHub CodeQL

#### ⚙️ ขั้นตอนการทำงาน (How It Works):
1. **การสกัดโค้ดลงฐานข้อมูลเชิงสัมพันธ์ (Database Extraction):**  
   CodeQL อ่านไฟล์โค้ดทั้งโปรเจกต์ และแปลงชิ้นส่วนโครงสร้างความสัมพันธ์ไปจัดเก็บลงในตาราง Relational Database:

   **ตาราง: `DataFlowNodes` (โหนดของคำสั่งและตัวแปร)**
   | Node ID | ชนิดของโหนด (Type) | ข้อความในโค้ด (Code Expression) | ตำแหน่งบรรทัด |
   | :---: | :--- | :--- | :---: |
   | 101 | RemoteSource | `request.args.get("username")` | 8 |
   | 102 | VariableDef | `username` | 8 |
   | 103 | StringConcat | `f"SELECT ... WHERE username = '{username}'"` | 14 |
   | 104 | DatabaseSink | `cursor.execute(query)` | 17 |

   **ตาราง: `DataFlowEdges` (เส้นทางการส่งต่อข้อมูล)**
   | From Node ID | To Node ID | รูปแบบการส่งต่อ (Flow Type) |
   | :---: | :---: | :--- |
   | 101 | 102 | Return value assignment |
   | 102 | 103 | Variable interpolation |
   | 103 | 104 | Function argument |

2. **การประมวลผลคำสั่งสืบค้น (Datalog Query Execution):**  
   นำคำสั่งภาษา QL (Declarative Logic Programming) มารันประมวลผลบนฐานข้อมูล:
   ```ql
   import python
   import semmle.python.security.dataflow.SqlInjectionCustomizations

   from SqlInjectionFlow::PathNode source, SqlInjectionFlow::PathNode sink
   where 
     // ตรวจสอบความสัมพันธ์การเดินทางในตาราง DataFlowEdges (Recursive Path Reachability)
     SqlInjectionFlow::flowPath(source, sink)
   select 
     sink.getNode(), source, sink, 
     "SQL query built from untrusted source: $@.",
     source.getNode(), "user input"
   ```
3. **การคำนวณเส้นทางและการแจ้งเตือน (Reachability & Reporting):**  
   Query Engine คำนวณความสัมพันธ์ของตารางฐานข้อมูล พบว่ามีเส้นทางเชื่อมโยงจาก Node `101` $\rightarrow$ `102` $\rightarrow$ `103` $\rightarrow$ `104` ครบวงจร จึงสั่งแจ้งเตือน Alert ช่องโหว่ **SQL Injection (CWE-89)**

#### 💡 การประเมินเทคนิค Datalog / Relational Code DB:
- **ข้อดี (Pros):**
  - มีความลึกและครอบคลุมที่สุดในเชิงทฤษฎีกราฟความสัมพันธ์ สามารถค้นหาเส้นทางซับซ้อนที่ต่อกันหลายชั้นได้อย่างสมบูรณ์
  - ยืดหยุ่นสูงมาก ผู้เชี่ยวชาญด้านความปลอดภัยสามารถเขียนคำสั่งภาษา QL เพื่อค้นหาช่องโหว่ประเภทใหม่ (Zero-day) ข้ามโปรเจกต์นับหมื่นแห่งได้พร้อมกัน
  - เป็นมาตรฐานที่ใช้ในระบบความปลอดภัยระดับสากล (GitHub Advanced Security)
- **ข้อเสีย (Cons):**
  - กระบวนการเตรียมข้อมูลหนักมาก (Heavyweight) ต้องสั่ง Compile/Extract โค้ดทั้งโปรเจกต์เป็น Database ขนาดใหญ่ก่อน จึงใช้เวลามากที่สุดในบรรดาทุกเทคนิค
  - ภาษาสืบค้น QL มีความซับซ้อนสูง ต้องอาศัยผู้เชี่ยวชาญเฉพาะทางในการออกแบบกฎ
- **เหตุผลที่ควรเลือกใช้ (Why & When to use):**
  - เหมาะสำหรับงานวิจัยความปลอดภัยระดับสูง (Security Research & Deep Variant Analysis)
  - เหมาะสำหรับการตรวจสอบความปลอดภัยระดับองค์กรใหญ่ (Periodic Security Audits) ที่ต้องการความครอบคลุมสูงสุดและยอมรับเวลาในการประมวลผลได้

---

## 4. เปรียบเทียบผลลัพธ์ของระบบ Auto-Fix เมื่อกดคลิก

| เครื่องมือ | มี Auto-Fix ไหม? | ผลลัพธ์ตอนกด Auto-Fix บนฟังก์ชันนี้ |
| :--- | :---: | :--- |
| **Bandit** | ❌ **ไม่มี** | ไม่มีคำสั่งแก้โค้ด แสดงเฉพาะรายงานข้อความใน Terminal ให้โปรแกรมเมอร์แก้ไขด้วยตนเอง |
| **ESLint** | ❌ **แก้ไม่ได้** | ฟังก์ชันนี้เป็นช่องโหว่ทางตรรกะคำสั่ง SQL ซึ่งเกินขอบเขตของ RuleFixer (แก้ได้เฉพาะ Token เครื่องหมายวรรคตอน) |
| **Semgrep OSS** | ⚠️ **แก้ไม่สมบูรณ์** | ใช้ฟิลด์ Search & Replace แทนที่ข้อความเฉพาะบรรทัด แต่ไม่สามารถปรับเปลี่ยนชนิดข้อมูลและโครงสร้างของคำสั่งทั้งฟังก์ชันให้ทำงานถูกต้องได้ |
| **Snyk Code** | 💰 **มี (DeepCode AI)** | สร้าง Git Diff แสดงโค้ดเก่าเปรียบเทียบกับโค้ดใหม่ที่แปลงเป็น Parameterized Query บน Editor *(จำกัดการใช้งานเฉพาะสิทธิ์ Enterprise)* |
| **GitHub CodeQL** | 💰 **มี (Copilot Autofix)** | ประมวลผลบนเซิร์ฟเวอร์และสร้าง Git Commit แก้ไขช่องโหว่เข้าไปใน Pull Request บน GitHub ให้อัตโนมัติ *(ต้องใช้งานร่วมกับ GitHub Advanced Security)* |
| **CodeLens AI (งานเรา)** | ** มี (1-Click Fix)** | ทำการ Refactor ฟังก์ชันใหม่ทั้งบล็อก: แปลงเป็น Parameterized Query + ห่อหุ้มด้วย Context Manager `with sqlite3.connect` ป้องกัน Connection Leak ในคลิกเดียว |
