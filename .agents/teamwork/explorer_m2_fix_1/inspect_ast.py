import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.parser.cst_manager import CSTParserManager

cst = CSTParserManager.get_instance()

def dump_node(node, source_bytes, indent=0):
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    text_snippet = text if len(text) <= 30 else text[:27] + "..."
    text_snippet = text_snippet.replace("\n", "\\n")
    print("  " * indent + f"({node.type} [{node.start_point.row}:{node.start_point.column}-{node.end_point.row}:{node.end_point.column}] '{text_snippet}')")
    for child in node.children:
        dump_node(child, source_bytes, indent + 1)

cases = [
    ("python", '"%s" % (username,)'),
    ("python", '"%s" % (username)'),
    ("python", '"%s %s" % (user, role)'),
    ("python", '"%s" % [username]'),
    ("python", '"%s" % {"u": username}'),
    ("javascript", '["a", username]'),
    ("javascript", '({u: username})'),
    ("typescript", '<any>(username)'),
]

for lang, code in cases:
    print(f"\n==================== {lang}: {code} ====================")
    b = code.encode("utf-8")
    t = cst.parse(code, lang)
    dump_node(t.root_node, b)
