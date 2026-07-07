from pathlib import Path

import pytest

from fcmp.filters import IgnoreList
from fcmp.scanner import FileEntry, KeyMode, scan, scan_groups


def _touch(path: Path, content: bytes = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    _touch(tmp_path / "a.mp4")
    _touch(tmp_path / "b.mov")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / ".DS_Store")
    _touch(tmp_path / "sub" / "c.mp4")
    _touch(tmp_path / "sub" / "._c.mp4")
    _touch(tmp_path / ".Trash" / "trashed.mp4")
    _touch(tmp_path / "nested" / "deep" / "d.mxf")
    return tmp_path


def test_scan_returns_file_entries_keyed_by_name(tree: Path) -> None:
    result = scan(tree)
    assert set(result.keys()) == {"a.mp4", "b.mov", "notes.txt", "c.mp4", "d.mxf"}
    for entry in result.values():
        assert isinstance(entry, FileEntry)
        assert entry.path.is_absolute() or entry.path.exists()
        assert entry.frame_count is None


def test_scan_skips_system_files_and_dirs(tree: Path) -> None:
    result = scan(tree)
    assert ".DS_Store" not in result
    assert "._c.mp4" not in result
    assert "trashed.mp4" not in result


def test_scan_video_only(tree: Path) -> None:
    result = scan(tree, video_only=True)
    assert "notes.txt" not in result
    assert "a.mp4" in result


def test_scan_stem_key_mode(tree: Path) -> None:
    result = scan(tree, video_only=True, key=KeyMode.STEM)
    assert set(result.keys()) == {"a", "b", "c", "d"}


def test_scan_first_wins_on_duplicate_key(tmp_path: Path) -> None:
    first = _touch(tmp_path / "one" / "clip.mp4")
    _touch(tmp_path / "two" / "clip.mov")
    result = scan(tmp_path, video_only=True, key=KeyMode.STEM)
    assert result["clip"].path == first


def test_scan_groups_merges_multiple_directories(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _touch(a / "x.mp4")
    _touch(b / "y.mp4")
    _touch(b / "x.mp4")
    result = scan_groups([a, b])
    assert set(result.keys()) == {"x.mp4", "y.mp4"}
    assert result["x.mp4"].path == a / "x.mp4"


def test_scan_groups_empty_input_returns_empty_dict() -> None:
    assert scan_groups([]) == {}


def test_scan_with_frames_invokes_frame_count_hook(tmp_path: Path) -> None:
    _touch(tmp_path / "a.mp4")
    _touch(tmp_path / "b.mp4")
    calls: list[Path] = []

    def fake_frame_count(path: Path) -> int:
        calls.append(path)
        return 1000

    result = scan(
        tmp_path,
        video_only=True,
        with_frames=True,
        frame_count=fake_frame_count,
    )
    assert {e.frame_count for e in result.values()} == {1000}
    assert len(calls) == 2


def test_scan_on_file_callback_called_per_kept_file(tree: Path) -> None:
    seen: list[Path] = []
    scan(tree, on_file=seen.append)
    assert len(seen) == 5


def test_scan_ignore_skips_matching_files(tmp_path: Path) -> None:
    _touch(tmp_path / "clip.mp4")
    _touch(tmp_path / "transfer.log")
    _touch(tmp_path / "shoot.mhl")
    ignore = IgnoreList.from_patterns(["*.log", "*.mhl"])
    result = scan(tmp_path, ignore=ignore)
    assert set(result.keys()) == {"clip.mp4"}


def test_scan_ignore_prunes_matching_dirs(tmp_path: Path) -> None:
    _touch(tmp_path / "clip.mp4")
    _touch(tmp_path / "_gsdata_" / "hidden.mp4")
    _touch(tmp_path / "ascmhl" / "hash.mhl")
    ignore = IgnoreList.from_patterns(["_gsdata_", "ascmhl/"])
    result = scan(tmp_path, ignore=ignore)
    assert set(result.keys()) == {"clip.mp4"}


def test_scan_groups_passes_ignore_through(tmp_path: Path) -> None:
    a = tmp_path / "a"
    _touch(a / "x.mp4")
    _touch(a / "x.log")
    result = scan_groups([a], ignore=IgnoreList.from_patterns(["*.log"]))
    assert set(result.keys()) == {"x.mp4"}
