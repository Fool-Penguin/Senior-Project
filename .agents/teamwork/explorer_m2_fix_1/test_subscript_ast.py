import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.parser.cst_manager import CSTParserManager

c = CSTParserManager.get_instance()
t = c.parse('u = req.args["user"]', 'python')
sub = t.root_node.children[0].children[0].children[-1]
print('val:', sub.child_by_field_name('value'), 'sub:', sub.child_by_field_name('subscript'))

t_js = c.parse('let u = req.args["user"];', 'javascript')
sub_js = t_js.root_node.children[0].children[1].children[-1]
print('val_js:', sub_js.child_by_field_name('object'), 'sub_js:', sub_js.child_by_field_name('index'))
