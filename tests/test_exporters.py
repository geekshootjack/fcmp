import csv
import json
from pathlib import Path

import pytest

from fcmp.compare import ComparisonResult, FrameMismatch
from fcmp.exporters import EXPORTERS, Report, export


@pytest.fixture
def simple_report() -> Report:
    return Report(
        mode="normal",
        dirs_a=[Path("/src/a")],
        dirs_b=[Path("/src/b")],
        result=ComparisonResult(
            unique_a=[Path("/src/a/only_a.mp4")],
            unique_b=[Path("/src/b/only_b.mov"), Path("/src/b/another.mkv")],
            frame_mismatches=[],
        ),
    )


@pytest.fixture
def proxy_frames_report() -> Report:
    return Report(
        mode="proxy-frames",
        dirs_a=[Path("/originals")],
        dirs_b=[Path("/proxies")],
        result=ComparisonResult(
            unique_a=[],
            unique_b=[],
            frame_mismatches=[
                FrameMismatch(
                    basename="clip_01",
                    file_a="clip_01.mxf",
                    file_b="clip_01.mp4",
                    frames_a=1000,
                    frames_b=900,
                    difference=100,
                    path_a=Path("/originals/clip_01.mxf"),
                    path_b=Path("/proxies/clip_01.mp4"),
                ),
                FrameMismatch(
                    basename="clip_02",
                    file_a="clip_02.mxf",
                    file_b="clip_02.mp4",
                    frames_a=None,
                    frames_b=500,
                    difference="Group A frame count missing",
                    path_a=Path("/originals/clip_02.mxf"),
                    path_b=Path("/proxies/clip_02.mp4"),
                ),
            ],
        ),
    )


def test_exporters_registry_has_expected_formats() -> None:
    assert set(EXPORTERS) == {"json", "txt", "csv", "html"}


def test_export_json_shape(simple_report: Report, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    export(simple_report, out, "json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["format_version"] == 1
    assert data["mode"] == "normal"
    assert data["group_a"]["directories"] == [str(Path("/src/a"))]
    assert data["group_b"]["directories"] == [str(Path("/src/b"))]
    assert data["unique_in_a"] == [str(Path("/src/a/only_a.mp4"))]
    assert sorted(data["unique_in_b"]) == sorted(
        [str(Path("/src/b/another.mkv")), str(Path("/src/b/only_b.mov"))]
    )
    assert "frame_mismatches" not in data or data["frame_mismatches"] == []


def test_export_json_includes_frame_mismatches(
    proxy_frames_report: Report, tmp_path: Path
) -> None:
    out = tmp_path / "out.json"
    export(proxy_frames_report, out, "json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["frame_mismatches"]) == 2
    first = data["frame_mismatches"][0]
    assert first["basename"] == "clip_01"
    assert first["frames_a"] == 1000
    assert first["difference"] == 100


def test_export_json_handles_unicode(tmp_path: Path) -> None:
    report = Report(
        mode="normal",
        dirs_a=[Path("/原始")],
        dirs_b=[Path("/代理")],
        result=ComparisonResult(
            unique_a=[Path("/原始/视频.mp4")], unique_b=[], frame_mismatches=[]
        ),
    )
    out = tmp_path / "out.json"
    export(report, out, "json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["unique_in_a"] == [str(Path("/原始/视频.mp4"))]


def test_export_txt_contains_key_sections(
    simple_report: Report, tmp_path: Path
) -> None:
    out = tmp_path / "out.txt"
    export(simple_report, out, "txt")
    text = out.read_text(encoding="utf-8")
    assert "normal" in text.lower() or "Mode" in text
    assert str(Path("/src/a/only_a.mp4")) in text
    assert str(Path("/src/b/only_b.mov")) in text


def test_export_txt_includes_frame_mismatches(
    proxy_frames_report: Report, tmp_path: Path
) -> None:
    out = tmp_path / "out.txt"
    export(proxy_frames_report, out, "txt")
    text = out.read_text(encoding="utf-8")
    assert "clip_01" in text
    assert "100" in text
    assert "Group A frame count missing" in text


def test_export_csv_is_valid(simple_report: Report, tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    export(simple_report, out, "csv")
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    flat = [cell for row in rows for cell in row]
    assert str(Path("/src/a/only_a.mp4")) in flat
    assert str(Path("/src/b/only_b.mov")) in flat


def test_export_html_contains_paths_and_escapes(
    simple_report: Report, tmp_path: Path
) -> None:
    out = tmp_path / "out.html"
    export(simple_report, out, "html")
    body = out.read_bytes()
    assert body.startswith(b"\xef\xbb\xbf"), "HTML should have UTF-8 BOM"
    text = body.decode("utf-8-sig")
    assert "<html" in text
    assert str(Path("/src/a/only_a.mp4")) in text


def test_export_html_escapes_special_chars(tmp_path: Path) -> None:
    report = Report(
        mode="normal",
        dirs_a=[Path("/a")],
        dirs_b=[Path("/b")],
        result=ComparisonResult(
            unique_a=[Path("/a/<script>.mp4")], unique_b=[], frame_mismatches=[]
        ),
    )
    out = tmp_path / "out.html"
    export(report, out, "html")
    text = out.read_bytes().decode("utf-8-sig")
    assert "<script>.mp4" not in text
    assert "&lt;script&gt;.mp4" in text


def test_export_html_has_collapsible_sections_and_toolbar(
    simple_report: Report, tmp_path: Path
) -> None:
    out = tmp_path / "out.html"
    export(simple_report, out, "html")
    text = out.read_bytes().decode("utf-8-sig")
    assert text.count("<details") == 2  # Group A + Group B sections
    assert "<summary>" in text
    assert 'id="filter"' in text
    assert "Expand all" in text
    assert "Collapse all" in text


def test_export_html_shows_ignored_patterns(tmp_path: Path) -> None:
    report = Report(
        mode="normal",
        dirs_a=[Path("/a")],
        dirs_b=[Path("/b")],
        result=ComparisonResult(unique_a=[], unique_b=[], frame_mismatches=[]),
        ignored=["_gsdata_", "*.log"],
    )
    out = tmp_path / "out.html"
    export(report, out, "html")
    text = out.read_bytes().decode("utf-8-sig")
    assert "Ignored:" in text
    assert "_gsdata_, *.log" in text


def test_export_json_includes_ignored(tmp_path: Path) -> None:
    report = Report(
        mode="normal",
        dirs_a=[Path("/a")],
        dirs_b=[Path("/b")],
        result=ComparisonResult(unique_a=[], unique_b=[], frame_mismatches=[]),
        ignored=["*.mhl"],
    )
    out = tmp_path / "out.json"
    export(report, out, "json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ignored"] == ["*.mhl"]


def test_export_unknown_format_raises(simple_report: Report, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export(simple_report, tmp_path / "out.xml", "xml")
