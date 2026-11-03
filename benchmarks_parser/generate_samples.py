"""
Generates all separated test code samples for Python and JavaScript benchmarks.
Files are placed strictly under:
  - benchmarks_parser/samples/python/
  - benchmarks_parser/samples/javascript/
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent / "samples"
py_dir = BASE_DIR / "python"
js_dir = BASE_DIR / "javascript"
py_dir.mkdir(parents=True, exist_ok=True)
js_dir.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# 1. Large Python API Controller (~1,200 LOC)
# ------------------------------------------------------------------------------
large_py_lines = [
    "# ==============================================================================",
    "# Large Enterprise API Controller Module (~1,200 LOC)",
    "# Contains 40 controller classes, routing decorators, validation hooks,",
    "# and rich comment trivia for realistic benchmark parsing.",
    "# ==============================================================================",
    "from typing import Dict, List, Optional, Any",
    "import json",
    "import datetime",
    ""
]
for i in range(1, 41):
    large_py_lines.extend([
        f"class EndpointController_{i}:",
        f"    '''Controller handling dispatch for route cluster {i}.'''",
        f"    ENDPOINT_VERSION = 'v2.{i}'",
        f"    ROUTE_PREFIX = '/api/v2/service_{i}'",
        "",
        f"    def __init__(self, tenant_id: str, quota_limit: int = 1000):",
        f"        # Tenant identifier configuration",
        f"        self.tenant_id = tenant_id",
        f"        self.quota_limit = quota_limit",
        f"        self.active_calls = 0  # live counter",
        "",
        f"    def handle_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:",
        f"        # Step 1: Pre-validation checks",
        f"        if not payload:",
        f"            return {{'error': 'Empty payload for endpoint {i}', 'code': 400}}",
        f"        self.active_calls += 1",
        f"        # Step 2: Extract normalized parameters",
        f"        entity_id = payload.get('id', 'default_{i}')",
        f"        action = payload.get('action', 'read')",
        f"        # Step 3: Compute response metrics",
        f"        processed_keys = [k for k in payload.keys() if k.startswith('param_')]",
        f"        return {{",
        f"            'controller': 'EndpointController_{i}',",
        f"            'entity_id': entity_id,",
        f"            'action': action,",
        f"            'keys_count': len(processed_keys),",
        f"            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),",
        f"            'status': 200",
        f"        }}",
        "",
        f"    def reset_quota(self, admin_token: str) -> bool:",
        f"        # Verify admin credentials before reset",
        f"        if admin_token != 'adm_super_token':",
        f"            return False",
        f"        self.active_calls = 0",
        f"        return True",
        ""
    ])

(py_dir / "large_api_controller.py").write_text("\n".join(large_py_lines), encoding="utf-8")

# ------------------------------------------------------------------------------
# 2. Broken Python Syntax (Simulating live keystroke mid-edit)
# ------------------------------------------------------------------------------
broken_py = """# Incomplete syntax sample mid-typing
def process_user_registration(user_id: int, request_data: dict):
    # Developer is currently typing an if-condition without closing parenthesis:
    if (user_id is not None and len(request_data) > 0
        print("Incomplete syntax statement")
    return True
"""
(py_dir / "broken_syntax_edit.py").write_text(broken_py, encoding="utf-8")

# ------------------------------------------------------------------------------
# 3. Python Multi-File Project Mini-Package
# ------------------------------------------------------------------------------
pkg_py_dir = py_dir / "multi_file_project"
pkg_py_dir.mkdir(parents=True, exist_ok=True)
(pkg_py_dir / "__init__.py").write_text('"""CodeDEE Core Micro-Package."""\n__version__ = "1.0.0"\n', encoding="utf-8")
(pkg_py_dir / "config.py").write_text("""# Configuration module
import os
class AppConfig:
    DEBUG = os.getenv("APP_DEBUG", "False").lower() == "true"
    DB_URI = os.getenv("DB_URI", "sqlite:///app.db")
    MAX_PAYLOAD_SIZE = 1048576  # 1 MB
""", encoding="utf-8")
(pkg_py_dir / "models.py").write_text("""# Data Models module
from dataclasses import dataclass

@dataclass
class UserRecord:
    # Primary user entity
    user_id: int
    username: str
    email: str
    is_active: bool = True
""", encoding="utf-8")
(pkg_py_dir / "middleware.py").write_text("""# Middleware verification module
class SecurityHeaderMiddleware:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        # Attach defense-in-depth security headers
        def custom_start_response(status, headers, exc_info=None):
            headers.append(("X-Content-Type-Options", "nosniff"))
            headers.append(("X-Frame-Options", "DENY"))
            return start_response(status, headers, exc_info)
        return self.app(environ, custom_start_response)
""", encoding="utf-8")
(pkg_py_dir / "routes.py").write_text("""# Route handlers module
from .config import AppConfig
from .models import UserRecord

def index_route(request):
    # Public health check
    return {"status": "ok", "debug": AppConfig.DEBUG}

def get_user_route(request, uid: int):
    # Return user record safely
    user = UserRecord(user_id=uid, username="alice", email="alice@example.com")
    return {"user": user.__dict__}
""", encoding="utf-8")

# ------------------------------------------------------------------------------
# 4. Small JavaScript JWT Helper (~25 LOC)
# ------------------------------------------------------------------------------
small_js = """// Small JWT Helper Module
const crypto = require('crypto');

// Minimum security entropy requirement
const TOKEN_EXPIRY_MS = 3600000; // 1 hour

function createHmacToken(payload, secretKey) {
  // Validate secret key boundary
  if (!secretKey || secretKey.length < 32) {
    throw new Error('Secret key must have at least 256 bits');
  }
  const serialized = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signature = crypto.createHmac('sha256', secretKey)
    .update(serialized)
    .digest('base64url');
  return `${serialized}.${signature}`;
}

function verifyHmacToken(rawToken, secretKey) {
  // Constant time comparison against timing attack
  const parts = rawToken.split('.');
  if (parts.length !== 2) return null;
  const [data, signature] = parts;
  const expectedSig = crypto.createHmac('sha256', secretKey).update(data).digest('base64url');
  if (crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSig))) {
    return JSON.parse(Buffer.from(data, 'base64url').toString('utf-8'));
  }
  return null;
}

