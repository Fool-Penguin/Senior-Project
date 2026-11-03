import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.parser.cst_manager import CSTParserManager

cst = CSTParserManager.get_instance()

def show_ast(code, lang):
    b = code.encode("utf-8")
    t = cst.parse(code, lang)
    def walk(n, indent=0):
        val = b[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
        val = val if len(val) < 25 else val[:22] + "..."
        print("  " * indent + f"{n.type} ('{val}')")
        for c in n.children:
            walk(c, indent + 1)
    print(f"--- {lang}: {code} ---")
    walk(t.root_node)

show_ast("a = (x, y)", "python")
show_ast("a = (x)", "python")
show_ast("a = [x, y]", "python")
show_ast("a = {'k': x}", "python")
show_ast("a = (x,)", "python")
show_ast("let a = [x, y];", "javascript")
show_ast("let a = (x);", "javascript")
show_ast("let a = {k: x};", "javascript")
show_ast("let a = x as any;", "typescript")
show_ast("let a = <any>x;", "typescript")
