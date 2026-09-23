import json
import urllib.request

from pathlib import Path

token = None
for p in [Path(".env"), Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"]:
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GITHUB_TOKEN"):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
        if token:
            break

req = urllib.request.Request(
    "https://api.github.com/rate_limit",
    headers={"Authorization": f"token {token}", "User-Agent": "Test"}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(data["resources"]["core"])
