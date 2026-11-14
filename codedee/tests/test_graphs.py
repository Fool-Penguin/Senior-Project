"""
Unit tests for Stage 1 (Tree-sitter Parser) & Stage 2 (NetworkX Intermediate Graphs).
Verifies parsing and graph generation across Python, JavaScript, and TypeScript.
"""

import unittest
from codedee.core.parser import CodeDEEParser
from codedee.core.graph_builder import GraphBuilder


class TestStage1And2(unittest.TestCase):

    def test_python_parsing_and_graphs(self):
        code = """
def execute_query(user_id):
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    if user_id > 0:
        db.cursor.execute(query)
    return query
"""
        graphs = GraphBuilder.build_all(code, "python")
        self.assertEqual(len(graphs.functions), 1)
        fn = graphs.functions[0]
        self.assertEqual(fn.name, "execute_query")
        self.assertIn("user_id", fn.parameters)

        # Call Graph check
        self.assertTrue(graphs.call_graph.has_node("execute_query"))

        # CFG check
        self.assertTrue(graphs.cfg.has_node("execute_query:entry"))
        self.assertTrue(graphs.cfg.has_node("execute_query:exit"))

        # DFG check (Parameter taint to variable to sink)
        dfg_nodes = dict(graphs.dfg.nodes(data=True))
        param_nodes = [n for n, d in dfg_nodes.items() if d.get("kind") == "param_source"]
        self.assertTrue(len(param_nodes) > 0)
        self.assertIn("execute_query:param:user_id", param_nodes)

        # Edges from param to var assignment
        var_nodes = [n for n, d in dfg_nodes.items() if d.get("kind") == "variable_def"]
        self.assertTrue(len(var_nodes) > 0)

        # Sinks (call to db.cursor.execute)
        sink_nodes = [n for n, d in dfg_nodes.items() if d.get("kind") == "call_sink"]
        self.assertTrue(len(sink_nodes) > 0)

    def test_javascript_parsing_and_graphs(self):
        code = """
function serveFile(req, res) {
    const filename = req.params.file;
    if (filename) {
        fs.readFile(filename, (err, data) => {
            res.send(data);
        });
    }
}
"""
        graphs = GraphBuilder.build_all(code, "javascript")
        self.assertTrue(len(graphs.functions) >= 1)
        root_fn = [f for f in graphs.functions if f.name == "serveFile"][0]
        self.assertIn("req", root_fn.parameters)
        self.assertIn("res", root_fn.parameters)

        # Call Graph
        self.assertTrue(graphs.call_graph.has_node("serveFile"))

        # DFG Taint propagation
        dfg_nodes = dict(graphs.dfg.nodes(data=True))
        self.assertIn("serveFile:param:req", dfg_nodes)

    def test_typescript_parsing_and_graphs(self):
        code = """
async function runCommand(cmd: string): Promise<string> {
    const safeCmd: string = cmd.trim();
    if (safeCmd.length > 0) {
        return execSync(safeCmd).toString();
    }
    return "";
}
"""
        graphs = GraphBuilder.build_all(code, "typescript")
        self.assertEqual(len(graphs.functions), 1)
        fn = graphs.functions[0]
        self.assertEqual(fn.name, "runCommand")
        self.assertIn("cmd", fn.parameters)

        # CFG & DFG
        self.assertTrue(graphs.cfg.has_node("runCommand:entry"))
        self.assertTrue(graphs.dfg.has_node("runCommand:param:cmd"))


if __name__ == "__main__":
    unittest.main()
