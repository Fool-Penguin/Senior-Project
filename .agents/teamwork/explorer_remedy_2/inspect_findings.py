from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()
controller_path = 'Security_CWE/cross_file_demo/api_controller.py'
storage_path = 'Security_CWE/cross_file_demo/storage_service.py'
findings = walker.analyze_files([controller_path, storage_path])
print(f"Total findings: {len(findings)}")
for i, f in enumerate(findings):
    print(f"=== Finding {i} ===")
    print(f"  sanitized: {f.sanitized}")
    print(f"  severity: {f.severity}")
    print(f"  source file: {f.source_node.get('file')}:{f.source_node.get('line')}")
    print(f"  source expr: {f.source_node.get('expression')}")
    print(f"  sink file: {f.sink_node.get('file')}:{f.sink_node.get('line')}")
    print(f"  sink expr: {f.sink_node.get('expression')}")
    print(f"  taint_path steps ({len(f.taint_path)}):")
    for s in f.taint_path:
        print(f"    - L{s.get('line')} {s.get('file')}: {s.get('symbol')} ({s.get('operation')}) -> {s.get('code_snippet')}")
