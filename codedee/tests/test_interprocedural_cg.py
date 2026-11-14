"""
CodeDEE - Unit and Integration Tests for Semester 2 Inter-Procedural Call Graph
Tests project-wide symbol resolution, cross-file edge construction, and backward reachability slicing.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codedee.core.symbol_resolver import ProjectSymbolResolver
from codedee.core.interprocedural_cg import InterproceduralCallGraph


class TestInterproceduralCallGraph(unittest.TestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_python_cross_file_call_resolution(self):
        """Test multi-file Python call graph construction and backward reachability slicing."""
        # File 1: HTTP Controller
        routes_py = self.root / "routes.py"
        routes_py.write_text(
            """
from services import authenticate_user

def login_route(username, password):
    user = authenticate_user(username, password)
    return {"user": user}
""",
            encoding="utf-8",
        )

        # File 2: Service Layer
        services_py = self.root / "services.py"
        services_py.write_text(
            """
from db import run_sql_query

def authenticate_user(user_arg, pass_arg):
    query = f"SELECT * FROM users WHERE u='{user_arg}'"
    return run_sql_query(query)
""",
            encoding="utf-8",
        )

        # File 3: Database Layer (Sink)
        db_py = self.root / "db.py"
        db_py.write_text(
            """
import sqlite3

def run_sql_query(raw_sql):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(raw_sql)
    return cursor.fetchall()
""",
            encoding="utf-8",
        )

        # Initialize and Index
        resolver = ProjectSymbolResolver(self.root)
        resolver.index_project()

        # Verify Symbol Indexing
        self.assertIn("routes.py:login_route", resolver.symbols)
        self.assertIn("services.py:authenticate_user", resolver.symbols)
        self.assertIn("db.py:run_sql_query", resolver.symbols)

        # Build Inter-Procedural Graph
        cg = InterproceduralCallGraph(resolver)
        cg.build_project_graph()

        # Verify Directed Edges
        self.assertTrue(cg.graph.has_edge("routes.py:login_route", "services.py:authenticate_user"))
        self.assertTrue(cg.graph.has_edge("services.py:authenticate_user", "db.py:run_sql_query"))

        # Test Backward Reachability Slicing from the Sink
        sink_id = "db.py:run_sql_query"
        chains = cg.get_backward_call_chains(sink_id, max_depth=4)
        self.assertTrue(len(chains) >= 1)

        expected_chain = [
            "routes.py:login_route",
            "services.py:authenticate_user",
            "db.py:run_sql_query",
        ]
        self.assertEqual(chains[0], expected_chain)

        # Test Taint Context Construction
        taint_ctx = cg.build_taint_context(sink_id, sink_callee="cursor.execute")
        self.assertIsNotNone(taint_ctx)
        self.assertEqual(taint_ctx.source_function, "login_route")
        self.assertEqual(taint_ctx.source_file, "routes.py")
        self.assertIn("username", taint_ctx.untrusted_params)
        self.assertEqual(taint_ctx.call_depth, 2)
        self.assertEqual(len(taint_ctx.call_chain), 2)

    def test_javascript_cross_file_call_resolution(self):
        """Test multi-file JavaScript/TypeScript import resolution and call edges."""
        # File 1: Express Controller
        controller_js = self.root / "controller.js"
        controller_js.write_text(
            """
import { executeCommand } from './executor';

export function handlePing(req, res) {
    const host = req.query.host;
    executeCommand(host);
}
""",
            encoding="utf-8",
        )

        # File 2: System Executor (Sink)
        executor_js = self.root / "executor.js"
        executor_js.write_text(
            """
const { exec } = require('child_process');

export function executeCommand(cmd) {
    exec("ping -c 1 " + cmd);
}
""",
            encoding="utf-8",
        )

        resolver = ProjectSymbolResolver(self.root)
        resolver.index_project()

        self.assertIn("controller.js:handlePing", resolver.symbols)
        self.assertIn("executor.js:executeCommand", resolver.symbols)

        cg = InterproceduralCallGraph(resolver)
        cg.build_project_graph()

        self.assertTrue(cg.graph.has_edge("controller.js:handlePing", "executor.js:executeCommand"))

        # Backward slice
        chains = cg.get_backward_call_chains("executor.js:executeCommand", max_depth=3)
        self.assertEqual(chains[0], ["controller.js:handlePing", "executor.js:executeCommand"])


if __name__ == "__main__":
    unittest.main()
