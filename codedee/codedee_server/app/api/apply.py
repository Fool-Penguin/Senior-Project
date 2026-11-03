"""
apply.py - POST /api/apply-patch endpoint.

Applies verified patch diffs or remediated code directly to the target file on disk,
creating an automatic safety backup (.bak) and running a post-application Tree-sitter
syntax verification check before finalizing changes.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
import tree_sitter

from ..models.contracts import ApplyPatchRequest, ApplyPatchResponse
from .scan import detect_language, get_parser_for_language

router = APIRouter(tags=["Apply"])


HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


def apply_unified_diff(original_text: str, patch_diff: str) -> str:
    """
    Applies a standard unified diff to original text.
    Handles hunk headers (@@ -start,count +start,count @@), context lines,
    deletions (-), and additions (+).
    Raises ValueError on malformed diffs, context mismatches, or invalid hunks.
    """
    if not patch_diff or not patch_diff.strip():
        raise ValueError("Patch diff is empty or whitespace-only.")

    orig_lines = original_text.splitlines()
    patch_lines = patch_diff.splitlines()

    result_lines: List[str] = []
    orig_idx = 0
    hunks_count = 0
    i = 0

    while i < len(patch_lines):
        line = patch_lines[i]

        if line.startswith("@@"):
            match = HUNK_HEADER_RE.match(line)
            if not match:
                raise ValueError(f"Malformed hunk header: {line}")

            hunks_count += 1
            orig_start = int(match.group(1))
            orig_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1

            if orig_count == 0:
                target_orig_idx = orig_start
            else:
                target_orig_idx = max(0, orig_start - 1)

            if target_orig_idx < orig_idx:
                raise ValueError(
                    f"Hunk {hunks_count} start line {orig_start} is before current line {orig_idx + 1}."
                )

            while orig_idx < target_orig_idx:
                if orig_idx < len(orig_lines):
                    result_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                else:
                    raise ValueError(
                        f"Hunk start line {orig_start} exceeds original file length {len(orig_lines)}."
                    )

            i += 1
            while i < len(patch_lines):
                hunk_line = patch_lines[i]
                if hunk_line.startswith("@@"):
                    # Next hunk starts
                    break

                if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    result_lines.append(hunk_line[1:])
                elif hunk_line.startswith("-") and not hunk_line.startswith("---"):
                    if orig_idx >= len(orig_lines):
                        raise ValueError(
                            f"Deletion line exceeds original file length at hunk {hunks_count}."
                        )
                    expected = hunk_line[1:]
                    actual = orig_lines[orig_idx]
                    if actual != expected and actual.rstrip() != expected.rstrip():
                        raise ValueError(
                            f"Deletion mismatch at line {orig_idx + 1}: expected '{expected}', found '{actual}'."
                        )
                    orig_idx += 1
                elif hunk_line.startswith(" "):
                    if orig_idx >= len(orig_lines):
                        raise ValueError(
                            f"Context line exceeds original file length at hunk {hunks_count}."
                        )
                    expected = hunk_line[1:]
                    actual = orig_lines[orig_idx]
                    if actual != expected and actual.rstrip() != expected.rstrip():
                        raise ValueError(
                            f"Context mismatch at line {orig_idx + 1}: expected '{expected}', found '{actual}'."
                        )
                    result_lines.append(actual)
                    orig_idx += 1
                elif hunk_line == "" and orig_idx < len(orig_lines) and orig_lines[orig_idx] == "":
                    result_lines.append("")
                    orig_idx += 1
                elif hunk_line.startswith("\\"):
                    pass
                elif hunk_line.startswith("---") or hunk_line.startswith("+++"):
                    pass
                else:
                    raise ValueError(f"Unexpected line in hunk {hunks_count}: {repr(hunk_line)}")
                i += 1
            continue

        if line.startswith("---") or line.startswith("+++") or line.startswith("diff ") or line.startswith("index "):
            i += 1
            continue

        if hunks_count == 0:
            i += 1
            continue

        raise ValueError(f"Unexpected line outside hunk: {repr(line)}")

    if hunks_count == 0:
        raise ValueError("No valid @@ hunk headers found in patch diff.")

    while orig_idx < len(orig_lines):
        result_lines.append(orig_lines[orig_idx])
        orig_idx += 1

    if not result_lines and not orig_lines:
        return ""

    newline = "\r\n" if "\r\n" in original_text else "\n"
    res = newline.join(result_lines)
    if original_text.endswith(("\r\n", "\n")):
        res += newline
    return res


@router.post("/api/apply-patch", response_model=ApplyPatchResponse)
def apply_patch(req: ApplyPatchRequest) -> ApplyPatchResponse:
    """
    Apply a verified patch to the target source file on disk.
    Creates safety backup (.bak) and verifies syntax with Tree-sitter.
    """
    target_path = Path(req.target_file)
    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target file does not exist: {req.target_file}",
        )

    # Read original file
    try:
        original_content = target_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read target file {req.target_file}: {str(e)}",
        )

    # Create safety backup file
    backup_path = target_path.with_name(f"{target_path.name}.bak")
    try:
        shutil.copy2(target_path, backup_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup at {backup_path}: {str(e)}",
        )

    # Determine updated content
    new_content: Optional[str] = None

    if req.remediated_code:
        # Direct code substitution
        new_content = req.remediated_code
    elif req.patch_diff:
        # Unified diff application
        try:
            new_content = apply_unified_diff(original_content, req.patch_diff)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Failed to apply patch diff: {str(e)}",
            )
        if new_content == original_content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Patch diff produced no changes to the target file.",
            )

    if new_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either remediated_code or patch_diff must be supplied to apply patch.",
        )

    # Post-application Tree-sitter CST syntax verification
    lang = detect_language(str(target_path), new_content)
    parser = get_parser_for_language(lang)
    tree = parser.parse(new_content.encode("utf-8"))

    if tree.root_node.has_error:
        # Revert to backup immediately
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Patch resulted in invalid CST syntax. Changes reverted from backup.",
        )

    # Write patched file
    try:
        target_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        # Revert on write failure
        shutil.copy2(backup_path, target_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write updated file: {str(e)}",
        )

    return ApplyPatchResponse(
        success=True,
        target_file=str(target_path),
        backup_file=str(backup_path),
        message=f"Patch {req.patch_id or ''} applied successfully and syntax-verified via Tree-sitter.".strip(),
        updated_content=new_content,
    )
