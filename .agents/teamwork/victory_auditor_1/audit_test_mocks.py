from pathlib import Path

test_dirs = [Path("codedee/codedee_server/tests"), Path("codedee/tests_e2e")]
results = []

for td in test_dirs:
    for p in td.rglob("*.py"):
        content = p.read_text(encoding="utf-8")
        mocks = []
        for i, line in enumerate(content.splitlines(), 1):
            if "mock" in line.lower() or "patch" in line.lower():
                mocks.append((i, line.strip()))
        results.append((str(p), len(mocks), mocks))

for r in results:
    print(f"File: {r[0]} - Mock mentions: {r[1]}")
    if r[1] > 0:
        for m in r[2][:5]:
            print(f"   Line {m[0]}: {m[1]}")
