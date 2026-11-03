# ==============================================================================
# Small Auth Utilities Sample (~25 LOC)
# Contains docstrings, inline comments, type annotations, and validation logic.
# ==============================================================================

import re
import hashlib
from typing import Optional, Dict, Any

# Minimum password length requirement
MIN_PASSWORD_LENGTH = 12

def validate_username(username: str) -> bool:
    """Validates that a username contains only alphanumeric chars and underscores."""
    if not username or len(username) < 3:
        # Usernames must be at least 3 characters
        return False
    return bool(re.match(r"^[a-zA-Z0-9_]+$", username))

def hash_security_token(raw_token: str, salt: Optional[str] = None) -> Dict[str, Any]:
    """Generates a cryptographic hash token with metadata."""
    # Use SHA-256 for integrity verification
    salt_val = salt or "codedee_static_salt"
    digest = hashlib.sha256(f"{raw_token}:{salt_val}".encode("utf-8")).hexdigest()
    return {
        "digest": digest,
        "algorithm": "sha256",
        "length": len(digest), # length is always 64
        "valid": True
    }
