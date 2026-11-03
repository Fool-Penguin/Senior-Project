import sys
from pathlib import Path
import pytest

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

# Run pytest on test_treesitter_graphs.py
pytest.main(["-v", str(SERVER_ROOT / "tests" / "test_treesitter_graphs.py")])
