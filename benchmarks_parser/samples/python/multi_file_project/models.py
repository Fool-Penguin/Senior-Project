# Data Models module
from dataclasses import dataclass

@dataclass
class UserRecord:
    # Primary user entity
    user_id: int
    username: str
    email: str
    is_active: bool = True
