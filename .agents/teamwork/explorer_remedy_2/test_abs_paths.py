import os
from pathlib import Path
from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()
repo_root = Path('.').resolve()
controller_path = str(repo_root / 'Security_CWE' / 'cross_file_demo' / 'api_controller.py')
storage_path = str(repo_root / 'Security_CWE' / 'cross_file_demo' / 'storage_service.py')
findings = walker.analyze_files([controller_path, storage_path])
print(f"Total findings with abs paths: {len(findings)}")
for i, f in enumerate(findings):
    print(f"Finding {i}: sanitized={f.sanitized}, sink_symbol={f.sink_node.get('symbol')}, sink_file={f.sink_node.get('file')}")
