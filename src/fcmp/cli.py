from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from fcmp import __version__, mediainfo
from fcmp.compare import compare
from fcmp.exporters import EXPORTERS, Report, export
from fcmp.filters import IgnoreList
from fcmp.scanner import KeyMode, scan_groups

MODE_CHOICES: tuple[str, ...] = ("normal", "proxy", "proxy-frames")
FORMAT_CHOICES: tuple[str, ...] = tuple(sorted(EXPORTERS))
DEFAULT_FORMAT = "html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcmp",
        description=(
            f"fcmp v{__version__}\n\n"
            "Compare two directory trees (or groups of them) for parity. "
            "Supports video proxy workflows, including frame-count verification."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  fcmp -a /src -b /backup\n"
            "  fcmp -a /originals -b /proxies -m proxy\n"
            "  fcmp -a /originals -b /proxies -m proxy-frames -f html json\n"
            "  fcmp -a /part1 /part2 -b /mirror -o reports/\n"
            "  fcmp -a /src -b /backup -i _gsdata_ '*.log' '*.mhl' ascmhl/\n"
        ),
    )
    parser.add_argument(
        "-v", "-V", "--version",
        action="version", version=f"fcmp v{__version__}",
    )
    parser.add_argument(
        "-a",
        "--group-a",
        required=True,
        nargs="+",
        type=Path,
        metavar="DIR",
        help="One or more directories forming group A.",
    )
    parser.add_argument(
        "-b",
        "--group-b",
        required=True,
        nargs="+",
        type=Path,
        metavar="DIR",
        help="One or more directories forming group B.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=MODE_CHOICES,
        default="normal",
        help="Comparison mode (default: %(default)s).",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMAT_CHOICES,
        nargs="+",
        default=[DEFAULT_FORMAT],
        help="Output format(s) (default: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="Directory for report files (default: current directory).",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        nargs="+",
        default=[],
        metavar="PATTERN",
        help=(
            "File/directory name patterns to ignore during comparison "
            "(glob syntax, case-insensitive; a trailing '/' restricts a "
            "pattern to directories). Example: -i _gsdata_ '*.log' '*.mhl' ascmhl/"
        ),
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress and status output."
    )
    return parser


def _scan_opts(mode: str) -> dict:
    if mode == "proxy":
        return {"video_only": True, "key": KeyMode.STEM}
    if mode == "proxy-frames":
        return {
            "video_only": True,
            "with_frames": True,
            "key": KeyMode.STEM,
            "frame_count": mediainfo.frame_count,
        }
    return {}


def _validate_paths(paths: Sequence[Path], console: Console) -> list[str]:
    errors: list[str] = []
    for p in paths:
        if not p.exists():
            errors.append(f"Path does not exist: {p}")
        elif not p.is_dir():
            errors.append(f"Not a directory: {p}")
    for err in errors:
        console.print(f"[red]error:[/red] {err}")
    return errors


def _render_summary(
    console: Console,
    report: Report,
    written: list[Path],
) -> None:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Mode", report.mode)
    summary.add_row("Group A dirs", ", ".join(str(p) for p in report.dirs_a))
    summary.add_row("Group B dirs", ", ".join(str(p) for p in report.dirs_b))
    if report.ignored:
        summary.add_row("Ignored", ", ".join(report.ignored))
    summary.add_row("Unique in A", str(len(report.result.unique_a)))
    summary.add_row("Unique in B", str(len(report.result.unique_b)))
    if report.mode == "proxy-frames":
        summary.add_row(
            "Frame mismatches", str(len(report.result.frame_mismatches))
        )
    summary.add_row("Reports", "\n".join(str(p) for p in written))
    console.print(Panel(summary, title="fcmp", border_style="cyan"))


def _scan_with_progress(
    console: Console,
    label: str,
    paths: Sequence[Path],
    *,
    mode: str,
    quiet: bool,
    ignore: IgnoreList | None = None,
) -> dict:
    opts = _scan_opts(mode)
    if ignore:
        opts["ignore"] = ignore

    if quiet:
        return scan_groups(paths, **opts)

    columns = [
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ]
    with Progress(*columns, console=console, transient=True) as progress:
        task_id = progress.add_task(label, total=None)

        def _tick(_: Path) -> None:
            progress.update(task_id, advance=1)

        return scan_groups(paths, on_file=_tick, **opts)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 2
    args = parser.parse_args(argv)

    console = Console(quiet=args.quiet, stderr=True)

    errors = _validate_paths([*args.group_a, *args.group_b], console)
    if errors:
        return 2

    if args.mode == "proxy-frames" and not mediainfo.is_available():
        console.print(
            "[red]error:[/red] proxy-frames mode requires the 'mediainfo' CLI.\n"
            "  macOS:   brew install mediainfo\n"
            "  Linux:   sudo apt-get install mediainfo\n"
            "  Windows: https://mediaarea.net/en/MediaInfo/Download"
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)

    ignore = IgnoreList.from_patterns(args.ignore)

    files_a = _scan_with_progress(
        console,
        "Scanning group A",
        args.group_a,
        mode=args.mode,
        quiet=args.quiet,
        ignore=ignore,
    )
    files_b = _scan_with_progress(
        console,
        "Scanning group B",
        args.group_b,
        mode=args.mode,
        quiet=args.quiet,
        ignore=ignore,
    )

    result = compare(files_a, files_b, check_frames=args.mode == "proxy-frames")
    report = Report(
        mode=args.mode,
        dirs_a=list(args.group_a),
        dirs_b=list(args.group_b),
        result=result,
        ignored=list(args.ignore),
    )

    stamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
    written: list[Path] = []
    for fmt in args.format:
        out_path = args.output_dir / f"fcmp_{stamp}.{fmt}"
        export(report, out_path, fmt)
        written.append(out_path.resolve())

    if not args.quiet:
        _render_summary(console, report, written)

    return 0
