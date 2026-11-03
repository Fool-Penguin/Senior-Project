import difflib
import sys

sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from app.api.apply import apply_unified_diff

# Case 1: Mismatched content (diff generated for another file or different lines)
orig = """line 1: apples
line 2: oranges
line 3: bananas
line 4: grapes
line 5: pears
"""

diff_mismatched = """--- a/f.py
+++ b/f.py
@@ -2,3 +2,3 @@
 line 2: pineapples
-line 3: kiwis
+line 3: mangoes
 line 4: grapes
"""

applied = apply_unified_diff(orig, diff_mismatched)
print("=== Mismatched lines ===")
print("Orig:\n", orig)
print("Applied:\n", applied)

# Case 2: Multi-hunk diff
orig_multi = "\n".join([f"line {i}" for i in range(1, 25)])
patched_multi = "\n".join([
    "line 1 (modified)" if i == 1 else ("line 20 (modified)" if i == 20 else f"line {i}")
    for i in range(1, 25)
])
diff_multi = "".join(difflib.unified_diff(
    orig_multi.splitlines(True),
    patched_multi.splitlines(True),
    fromfile="a/f.py",
    tofile="b/f.py"
))
print("\n=== Multi-hunk diff ===")
print(diff_multi)
applied_multi = apply_unified_diff(orig_multi, diff_multi)
print("Applied multi matches patched:", applied_multi.strip() == patched_multi.strip())

# Case 3: Empty file / new file diff
orig_empty = ""
patched_new = "def hello():\n    return 42\n"
diff_new = "".join(difflib.unified_diff(
    orig_empty.splitlines(True),
    patched_new.splitlines(True),
    fromfile="a/f.py",
    tofile="b/f.py"
))
print("\n=== New file diff ===")
print(diff_new)
applied_new = apply_unified_diff(orig_empty, diff_new)
print("Applied new:\n", applied_new)
print("Applied new matches patched:", applied_new.strip() == patched_new.strip())

# Case 4: Delete all lines
orig_del = "some content\nmore content\n"
patched_del = ""
diff_del = "".join(difflib.unified_diff(
    orig_del.splitlines(True),
    patched_del.splitlines(True),
    fromfile="a/f.py",
    tofile="b/f.py"
))
print("\n=== Delete all diff ===")
print(diff_del)
applied_del = apply_unified_diff(orig_del, diff_del)
print("Applied del matches patched:", applied_del.strip() == patched_del.strip())
