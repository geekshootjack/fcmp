from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from fcmp.filters import (
    IgnoreList,
    is_video,
    should_skip_dir,
    should_skip_file,
    should_skip_path,
)


class KeyMode(str, Enum):
    NAME = "name"
    STEM = "stem"


FrameCountFn = Callable[[Path], int | None]
OnFileFn = Callable[[Path], None]


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: Path
    filename: str
    frame_count: int | None = None


def _key_for(path: Path, mode: KeyMode) -> str:
    return path.stem if mode is KeyMode.STEM else path.name


def scan(
    directory: Path,
    *,
    video_only: bool = False,
    with_frames: bool = False,
    key: KeyMode = KeyMode.NAME,
    frame_count: FrameCountFn | None = None,
    on_file: OnFileFn | None = None,
    ignore: IgnoreList | None = None,
) -> dict[str, FileEntry]:
    """Walk ``directory`` and return a dict of file entries keyed by name or stem."""
    if with_frames and frame_count is None:
        raise ValueError("with_frames=True requires a frame_count callable")

    result: dict[str, FileEntry] = {}
    directory = Path(directory)

    for root, dirs, files in os.walk(directory):
        # Sort so traversal (and thus first-wins on duplicate keys) is
        # deterministic across filesystems.
        dirs[:] = sorted(
            d
            for d in dirs
            if not should_skip_dir(d) and not (ignore and ignore.matches_dir(d))
        )
        root_path = Path(root)
        if should_skip_path(root_path):
            continue

        for name in sorted(files):
            if should_skip_file(name):
                continue
            if ignore and ignore.matches_file(name):
                continue
            path = root_path / name
            if video_only and not is_video(path):
                continue

            k = _key_for(path, key)
            if k in result:
                continue

            frames = frame_count(path) if with_frames and frame_count else None
            result[k] = FileEntry(path=path, filename=name, frame_count=frames)
            if on_file is not None:
                on_file(path)

    return result


def scan_groups(
    paths: Iterable[Path],
    *,
    video_only: bool = False,
    with_frames: bool = False,
    key: KeyMode = KeyMode.NAME,
    frame_count: FrameCountFn | None = None,
    on_file: OnFileFn | None = None,
    ignore: IgnoreList | None = None,
) -> dict[str, FileEntry]:
    """Scan multiple directories and merge results with first-wins semantics."""
    merged: dict[str, FileEntry] = {}
    for p in paths:
        partial = scan(
            Path(p),
            video_only=video_only,
            with_frames=with_frames,
            key=key,
            frame_count=frame_count,
            on_file=on_file,
            ignore=ignore,
        )
        for k, v in partial.items():
            merged.setdefault(k, v)
    return merged
