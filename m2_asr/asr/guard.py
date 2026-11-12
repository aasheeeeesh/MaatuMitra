"""Dev-only guard (PROJECT_BRIEF 6.5): m2 may never transcribe test-split audio.

Refuses a path when: any folder is named 'test'; the file stem names a test conversation
(data/splits/test.txt); the path is listed in data/splits/test.lock; the path contains a
held-out voice (D-132). Runs before any model sees the file.
"""

from __future__ import annotations

from pathlib import Path

HELD_OUT_VOICES = ("mms_kan_pitch084",)


class TestSplitRefused(RuntimeError):
    """Raised when a path belongs to the test split."""

    __test__ = False  # not a pytest class


class DevGuard:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        sp = self.root / "data" / "splits"
        self.test_ids = set((sp / "test.txt").read_text(encoding="utf-8").split())
        self.locked: set[str] = set()
        lock = sp / "test.lock"
        if lock.exists():
            for ln in lock.read_text(encoding="utf-8").splitlines():
                if ln and not ln.startswith("#") and "  " in ln:
                    self.locked.add(ln.split("  ", 1)[1].strip())

    def check(self, path: str | Path) -> None:
        p = Path(path)
        posix = p.as_posix()
        try:
            posix = p.resolve().relative_to(self.root.resolve()).as_posix()
            parts = set(posix.split("/"))
        except (ValueError, OSError):
            parts = set(p.parts)
        why = None
        if "test" in parts:
            why = "a folder is named 'test'"
        elif posix in self.locked:
            why = "listed in data/splits/test.lock"
        elif any(v in posix for v in HELD_OUT_VOICES):
            why = "held-out test voice"
        else:
            stem = p.stem
            for piece in stem.split("__"):
                if piece in self.test_ids:
                    why = f"conversation {piece} is in data/splits/test.txt"
                    break
        if why:
            raise TestSplitRefused(f"REFUSED test-split audio ({why}): {path}")
