import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.graphs.dfg import DFGBuilder

b = DFGBuilder()

def inspect_dfg(code, lang="python"):
    print(f"\n==================== {lang}: {code.strip()} ====================")
    g = b.build_for_code(code, lang)
    print("Nodes:")
    for n, d in g.nodes(data=True):
        print(f"  {n}: kind={d.get('node_kind')}, var={d.get('var_name')}, text={repr(d.get('expression_text'))}")
    print("Edges:")
    for u, v, d in g.edges(data=True):
        print(f"  {u} -> {v}: flow={d.get('flow_type')}, op={d.get('operation')}")

inspect_dfg("""
def test_tuple():
    u = req.get("u")
    sql = "SELECT * FROM t WHERE x = %s" % (u,)
""")

inspect_dfg("""
def test_paren():
    u = req.get("u")
    sql = "SELECT * FROM t WHERE x = %s" % (u)
""")

inspect_dfg("""
def test_list():
    u = req.get("u")
    sql = "SELECT * FROM t WHERE x = %s" % [u]
""")

inspect_dfg("""
def test_subscript():
    u = req.args['u']
""")

inspect_dfg("""
function test_await() {
    let u = await req.query.u;
}
""", "javascript")
