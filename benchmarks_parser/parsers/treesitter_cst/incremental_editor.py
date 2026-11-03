"""
Incremental Editing Simulation for Tree-sitter CST
Demonstrates Tree-sitter's live keystroke incremental parsing algorithm:
  1. Base tree is parsed once.
  2. A developer types a character / statement (buffer modified).
  3. `tree.edit(...)` informs the CST of the exact byte delta.
  4. `parser.parse(new_bytes, old_tree)` re-uses unaffected subtrees and only re-parses the dirty nodes.
"""

import time
from typing import Tuple, Dict, Any
from tree_sitter import Parser, Tree


class IncrementalEditor:
    """Manages incremental edit benchmarking."""

    @staticmethod
    def simulate_edit(
        parser: Parser,
        original_bytes: bytes,
        insertion_bytes: bytes = b"# live edit\n",
        insert_line: int = 1
    ) -> Dict[str, Any]:
        """
        Executes and benchmarks an incremental re-parse against a full re-parse.
        """
        # Step 1: Initial base parse
        initial_tree = parser.parse(original_bytes)

        # Step 2: Compute edit offsets
        lines = original_bytes.split(b"\n")
        byte_offset = 0
        for i in range(min(insert_line, len(lines))):
            byte_offset += len(lines[i]) + 1  # include newline

        modified_bytes = original_bytes[:byte_offset] + insertion_bytes + original_bytes[byte_offset:]

        # Step 3: Full re-parse from scratch (Standard AST behavior)
        t0 = time.perf_counter()
        _ = parser.parse(modified_bytes)
        t1 = time.perf_counter()
        full_reparse_ms = (t1 - t0) * 1000

        # Step 4: Incremental re-parse using Tree-sitter edit hint
        # We create a fresh copy of the initial tree state for the benchmark
        working_tree = parser.parse(original_bytes)
        working_tree.edit(
            start_byte=byte_offset,
            old_end_byte=byte_offset,
            new_end_byte=byte_offset + len(insertion_bytes),
            start_point=(insert_line, 0),
            old_end_point=(insert_line, 0),
            new_end_point=(insert_line + insertion_bytes.count(b"\n"), 0),
        )

        t2 = time.perf_counter()
        incremental_tree = parser.parse(modified_bytes, working_tree)
        t3 = time.perf_counter()
        incremental_reparse_ms = (t3 - t2) * 1000

        speedup = full_reparse_ms / incremental_reparse_ms if incremental_reparse_ms > 0 else 1.0

        return {
            "original_bytes_len": len(original_bytes),
            "modified_bytes_len": len(modified_bytes),
            "full_reparse_ms": round(full_reparse_ms, 4),
            "incremental_reparse_ms": round(incremental_reparse_ms, 4),
            "speedup_ratio": round(speedup, 2),
            "is_valid_tree": incremental_tree.root_node is not None,
        }
