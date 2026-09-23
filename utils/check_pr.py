import urllib.request
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

token = None
for p in [Path(".env"), Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"]:
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GITHUB_TOKEN"):
                    token = line.split("=", 1)[1].strip().strip('"')
        if token:
            break

headers = {
    "User-Agent": "Test/1.0",
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

url = "https://api.github.com/repos/mem0ai/mem0/pulls/7269"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("PR Title:", data.get("title"))
        print("PR User:", data.get("user", {}).get("login"))
        print("Head ref:", data.get("head", {}).get("ref"))
        print("Labels:", [l.get("name") for l in data.get("labels", [])])
        print("Body Full:\n", data.get("body"))
except Exception as e:
    print("Error:", e)