module.exports = { createHmacToken, verifyHmacToken };
"""
(js_dir / "small_jwt_helper.js").write_text(small_js, encoding="utf-8")

# ------------------------------------------------------------------------------
# 5. Medium JavaScript Express Router (~250 LOC)
# ------------------------------------------------------------------------------
medium_js_lines = [
    "// Medium Express Route Controller Module (~250 LOC)",
    "// Contains multi-endpoint routing, async error handling, and parameter validation",
    "const express = require('express');",
    "const router = express.Router();",
    ""
]
for i in range(1, 16):
    medium_js_lines.extend([
        f"// Route handler cluster {i}",
        f"router.get('/items/{i}/:itemId', async (req, res, next) => {{",
        f"  // Extract item id parameter cleanly",
        f"  const itemId = req.params.itemId;",
        f"  if (!itemId || !/^[0-9]+$/.test(itemId)) {{",
        f"    return res.status(400).json({{ error: 'Invalid item ID format' }});",
        f"  }}",
        f"  try {{",
        f"    // Simulate database lookup",
        f"    const record = {{ id: parseInt(itemId, 10), cluster: {i}, active: true }};",
        f"    res.json({{ data: record, status: 'success' }});",
        f"  }} catch (err) {{",
        f"    // Delegate to centralized error middleware",
        f"    next(err);",
        f"  }}",
        f"}});",
        f"",
        f"router.post('/items/{i}', async (req, res, next) => {{",
        f"  // Input validation with defense-in-depth bounds",
        f"  const body = req.body || {{}};",
        f"  if (!body.title || typeof body.title !== 'string') {{",
        f"    return res.status(422).json({{ error: 'Missing title' }});",
        f"  }}",
        f"  const sanitizedTitle = body.title.trim().slice(0, 100);",
        f"  res.status(201).json({{ created: true, title: sanitizedTitle, cluster: {i} }});",
        f"}});",
        ""
    ])
(js_dir / "medium_express_router.js").write_text("\n".join(medium_js_lines), encoding="utf-8")

# ------------------------------------------------------------------------------
# 6. Large JavaScript Application Bundle (~1,200 LOC)
# ------------------------------------------------------------------------------
large_js_lines = [
    "// Large Full-Stack Client/Server Bundle (~1,200 LOC)",
    "// Contains 35 class components, middleware chains, and state stores",
    "class ServiceRegistry {",
    "  constructor() {",
    "    this.services = new Map();",
    "  }",
    "  register(name, instance) {",
    "    this.services.set(name, instance);",
    "  }",
    "}",
    ""
]
for i in range(1, 36):
    large_js_lines.extend([
        f"class DataStoreService_{i} {{",
        f"  // Service instance for domain {i}",
        f"  constructor(serviceRegistry) {{",
        f"    this.registry = serviceRegistry;",
        f"    this.cache = new Map();",
        f"    this.metrics = {{ hits: 0, misses: 0 }}; // inline metrics comment",
        f"  }}",
        f"",
        f"  get(key) {{",
        f"    // Lookup in local in-memory partition",
        f"    if (this.cache.has(key)) {{",
        f"      this.metrics.hits++;",
        f"      return this.cache.get(key);",
        f"    }}",
        f"    this.metrics.misses++;",
        f"    return null;",
        f"  }}",
        f"",
        f"  set(key, value, ttl = 300) {{",
        f"    // Evict if capacity exceeded",
        f"    if (this.cache.size >= 1000) {{",
        f"      const firstKey = this.cache.keys().next().value;",
        f"      this.cache.delete(firstKey);",
        f"    }}",
        f"    this.cache.set(key, {{ val: value, expires: Date.now() + ttl * 1000 }});",
        f"  }}",
        f"",
        f"  flush() {{",
        f"    // Full clean of storage domain {i}",
        f"    this.cache.clear();",
        f"  }}",
        f"}}",
        ""
    ])
(js_dir / "large_app_bundle.js").write_text("\n".join(large_js_lines), encoding="utf-8")

# ------------------------------------------------------------------------------
# 7. Broken JavaScript Syntax (Simulating live keystroke mid-edit)
# ------------------------------------------------------------------------------
broken_js = """// Incomplete syntax sample mid-typing
function handleUserAuth(req, res) {
  // Developer is currently typing an arrow function with missing bracket:
  const token = req.headers['authorization'];
  if (token && token.startsWith('Bearer ') {
    console.log("Syntax error here");
  return res.status(200);
}
"""
(js_dir / "broken_syntax_edit.js").write_text(broken_js, encoding="utf-8")

# ------------------------------------------------------------------------------
# 8. JavaScript Multi-File Project Mini-Package
# ------------------------------------------------------------------------------
pkg_js_dir = js_dir / "multi_file_project"
pkg_js_dir.mkdir(parents=True, exist_ok=True)
(pkg_js_dir / "package.json").write_text('{\n  "name": "codedee-micro-package",\n  "version": "1.0.0"\n}\n', encoding="utf-8")
(pkg_js_dir / "db.js").write_text("""// Database connector module
class DatabaseClient {
  constructor(uri) {
    this.uri = uri;
    this.connected = false;
  }
  async connect() {
    this.connected = true;
    return this;
  }
}
module.exports = { DatabaseClient };
""", encoding="utf-8")
(pkg_js_dir / "auth.js").write_text("""// Auth module
const crypto = require('crypto');
function sanitizeInput(str) {
  // Prevent prototype pollution keys
  if (str === '__proto__' || str === 'constructor') return '';
  return String(str || '').trim();
}
module.exports = { sanitizeInput };
""", encoding="utf-8")
(pkg_js_dir / "models.js").write_text("""// Model entities
class SecurityFinding {
  constructor(id, cwe, severity) {
    this.id = id;
    this.cwe = cwe;
    this.severity = severity;
    this.timestamp = Date.now();
  }
}
module.exports = { SecurityFinding };
""", encoding="utf-8")
(pkg_js_dir / "middleware.js").write_text("""// Express security middleware
function corsMiddleware(req, res, next) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
  next();
}
module.exports = { corsMiddleware };
""", encoding="utf-8")
(pkg_js_dir / "routes.js").write_text("""// Application routes
const { SecurityFinding } = require('./models');
function setupRoutes(app) {
  app.get('/api/findings', (req, res) => {
    const finding = new SecurityFinding('F-101', 'CWE-89', 'CRITICAL');
    res.json([finding]);
  });
}
module.exports = { setupRoutes };
""", encoding="utf-8")

print("All benchmark code samples generated successfully in benchmarks_parser/samples/")
