import sys

mods = [
    'fastapi',
    'uvicorn',
    'pydantic',
    'tree_sitter',
    'tree_sitter_python',
    'tree_sitter_javascript',
    'tree_sitter_typescript',
    'tree_sitter_languages',
    'networkx',
    'chromadb',
    'requests',
    'pytest'
]

print("Python version:", sys.version)
for mod in mods:
    try:
        m = __import__(mod)
        ver = getattr(m, '__version__', 'loaded')
        print(f"{mod}: INSTALLED ({ver})")
    except ImportError as e:
        print(f"{mod}: NOT INSTALLED ({e})")
