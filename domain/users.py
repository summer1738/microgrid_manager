"""
User registration and authentication for the microgrid manager.
Users have: id, name, email, password_hash, system_type (package), role (user type).
"""
import json
import os
import uuid
from dataclasses import dataclass
from typing import List, Optional

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    def generate_password_hash(p): return p
    def check_password_hash(h, p): return h == p


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "..", "data", "users.json")

VALID_SYSTEM_TYPES = ("household", "community", "institutional")
VALID_ROLES = ("operator", "consumer", "maintenance", "utility")


@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    system_type: str
    role: str


def _ensure_data_dir():
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)


def _load_raw() -> List[dict]:
    _ensure_data_dir()
    if not os.path.exists(USERS_PATH):
        return []
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(users: List[dict]) -> None:
    _ensure_data_dir()
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def get_user_by_id(user_id: str) -> Optional[User]:
    for raw in _load_raw():
        if raw.get("id") == user_id:
            return User(**raw)
    return None


def get_user_by_email(email: str) -> Optional[User]:
    email_lower = email.strip().lower()
    for raw in _load_raw():
        if raw.get("email", "").strip().lower() == email_lower:
            return User(**raw)
    return None


def register(
    name: str,
    email: str,
    password: str,
    system_type: str,
    role: str,
) -> Optional[str]:
    if system_type not in VALID_SYSTEM_TYPES or role not in VALID_ROLES:
        return None
    if get_user_by_email(email):
        return None
    users = _load_raw()
    user_id = str(uuid.uuid4())
    users.append({
        "id": user_id,
        "name": name.strip(),
        "email": email.strip().lower(),
        "password_hash": generate_password_hash(password),
        "system_type": system_type,
        "role": role,
    })
    _save_raw(users)
    return user_id


def authenticate(email: str, password: str) -> Optional[User]:
    user = get_user_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "system_type": user.system_type,
        "role": user.role,
    }
