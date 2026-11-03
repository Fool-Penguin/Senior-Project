"""
Python Bridge for Native JavaScript AST Parser (Babel & Acorn)
Executes Node.js child process to benchmark standard JavaScript AST engines.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any

JS_PARSER_SCRIPT = Path(__file__).parent / "js_ast_parser.js"


class JavaScriptNativeAstBridge:
    """Invokes Babel and Acorn AST parsers via Node.js."""

    def __init__(self):
        self.script_path = JS_PARSER_SCRIPT

    def benchmark_file(self, file_path: str, iterations: int = 100) -> Dict[str, Any]:
        """Runs Node benchmark script and parses JSON output."""
        cmd = ["node", str(self.script_path), str(file_path), str(iterations)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_error_recovery(self, broken_code_path: str) -> Dict[str, Any]:
        """Tests Acorn and Babel on syntax error files."""
        acorn_path = (Path(__file__).parent.parent.parent / "node_modules/acorn").as_posix()
        babel_path = (Path(__file__).parent.parent.parent / "node_modules/@babel/parser").as_posix()
        file_path = Path(broken_code_path).as_posix()

        node_eval = f"""
        const fs = require('fs');
        const acorn = require('{acorn_path}');
        const babel = require('{babel_path}');
        const code = fs.readFileSync('{file_path}', 'utf-8');
        
        let acornThrew = false;
        let acornErr = null;
        try {{
          acorn.parse(code, {{ ecmaVersion: 'latest' }});
        }} catch (e) {{
          acornThrew = true;
          acornErr = e.message;
        }}

        let babelThrew = false;
        let babelErr = null;
        try {{
          babel.parse(code, {{ errorRecovery: false }});
        }} catch (e) {{
          babelThrew = true;
          babelErr = e.message;
        }}

        console.log(JSON.stringify({{
          acorn_fatal_abort: acornThrew,
          acorn_error: acornErr,
          babel_fatal_abort: babelThrew,
          babel_error: babelErr
        }}));
        """
        proc = subprocess.run(["node", "-e", node_eval], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)
