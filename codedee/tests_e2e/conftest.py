"""
conftest.py - Pytest Fixtures and Configuration for CodeDEE E2E Test Suite.

Provides unified opaque-box API client (live HTTP or in-memory TestClient),
dataset loaders, and workspace isolation fixtures across Tiers 1-4.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import requests

if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Ensure codedee_server is on sys.path
CODEDEE_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = CODEDEE_ROOT / "codedee_server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import threading
import time
import uvicorn
from app.main import app
from fastapi.testclient import TestClient

_LIVE_PORT = 8000
_SERVER_STARTED = False
_LOCK = threading.Lock()


def _ensure_live_server() -> int:
    """Ensure a live HTTP backend is running, starting an in-process uvicorn thread if needed."""
    global _SERVER_STARTED, _LIVE_PORT
    with _LOCK:
        if _SERVER_STARTED:
            return _LIVE_PORT

        # Check port 8000 first
        s = requests.Session()
        try:
            r = s.get(f"http://127.0.0.1:{_LIVE_PORT}/health", timeout=0.3)
            if r.status_code in (200, 503):
                _SERVER_STARTED = True
                return _LIVE_PORT
        except Exception:
            pass

        # Try starting on 8000, fallback to 8765
        for port in (8000, 8765):
            try:
                config = uvicorn.Config(
                    app,
                    host="127.0.0.1",
                    port=port,
                    log_level="error",
                    http="h11",
                    loop="asyncio:SelectorEventLoop",
                )
                server = uvicorn.Server(config)
                t = threading.Thread(target=server.run, daemon=True)
                t.start()

                # Wait for server to come up
                for _ in range(30):
                    time.sleep(0.1)
                    try:
                        r = s.get(f"http://127.0.0.1:{port}/health", timeout=0.3)
                        if r.status_code in (200, 503):
                            _LIVE_PORT = port
                            _SERVER_STARTED = True
                            return _LIVE_PORT
                    except Exception:
                        pass
            except Exception:
                continue

        return _LIVE_PORT


class ApiClientWrapper:
    """
    Transparent API Client wrapper.
    Directs requests over HTTP to live uvicorn server with session connection pooling.
    """

    def __init__(self, base_url: Optional[str] = None):
        port = _ensure_live_server()
        self.base_url = (base_url or f"http://127.0.0.1:{port}").rstrip("/")
        self._session = requests.Session()

    def get(self, path: str, **kwargs):
        """Send GET request."""
        clean_path = "/" + path.lstrip("/")
        return self._session.get(f"{self.base_url}{clean_path}", **kwargs)

    def post(self, path: str, **kwargs):
        """Send POST request."""
        clean_path = "/" + path.lstrip("/")
        return self._session.post(f"{self.base_url}{clean_path}", **kwargs)


@pytest.fixture(scope="session")
def client() -> ApiClientWrapper:
    """Session-scoped API Client fixture."""
    return ApiClientWrapper()


@pytest.fixture(scope="session")
def in_memory_client() -> TestClient:
    """Guaranteed in-memory TestClient fixture."""
    return TestClient(app)


@pytest.fixture(scope="session")
def dataset_path() -> Path:
    """Path to extracted mini_test_datasets.json."""
    path = SERVER_DIR / "data" / "mini_test_datasets.json"
    if not path.exists():
        pytest.fail(f"Dataset missing at {path}. Run extraction first.")
    return path


@pytest.fixture(scope="session")
def mini_datasets(dataset_path: Path) -> List[Dict[str, Any]]:
    """Loads all records from mini_test_datasets.json."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="session")
def datasets_by_id(mini_datasets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index dataset records by sample_id."""
    return {rec["sample_id"]: rec for rec in mini_datasets}


@pytest.fixture
def py_cwe89_sample(datasets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Curated Python SQL Injection sample SEC_PY_CWE89_001."""
    return datasets_by_id.get("SEC_PY_CWE89_001") or next(
        r for r in datasets_by_id.values() if r["language"] == "python" and r["Is_vulnerable"]
    )


@pytest.fixture
def js_cwe89_sample(datasets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Curated JavaScript SQL Injection sample SEC_JS_CWE89_001."""
    return datasets_by_id.get("SEC_JS_CWE89_001") or next(
        r for r in datasets_by_id.values() if r["language"] == "javascript" and r["Is_vulnerable"]
    )


@pytest.fixture
def ts_cwe89_sample(datasets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Curated TypeScript SQL Injection sample SEC_TS_JUICE_SHOP_001."""
    return datasets_by_id.get("SEC_TS_JUICE_SHOP_001") or next(
        r for r in datasets_by_id.values() if r["language"] == "typescript" and r["Is_vulnerable"]
    )


@pytest.fixture
def temp_workspace(tmp_path: Path):
    """
    Isolated temporary filesystem workspace for file scan and patch application tests.
    """
    class Workspace:
        def __init__(self, root: Path):
            self.root = root

        def create_file(self, filename: str, content: str) -> Path:
            p = self.root / filename
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return p

        def read_file(self, filename: str) -> str:
            p = self.root / filename
            return p.read_text(encoding="utf-8")

        def exists(self, filename: str) -> bool:
            return (self.root / filename).exists()

    return Workspace(tmp_path)
