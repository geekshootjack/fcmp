from pathlib import Path

import pytest

from fcmp import cli


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_build_parser_accepts_minimum_args(tmp_path: Path) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["-a", str(tmp_path), "-b", str(tmp_path)])
    assert args.group_a == [tmp_path]
    assert args.group_b == [tmp_path]
    assert args.mode == "proxy"
    assert args.format == ["html"]


def test_build_parser_multiple_dirs_per_group(tmp_path: Path) -> None:
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d3 = tmp_path / "d3"
    for d in (d1, d2, d3):
        d.mkdir()
    parser = cli.build_parser()
    args = parser.parse_args(
        ["-a", str(d1), str(d2), "-b", str(d3), "-m", "proxy", "-f", "html", "json"]
    )
    assert args.group_a == [d1, d2]
    assert args.group_b == [d3]
    assert args.mode == "proxy"
    assert args.format == ["html", "json"]


def test_build_parser_rejects_invalid_mode(tmp_path: Path) -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-a", str(tmp_path), "-b", str(tmp_path), "-m", "bogus"])


def test_build_parser_rejects_invalid_format(tmp_path: Path) -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-a", str(tmp_path), "-b", str(tmp_path), "-f", "xml"])


def test_main_end_to_end_normal_mode(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _touch(a / "same.txt")
    _touch(a / "only_a.txt")
    _touch(b / "same.txt")
    _touch(b / "only_b.txt")
    out = tmp_path / "reports"
    out.mkdir()

    exit_code = cli.main(
        [
            "-a",
            str(a),
            "-b",
            str(b),
            "-m",
            "normal",
            "-f",
            "json",
            "-o",
            str(out),
            "--quiet",
        ]
    )
    assert exit_code == 0

    reports = list(out.glob("*.json"))
    assert len(reports) == 1
    import json

    data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert [Path(p).name for p in data["unique_in_a"]] == ["only_a.txt"]
    assert [Path(p).name for p in data["unique_in_b"]] == ["only_b.txt"]


def test_build_parser_accepts_ignore_patterns(tmp_path: Path) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        ["-a", str(tmp_path), "-b", str(tmp_path), "-i", "_gsdata_", "*.log"]
    )
    assert args.ignore == ["_gsdata_", "*.log"]


def test_main_ignore_excludes_files_and_dirs(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _touch(a / "same.mp4")
    _touch(a / "only_in_a.log")
    _touch(a / "_gsdata_" / "junk.mp4")
    _touch(b / "same.mp4")
    out = tmp_path / "reports"

    exit_code = cli.main(
        [
            "-a",
            str(a),
            "-b",
            str(b),
            "-m",
            "normal",
            "-i",
            "_gsdata_",
            "*.log",
            "-f",
            "json",
            "-o",
            str(out),
            "--quiet",
        ]
    )
    assert exit_code == 0

    import json

    data = json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
    assert data["unique_in_a"] == []
    assert data["unique_in_b"] == []
    assert data["ignored"] == ["_gsdata_", "*.log"]


def test_main_exits_nonzero_on_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    exit_code = cli.main(
        ["-a", str(missing), "-b", str(tmp_path), "-f", "txt", "--quiet"]
    )
    assert exit_code != 0


def test_main_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main([])
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "usage: fcmp" in out
    assert "--group-a" in out


def test_version_flag_prints_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    for flag in ("-v", "-V", "--version"):
        with pytest.raises(SystemExit) as exc:
            cli.main([flag])
        assert exc.value.code == 0
    assert "fcmp v" in capsys.readouterr().out


def test_help_shows_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["-h"])
    assert exc.value.code == 0
    from fcmp import __version__

    assert f"fcmp v{__version__}" in capsys.readouterr().out
