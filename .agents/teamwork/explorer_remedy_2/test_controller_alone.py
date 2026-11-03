from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()
with open("Security_CWE/cross_file_demo/api_controller.py", "r", encoding="utf-8") as f:
    code = f.read()

findings = walker.analyze_code(code, "python", "Security_CWE/cross_file_demo/api_controller.py")
print(f"Total findings on api_controller alone: {len(findings)}")
for i, f in enumerate(findings):
    print(f"Finding {i}: sanitized={f.sanitized}, severity={f.severity}, sink={f.sink_node.get('expression')}")
