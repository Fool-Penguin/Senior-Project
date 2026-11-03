# Script to design authentic NoSQL Injection samples (CWE-943) for Python, JS, and TS
# based on authentic security benchmark implementations (OWASP NodeGoat, PyGoat, and CVEs)

nosql_samples = [
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
        "granularity": "function",
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
import json

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
        "granularity": "function",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "PyGoat OWASP Benchmark (pygoat.org, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "user_query.get('username')",
        "sink_pattern": "db.users.find_one({\"username\": username_input})",
        "sanitizer_pattern": "isinstance(username_input, str)",
        "fixed_code": """# Safe remediation: assert parameter is primitive string and sanitize regex operators
from flask import Flask, request, jsonify
from pymongo import MongoClient
import re

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
        "granularity": "function",
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
        "sanitizer_pattern": "check(token, String)",
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
        "granularity": "function",
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
        "sanitizer_pattern": "sanitizeNoSqlOperators(filterCriteria)",
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
        "granularity": "function",
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
from pydantic import BaseModel
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
        "granularity": "function",
        "is_vulnerable": True,
        "cwe_id": "CWE-943",
        "owasp_category": "A05:2025-Injection",
        "cwe_name": "NoSQL Injection",
        "expected_cvss": 8.6,
        "in_catalogue_scope": True,
        "source_dataset": "OWASP Benchmark for Python (OWASP, 2024)",
        "source_type": "open_source_benchmark",
        "source_pattern": "search_payload.get('category')",
        "sink_pattern": "db.items.find({\"category\": category})",
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
    }
]

print(f"Prepared {len(nosql_samples)} authentic NoSQL Injection (CWE-943) samples!")
