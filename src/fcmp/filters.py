from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

SKIP_FILE_PREFIXES: tuple[str, ...] = (
    "._",
    ".DS_Store",
    ".AppleDouble",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    "Thumbs.db",
    "desktop.ini",
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "$RECYCLE.BIN",
        "System Volume Information",
        ".Trash",
        "@eaDir",
        "#recycle",
    }
)

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4", ".mov", ".mxf",
        ".avi", ".wmv", ".mkv",
        ".m4v", ".mpg", ".mpeg",
        ".webm", ".flv", ".vob",
        ".ogv", ".ogg", ".dv",
        ".qt", ".f4v", ".m2ts",
        ".mts", ".ts", ".3gp",
        ".3g2",
    }
)


@dataclass(frozen=True, slots=True)
class IgnoreList:
    """User-supplied ignore patterns matched against single path components.

    Patterns use glob syntax (``fnmatch``) and match case-insensitively.
    A pattern ending in ``/`` (or ``\\``) only matches directory names;
    all other patterns match both file and directory names.
    """

    patterns: tuple[str, ...] = ()
    dir_only_patterns: tuple[str, ...] = ()

    @classmethod
    def from_patterns(cls, patterns: list[str] | None) -> IgnoreList:
        general: list[str] = []
        dir_only: list[str] = []
        for raw in patterns or []:
            p = raw.strip()
            if not p:
                continue
            if p.endswith(("/", "\\")):
                dir_only.append(p.rstrip("/\\").lower())
            else:
                general.append(p.lower())
        return cls(patterns=tuple(general), dir_only_patterns=tuple(dir_only))

    def __bool__(self) -> bool:
        return bool(self.patterns or self.dir_only_patterns)

    def matches_file(self, name: str) -> bool:
        lowered = name.lower()
        return any(fnmatch.fnmatchcase(lowered, p) for p in self.patterns)

    def matches_dir(self, name: str) -> bool:
        lowered = name.lower()
        return any(
            fnmatch.fnmatchcase(lowered, p)
            for p in (*self.patterns, *self.dir_only_patterns)
        )


def should_skip_file(name: str) -> bool:
    return any(name.startswith(p) for p in SKIP_FILE_PREFIXES)


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS
