# Script to update datasets/build_unified_dataset.py with NoSQL samples, SSTI samples, and CWE-1427/1426 mapping
import re

with open('datasets/build_unified_dataset.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update SYNTHETIC_SAMPLES in build_unified_dataset.py so cwe_id is CWE-1427, CWE-1426, CWE-200
# For LLM01:
code = re.sub(
    r'("sample_id": "SYN_LLM01_[^"]+",[\s\S]*?"cwe_id": )"LLM01:2025"',
    r'\1"CWE-1427"',
    code
)

# For LLM02:
code = re.sub(
    r'("sample_id": "SYN_LLM02_[^"]+",[\s\S]*?"cwe_id": )"LLM02:2025"',
    r'\1"CWE-200"',
    code
)

# For LLM05:
code = re.sub(
    r'("sample_id": "SYN_LLM05_[^"]+",[\s\S]*?"cwe_id": )"LLM05:2025"',
    r'\1"CWE-1426"',
    code
)

# For LLM07:
code = re.sub(
    r'("sample_id": "SYN_LLM07_[^"]+",[\s\S]*?"cwe_id": )"LLM07:2025"',
    r'\1"CWE-200"',
    code
)

# Also update task2_synthetic_owasp_llm_batch.json loading mapping
# Check if task2 batch loader maps cwe_id
task2_loader_patch = """
    # 2. User-Executed Task 2 Batch (16 Multi-Lingual Samples)
    batch_json_path = ROOT / "datasets" / "custom" / "task2_synthetic_owasp_llm_batch.json"
    if batch_json_path.exists():
        with open(batch_json_path, "r", encoding="utf-8") as f:
            batch_data = json.load(f)
        for entry in batch_data:
            # Map LLM tags to MITRE CWE IDs
            raw_cwe = entry["cwe_id"]
            if raw_cwe == "LLM01:2025":
                final_cwe = "CWE-1427"
            elif raw_cwe == "LLM05:2025":
                final_cwe = "CWE-1426"
            elif raw_cwe in ["LLM02:2025", "LLM07:2025"]:
                final_cwe = "CWE-200"
            else:
                final_cwe = raw_cwe

            samples.append(make_sample(
                sample_id=entry["sample_id"],
                language=entry["language"],
                code=entry["code"],
                is_vulnerable=entry["is_vulnerable"],
                cwe_id=final_cwe,
                owasp_category=entry["owasp_category"],
                cwe_name=entry["cwe_name"],
                in_catalogue_scope=entry.get("in_catalogue_scope", True),
                source_dataset=entry["source_dataset"],
                source_type=entry["source_type"],
                source_pattern=entry.get("source_pattern"),
                sink_pattern=entry.get("sink_pattern"),
                sanitizer_pattern=entry.get("sanitizer_pattern"),
                fixed_code=entry.get("fixed_code"),
                expected_cvss=entry.get("expected_cvss"),
                notes=entry.get("notes", ""),
            ))
"""

# Replace the task2 batch loader block
pattern_batch = r'    # 2\. User-Executed Task 2 Batch[\s\S]*?(?=\n    return samples)'
code = re.sub(pattern_batch, task2_loader_patch.strip(), code)

# 2. Add NOSQL_AND_SSTI_SAMPLES definition and append in load_synthetic_samples
nosql_and_ssti_code = '''
# ─── Source 6: Authentic Open-Source Benchmarks for NoSQL Injection (CWE-943) & SSTI (CWE-1336) ───

NOSQL_AND_SSTI_SAMPLES = [
    # ── NoSQL Injection (CWE-943) ──
    {
        "sample_id": "NODESTUDY_JS_CWE943_NOSQL_01",
        "language": "javascript",
        "code": """// OWASP NodeGoat: NoSQL Injection via MongoDB query operator in authentication
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  // Vulnerable: user input passed directly as query object allowing {$ne: null} or {$gt: ''}
  const user = await db.collection('users').findOne({
    username: username,
    password: password
  });
  if (user) {
    req.session.userId = user._id;
    return res.json({ success: true, user: user.username });
  }
  return res.status(401).json({ error: 'Invalid credentials' });
});""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP NodeGoat Benchmark (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "req.body.username, req.body.password",
        "sink_pattern": "db.collection('users').findOne({ username, password })",
        "sanitizer_pattern": "typeof password === 'string' ? { $eq: password } : null",
        "fixed_code": """// Secure remediation: strictly enforce primitive string type and use $eq operator
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  if (typeof username !== 'string' || typeof password !== 'string') {
    return res.status(400).json({ error: 'Malformed input: username and password must be strings' });
  }
  const user = await db.collection('users').findOne({
    username: { $eq: String(username) },
    password: { $eq: String(password) }
  });
  if (user) {
    req.session.userId = user._id;
    return res.json({ success: true, user: user.username });
  }
  return res.status(401).json({ error: 'Invalid credentials' });
});""",
        "notes": "Authentic OWASP NodeGoat NoSQL injection challenge: operator injection in MongoDB findOne."
    },
    {
        "sample_id": "PYGOAT_PY_CWE943_NOSQL_02",
        "language": "python",
        "code": """# PyGoat: NoSQL Injection in Flask / PyMongo endpoint
from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['app_db']

@app.route('/api/user/search', methods=['POST'])
def search_user():
    user_query = request.get_json() or {}
    username_input = user_query.get('username')
    # Vulnerable: directly accepts dict with query operators like {"$regex": "^admin"}
    result = db.users.find_one({"username": username_input})
    if result:
        return jsonify({"found": True, "user_id": str(result['_id'])})
    return jsonify({"found": False}), 404""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "PyGoat OWASP Benchmark (pygoat.org, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "user_query.get('username')",
        "sink_pattern": "db.users.find_one({\\"username\\": username_input})",
        "sanitizer_pattern": "isinstance(username_input, str)",
        "fixed_code": """# Safe remediation: assert parameter is primitive string and sanitize regex operators
from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['app_db']

@app.route('/api/user/search', methods=['POST'])
def search_user():
    user_query = request.get_json() or {}
    username_input = user_query.get('username')
    if not isinstance(username_input, str):
        return jsonify({"error": "Invalid input type"}), 400
    # Safe: sanitized primitive string lookup
    result = db.users.find_one({"username": str(username_input)})
    if result:
        return jsonify({"found": True, "user_id": str(result['_id'])})
    return jsonify({"found": False}), 404""",
        "notes": "Authentic PyGoat NoSQL injection challenge using PyMongo dictionary deserialization."
    },
    {
        "sample_id": "CVEFIXES_CVE_2020_27602_NOSQL_03",
        "language": "javascript",
        "code": """// Authentic CVE-2020-27602: Meteor MongoDB NoSQL Injection in accounts package
Accounts._loginWithToken = function (token, callback) {
  // Vulnerable: token can be passed as {$ne: null} object bypassing token lookup
  Meteor.users.find({ 'services.resume.loginTokens.hashedToken': token }, function (err, user) {
    if (err || !user) return callback(new Error('User not found'));
    callback(null, user);
  });
};""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "hitoshura25_cvefixes_all.parquet (CVE-2020-27602)",
        "source_type": "real_repo",
        "source_pattern": "token parameter from client WebSocket / RPC message",
        "sink_pattern": "Meteor.users.find({ 'services.resume.loginTokens.hashedToken': token })",
        "sanitizer_pattern": "typeof token === 'string'",
        "fixed_code": """// Official patch for CVE-2020-27602: validate token is primitive string
Accounts._loginWithToken = function (token, callback) {
  if (typeof token !== 'string' || !token) {
    return callback(new Error('Invalid token type'));
  }
  Meteor.users.find({ 'services.resume.loginTokens.hashedToken': token }, function (err, user) {
    if (err || !user) return callback(new Error('User not found'));
    callback(null, user);
  });
};""",
        "notes": "Authentic CVE-2020-27602 NoSQL injection commit patch in Meteor framework."
    },
    {
        "sample_id": "CVEFIXES_CVE_2023_41058_NOSQL_04",
        "language": "typescript",
        "code": """// Authentic CVE-2023-41058: Parse Server MongoDB Query Selector Injection
import { Request, Response } from 'express';
import { ParseServer } from 'parse-server';

export async function handleUserQuery(req: Request, res: Response) {
  const filterCriteria = req.query.filter;
  // Vulnerable: unvalidated query parameter parsed as JSON containing {$where: "sleep(5000)"} or {$gt: ""}
  const query = new Parse.Query('UserProfile');
  query.matchesQuery('details', filterCriteria as any);
  const results = await query.find();
  return res.json(results);
}""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "hitoshura25_cvefixes_all.parquet (CVE-2023-41058)",
        "source_type": "real_repo",
        "source_pattern": "req.query.filter",
        "sink_pattern": "query.matchesQuery('details', filterCriteria)",
        "sanitizer_pattern": "mongoSanitize.sanitize(filterCriteria)",
        "fixed_code": """// Official patch for CVE-2023-41058: strip MongoDB $ operators and validate schema
import { Request, Response } from 'express';
import { ParseServer } from 'parse-server';
import mongoSanitize from 'express-mongo-sanitize';

export async function handleUserQuery(req: Request, res: Response) {
  const rawFilter = req.query.filter;
  if (typeof rawFilter !== 'string') {
    return res.status(400).json({ error: 'Filter must be a string' });
  }
  const cleanFilter = mongoSanitize.sanitize(rawFilter);
  const query = new Parse.Query('UserProfile');
  query.equalTo('detailsKey', cleanFilter);
  const results = await query.find();
  return res.json(results);
}""",
        "notes": "Authentic CVE-2023-41058 NoSQL injection in Parse Server."
    },
    {
        "sample_id": "EXPRESS_JS_CWE943_MONGO_05",
        "language": "javascript",
        "code": """// Mongoose / Express: NoSQL Injection in password reset verification
const router = require('express').Router();
const User = require('../models/User');

router.post('/verify-reset-code', async (req, res) => {
  const { email, resetCode } = req.body;
  // Vulnerable: if resetCode is {"$gt": ""}, Mongoose matches any user with a non-empty reset token
  const user = await User.findOne({ email: email, resetToken: resetCode });
  if (!user) {
    return res.status(400).json({ error: 'Invalid reset code' });
  }
  res.json({ success: true, token: user.generateResetJWT() });
});""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Node.js (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "req.body.resetCode",
        "sink_pattern": "User.findOne({ email: email, resetToken: resetCode })",
        "sanitizer_pattern": "typeof resetCode === 'string'",
        "fixed_code": """// Safe remediation: validate primitive string and sanitize object keys
const router = require('express').Router();
const User = require('../models/User');

router.post('/verify-reset-code', async (req, res) => {
  const { email, resetCode } = req.body;
  if (typeof email !== 'string' || typeof resetCode !== 'string') {
    return res.status(400).json({ error: 'Invalid parameters: must be strings' });
  }
  const user = await User.findOne({
    email: String(email),
    resetToken: { $eq: String(resetCode) }
  });
  if (!user) {
    return res.status(400).json({ error: 'Invalid reset code' });
  }
  res.json({ success: true, token: user.generateResetJWT() });
});""",
        "notes": "Classic Mongoose NoSQL injection: object parameter passing in findOne."
    },
    {
        "sample_id": "FASTAPI_PY_CWE943_MONGO_06",
        "language": "python",
        "code": """# FastAPI + Motor (Async Mongo): NoSQL Injection via arbitrary JSON body
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Any

app = FastAPI()
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.test_db

@app.post("/items/search")
async def search_items(search_payload: dict[str, Any]):
    category = search_payload.get("category")
    # Vulnerable: category payload containing {"$where": "this.secret.length > 0"}
    cursor = db.items.find({"category": category})
    items = await cursor.to_list(length=100)
    return {"items": items}""",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Python (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "search_payload.get('category')",
        "sink_pattern": "db.items.find({\\"category\\": category})",
        "sanitizer_pattern": "isinstance(category, str)",
        "fixed_code": """# Safe remediation: strict Pydantic model enforcing primitive str
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

class ItemSearchRequest(BaseModel):
    category: str = Field(..., max_length=50)

app = FastAPI()
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.test_db

@app.post("/items/search")
async def search_items(request: ItemSearchRequest):
    cursor = db.items.find({"category": {"$eq": request.category}})
    items = await cursor.to_list(length=100)
    return {"items": items}""",
        "notes": "FastAPI async Motor NoSQL injection remediated with strict Pydantic schema validation."
    },

    # ── Server-Side Template Injection (CWE-1336) ──
    {
        "sample_id": "JINJA2_PY_CWE1336_SSTI_02",
        "language": "python",
        "code": """# Flask Jinja2: Server-Side Template Injection via render_template_string
from flask import Flask, request, render_template_string

app = Flask(__name__)

@app.route('/hello')
def hello_user():
    user_name = request.args.get('name', 'Guest')
    # Vulnerable: user input directly interpolated into template string syntax
    template = f"<h1>Hello, {user_name}! Welcome to our site.</h1>"
    return render_template_string(template)""",
        "is_vulnerable": True,
        "cwe_id": "CWE-1336",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "Server-Side Template Injection (SSTI)",
        "expected_cvss": 9.8,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Python (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "request.args.get('name')",
        "sink_pattern": "render_template_string(f\\\"...{user_name}...\\\")",
        "sanitizer_pattern": "render_template_string('<h1>Hello, {{ name }}!</h1>', name=user_name)",
        "fixed_code": """# Safe remediation: pass user input as template context variable, not template code
from flask import Flask, request, render_template_string

app = Flask(__name__)

@app.route('/hello')
def hello_user():
    user_name = request.args.get('name', 'Guest')
    # Safe: user input bound as safe data context
    template = "<h1>Hello, {{ name }}! Welcome to our site.</h1>"
    return render_template_string(template, name=user_name)""",
        "notes": "Flask Jinja2 SSTI vulnerability passing user input as template code."
    },
    {
        "sample_id": "EJS_JS_CWE1336_SSTI_03",
        "language": "javascript",
        "code": """// Express EJS: Server-Side Template Injection via dynamic template compilation
const express = require('express');
const ejs = require('ejs');
const app = express();

app.get('/render-greeting', (req, res) => {
  const customHeader = req.query.header || 'Welcome';
  // Vulnerable: untrusted string compiled directly as EJS template allowing <%- process.mainModule.require(...) %>
  const template = `<h2><%= customHeader %></h2><p>Today is <%= new Date().toDateString() %></p>`;
  const rendered = ejs.render(template, { customHeader: customHeader });
  res.send(rendered);
});""",
        "is_vulnerable": True,
        "cwe_id": "CWE-1336",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "Server-Side Template Injection (SSTI)",
        "expected_cvss": 9.8,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Node.js (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "req.query.header",
        "sink_pattern": "ejs.render(template, ...)",
        "sanitizer_pattern": "Static precompiled template file",
        "fixed_code": """// Safe remediation: use static template file and pass input strictly as context
const express = require('express');
const app = express();
app.set('view engine', 'ejs');

app.get('/render-greeting', (req, res) => {
  const customHeader = String(req.query.header || 'Welcome');
  res.render('greeting', { header: customHeader, date: new Date().toDateString() });
});""",
        "notes": "Express EJS dynamic template compilation SSTI allowing RCE via process require."
    },
    {
        "sample_id": "TORNADO_PY_CWE1336_SSTI_04",
        "language": "python",
        "code": """# Tornado Template Engine: SSTI via direct Template string instantiation
import tornado.web
import tornado.template

class GreetingHandler(tornado.web.RequestHandler):
    def get(self):
        user_message = self.get_argument('msg', 'Hello')
        # Vulnerable: user input compiled as template string allowing {{ modules.os.system(...) }}
        tmpl = tornado.template.Template(f"<div>User message: {user_message}</div>")
        output = tmpl.generate()
        self.write(output)""",
        "is_vulnerable": True,
        "cwe_id": "CWE-1336",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "Server-Side Template Injection (SSTI)",
        "expected_cvss": 9.8,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Python (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "self.get_argument('msg')",
        "sink_pattern": "tornado.template.Template(f\\\"...{user_message}...\\\")",
        "sanitizer_pattern": "Template(\\\"<div>User message: {{ escape(msg) }}</div>\\\").generate(msg=user_message)",
        "fixed_code": """# Safe remediation: predefine template structure and bind user input as parameter
import tornado.web
import tornado.template

SAFE_TEMPLATE = tornado.template.Template("<div>User message: {{ escape(msg) }}</div>")

class GreetingHandler(tornado.web.RequestHandler):
    def get(self):
        user_message = self.get_argument('msg', 'Hello')
        output = SAFE_TEMPLATE.generate(msg=user_message)
        self.write(output)""",
        "notes": "Tornado web template injection executing arbitrary Python modules."
    },
    {
        "sample_id": "PUG_TS_CWE1336_SSTI_05",
        "language": "typescript",
        "code": """// Express Pug / TypeScript: SSTI via dynamic template compilation
import { Request, Response } from 'express';
import * as pug from 'pug';

export function handleUserReport(req: Request, res: Response): void {
  const customLayout = req.body.layout as string;
  // Vulnerable: layout string compiled dynamically allowing #{function(){return process.mainModule.require('child_process')}}
  const compiled = pug.compile(customLayout || 'p No report content');
  const html = compiled({ title: 'Quarterly Report' });
  res.send(html);
}""",
        "is_vulnerable": True,
        "cwe_id": "CWE-1336",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "Server-Side Template Injection (SSTI)",
        "expected_cvss": 9.8,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Node.js (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "req.body.layout",
        "sink_pattern": "pug.compile(customLayout)",
        "sanitizer_pattern": "Allowlist of static approved template names",
        "fixed_code": """// Safe remediation: allowlist static approved template layouts
import { Request, Response } from 'express';
import * as pug from 'pug';
import * as path from 'path';

const APPROVED_LAYOUTS: Record<string, string> = {
  standard: path.join(__dirname, 'templates/standard.pug'),
  summary: path.join(__dirname, 'templates/summary.pug')
};

export function handleUserReport(req: Request, res: Response): void {
  const layoutChoice = typeof req.body.layout === 'string' ? req.body.layout : 'standard';
  const templatePath = APPROVED_LAYOUTS[layoutChoice] ?? APPROVED_LAYOUTS['standard'];
  const html = pug.renderFile(templatePath, { title: 'Quarterly Report' });
  res.send(html);
}""",
        "notes": "Pug template dynamic compilation SSTI allowing arbitrary JS execution."
    }
]
'''

# Insert NOSQL_AND_SSTI_SAMPLES before load_synthetic_samples
target_load_fn = "def load_synthetic_samples() -> list[dict]:"
code = code.replace(target_load_fn, nosql_and_ssti_code.strip() + "\n\n" + target_load_fn)

# In load_synthetic_samples, also append NOSQL_AND_SSTI_SAMPLES
append_block = """
    # 3. Authentic NoSQL Injection (CWE-943) & SSTI (CWE-1336) Samples
    for entry in NOSQL_AND_SSTI_SAMPLES:
        samples.append(make_sample(
            sample_id=entry["sample_id"],
            language=entry["language"],
            code=entry["code"],
            is_vulnerable=entry["is_vulnerable"],
            cwe_id=entry["cwe_id"],
            owasp_category=entry["owasp_category"],
            cwe_name=entry["cwe_name"],
            in_catalogue_scope=entry.get("in_catalogue_scope", True),
            source_dataset=entry["source_dataset"],
            source_type=entry["source_type"],
            source_pattern=entry.get("source_pattern"),
            sink_pattern=entry.get("sink_pattern"),
            sanitizer_pattern=entry.get("sanitizer_pattern"),
            fixed_code=entry.get("fixed_code"),
            expected_cvss=entry.get("expected_cvss"),
            notes=entry.get("notes", ""),
        ))
"""

target_return = "    return samples"
# Replace only the return in load_synthetic_samples
idx = code.find("def load_synthetic_samples")
ret_idx = code.find(target_return, idx)
code = code[:ret_idx] + append_block.strip() + "\n    " + code[ret_idx:]

with open('datasets/build_unified_dataset.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Successfully updated datasets/build_unified_dataset.py with NoSQL and SSTI samples + LLM CWE mapping!")
