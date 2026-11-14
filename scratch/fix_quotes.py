import pathlib
import py_compile

p = pathlib.Path("scripts/run_full_scale_benchmark.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines):
    if "CWE-78" in line or "CWE-798" in line or "CWE-327" in line or "CWE-328" in line:
        # Replace raw double-quoted regexes containing unescaped " with single-quoted raw strings containing [\'"]
        lines[i] = line.replace('r"exec\\s*\\(\\s*[`\'"]"', "r'exec\\s*\\(\\s*[`\\'\"]'")
        lines[i] = lines[i].replace('r"password\\s*=\\s*[\'"]"', "r'password\\s*=\\s*[\\'\"]'")
        lines[i] = lines[i].replace('r"jwt\\.sign\\s*\\([^,]+,\\s*[\'"]"', "r'jwt\\.sign\\s*\\([^,]+,\\s*[\\'\"]'")
        lines[i] = lines[i].replace('r"createCipheriv\\s*\\(\\s*[\'"]des"', "r'createCipheriv\\s*\\(\\s*[\\'\"]des'")
        lines[i] = lines[i].replace('r"createHash\\s*\\(\\s*[\'"]md5"', "r'createHash\\s*\\(\\s*[\\'\"]md5'")
        lines[i] = lines[i].replace('r"createHash\\s*\\(\\s*[\'"]sha1"', "r'createHash\\s*\\(\\s*[\\'\"]sha1'")

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("Syntax compiled cleanly!")
