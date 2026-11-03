import difflib
import json
import os
import subprocess
import tempfile

orig = """      return new ParameterizedSQL(columnName + ' @> array[' + operatorValue.map((v) => `'${v}'`) + ']::'
        + propertyDefinition.postgresql.dataType);
      return new ParameterizedSQL(`to_tsvector(${columnName}) @@ to_tsquery('${operatorValue}')`);"""

fixed = """      return new ParameterizedSQL(columnName + ' @> array[' + operatorValue.map(() => '?') + ']::'
        + propertyDefinition.postgresql.dataType,
        operatorValue);
      return new ParameterizedSQL(`to_tsvector(${columnName}) @@ to_tsquery(?)`, [operatorValue]);"""

# Without trailing newline
orig_lines = [line + "\n" for line in orig.splitlines()]
patch_lines = [line + "\n" for line in fixed.splitlines()]
diff_lines = list(difflib.unified_diff(orig_lines, patch_lines, fromfile="a/test.js", tofile="b/test.js"))
diff_text = "".join(diff_lines)

# Now test: if the file on disk HAS a trailing newline:
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, check=True, capture_output=True)
    
    with open(os.path.join(tmp, "test.js"), "w", encoding="utf-8") as f:
        f.write(orig + "\n")

    subprocess.run(["git", "add", "test.js"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, check=True, capture_output=True)

    proc = subprocess.run(["git", "apply", "-v", "-"], input=diff_text, text=True, cwd=tmp, capture_output=True)
    print("=== WITH TRAILING NEWLINE ON DISK ===")
    print("Returncode:", proc.returncode)
    print("STDOUT:", proc.stdout)
    print("STDERR:", proc.stderr)

# Now test what standard git diff produces when a file lacks a trailing newline!
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, check=True, capture_output=True)
    
    with open(os.path.join(tmp, "test.js"), "w", encoding="utf-8") as f:
        f.write(orig)

    subprocess.run(["git", "add", "test.js"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, check=True, capture_output=True)

    with open(os.path.join(tmp, "test.js"), "w", encoding="utf-8") as f:
        f.write(fixed)

    git_diff_proc = subprocess.run(["git", "diff"], cwd=tmp, check=True, capture_output=True, text=True)
    print("=== NATIVE GIT DIFF OUTPUT ===")
    print(git_diff_proc.stdout)
