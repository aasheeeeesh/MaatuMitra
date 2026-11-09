"""Synthetic user directory used by the sandbox mock issuer (seed/synthetic_users.json)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

DIRECTORY_FILE = Path(__file__).resolve().parents[1] / "seed" / "synthetic_users.json"
APP_ROLES = ("asha", "nurse", "physician", "pharmacist", "researcher")


@dataclass(frozen=True)
class DirectoryUser:
    key: str
    id: uuid.UUID
    role: str
    facility_key: str
    facility_id: uuid.UUID
    display_name: str


class Directory:
    def __init__(self, facilities: dict[str, dict], users: list[DirectoryUser]):
        self.facilities = facilities
        self.users = users
        self._by_id = {u.id: u for u in users}
        self._by_key = {u.key: u for u in users}

    def get(self, user_id: uuid.UUID) -> DirectoryUser | None:
        return self._by_id.get(user_id)

    def by_key(self, key: str) -> DirectoryUser:
        return self._by_key[key]

    def facility_id(self, key: str) -> uuid.UUID:
        return uuid.UUID(self.facilities[key]["id"])


def load_directory(path: Path = DIRECTORY_FILE) -> Directory:
    doc = json.loads(path.read_text(encoding="utf-8"))
    facs = doc["facilities"]
    users = []
    for u in doc["users"]:
        if u["role"] not in APP_ROLES:
            raise ValueError(f"unknown role in directory: {u['role']!r}")
        users.append(
            DirectoryUser(
                key=u["key"],
                id=uuid.UUID(u["id"]),
                role=u["role"],
                facility_key=u["facility"],
                facility_id=uuid.UUID(facs[u["facility"]]["id"]),
                display_name=u["display_name"],
            )
        )
    return Directory(facs, users)
