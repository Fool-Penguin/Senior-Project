import sys, os
import networkx as nx
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from app.graphs.dfg import DFGBuilder

b = DFGBuilder()
code = '''
def chain(user):
    step1 = f"prefix_{user}"
    step2 = f"middle_{step1}"
    step3 = f"SELECT * FROM t WHERE id = '{step2}'"
    return step3
'''
g = b.build_for_code(code, "python", "chain.py")
for n, d in g.nodes(data=True):
    print("Node:", n, d.get("node_kind"), d.get("var_name"))
for u, v, d in g.edges(data=True):
    print("Edge:", u, "->", v, d)
