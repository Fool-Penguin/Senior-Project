import sys
from pathlib import Path
sys.path.insert(0, str(Path("codedee/codedee_server").resolve()))
import asyncio
try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except Exception:
    pass
import uvicorn
from app.main import app
import threading
import time
import requests
import traceback

def run_srv():
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8998,
        log_level="debug",
        http="h11",
        loop="asyncio:SelectorEventLoop",
    )
    server = uvicorn.Server(config)
    server.run()

t = threading.Thread(target=run_srv, daemon=True)
t.start()
time.sleep(1.5)

code = 'def find_user(name):\n    cursor.execute(f"SELECT * FROM users WHERE name = \'{name}\'")\n'

try:
    print("Sending request...")
    r = requests.post("http://127.0.0.1:8998/api/generate-patches", json={"issue_id": "GATES_TEST", "code_content": code, "candidate_count": 3}, timeout=30)
    print("Response status:", r.status_code)
    print("Response body:", r.text[:200])
except Exception as e:
    traceback.print_exc()
