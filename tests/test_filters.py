from pathlib import Path

import pytest

from fcmp.filters import (
    VIDEO_EXTENSIONS,
    IgnoreList,
    is_video,
    should_skip_dir,
    should_skip_file,
    should_skip_path,
)


@pytest.mark.parametrize(
    "name",
    [
        ".DS_Store",
        "._resource_fork",
        ".AppleDouble",
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        "Thumbs.db",
        "desktop.ini",
    ],
)
def test_should_skip_file_system_artifacts(name: str) -> None:
    assert should_skip_file(name) is True


@pytest.mark.parametrize("name", ["video.mp4", "clip_v01.mov", "notes.txt", "README"])
def test_should_skip_file_passes_normal_files(name: str) -> None:
    assert should_skip_file(name) is False


@pytest.mark.parametrize(
    "name",
    ["$RECYCLE.BIN", "System Volume Information", ".Trash", "@eaDir", "#recycle"],
)
def test_should_skip_dir_system_artifacts(name: str) -> None:
    assert should_skip_dir(name) is True


@pytest.mark.parametrize("name", ["footage", "proxies", "2024-Q1"])
def test_should_skip_dir_passes_user_dirs(name: str) -> None:
    assert should_skip_dir(name) is False


def test_should_skip_path_detects_any_skipped_component(tmp_path: Path) -> None:
    p = tmp_path / ".Trash" / "inner" / "file"
    assert should_skip_path(p) is True


def test_should_skip_path_allows_clean_path(tmp_path: Path) -> None:
    p = tmp_path / "projects" / "alpha"
    assert should_skip_path(p) is False


def test_video_extensions_are_lowercase_and_start_with_dot() -> None:
    for ext in VIDEO_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


@pytest.mark.parametrize(
    "name", ["clip.mp4", "CLIP.MOV", "shot.MxF", "a.b.mkv", "00001.MTS", "clip.m2ts"]
)
def test_is_video_matches_known_extensions_case_insensitively(name: str) -> None:
    assert is_video(Path(name)) is True


@pytest.mark.parametrize("name", ["notes.txt", "photo.jpg", "archive.zip", "no_ext"])
def test_is_video_rejects_non_video(name: str) -> None:
    assert is_video(Path(name)) is False


def test_ignore_list_empty_is_falsy() -> None:
    ignore = IgnoreList.from_patterns(None)
    assert not ignore
    assert ignore.matches_file("anything.log") is False
    assert ignore.matches_dir("_gsdata_") is False


def test_ignore_list_exact_name_matches_files_and_dirs() -> None:
    ignore = IgnoreList.from_patterns(["_gsdata_"])
    assert ignore.matches_dir("_gsdata_") is True
    assert ignore.matches_file("_gsdata_") is True
    assert ignore.matches_dir("footage") is False


def test_ignore_list_glob_patterns() -> None:
    ignore = IgnoreList.from_patterns(["*.log", "*.mhl"])
    assert ignore.matches_file("2026-0402-144440-GSJ-DATA-4-2.log") is True
    assert ignore.matches_file("shoot_2023-12-03.mhl") is True
    assert ignore.matches_file("clip.mp4") is False


def test_ignore_list_is_case_insensitive() -> None:
    ignore = IgnoreList.from_patterns(["*.LOG", "ASCMHL"])
    assert ignore.matches_file("session.log") is True
    assert ignore.matches_dir("ascmhl") is True


def test_ignore_list_trailing_slash_restricts_to_dirs() -> None:
    ignore = IgnoreList.from_patterns(["ascmhl/"])
    assert ignore.matches_dir("ascmhl") is True
    assert ignore.matches_file("ascmhl") is False


def test_ignore_list_skips_blank_patterns() -> None:
    ignore = IgnoreList.from_patterns(["", "  ", "*.log"])
    assert ignore.patterns == ("*.log",)
