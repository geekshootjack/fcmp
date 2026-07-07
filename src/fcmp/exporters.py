from __future__ import annotations

import csv
import html
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from fcmp.compare import ComparisonResult, FrameMismatch

Exporter = Callable[["Report", Path], None]


@dataclass(frozen=True, slots=True)
class Report:
    mode: str
    dirs_a: list[Path]
    dirs_b: list[Path]
    result: ComparisonResult
    generated_at: datetime = field(default_factory=datetime.now)
    ignored: list[str] = field(default_factory=list)


_MODE_LABELS = {
    "normal": "Normal (compare all files by filename)",
    "proxy": "Proxy (compare video files by basename)",
    "proxy-frames": "Proxy + frames (basename match plus frame-count verification)",
}


def _diff_sort_key(m: FrameMismatch) -> tuple[int, int | str]:
    """Sort numeric differences first (desc), then textual reasons."""
    if isinstance(m.difference, (int, float)):
        return (0, -int(m.difference))
    return (1, str(m.difference))


def _mismatch_to_dict(m: FrameMismatch) -> dict:
    d = asdict(m)
    d["path_a"] = str(m.path_a)
    d["path_b"] = str(m.path_b)
    return d


def export_json(report: Report, path: Path) -> None:
    payload = {
        "mode": report.mode,
        "generated_at": report.generated_at.isoformat(),
        "ignored": list(report.ignored),
        "group_a": {"directories": [str(p) for p in report.dirs_a]},
        "group_b": {"directories": [str(p) for p in report.dirs_b]},
        "unique_in_a": [str(p) for p in report.result.unique_a],
        "unique_in_b": [str(p) for p in report.result.unique_b],
    }
    if report.mode == "proxy-frames":
        payload["frame_mismatches"] = [
            _mismatch_to_dict(m) for m in report.result.frame_mismatches
        ]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def export_txt(report: Report, path: Path) -> None:
    lines: list[str] = []
    lines.append("File Comparison Report")
    lines.append(f"Mode: {report.mode}")
    lines.append(f"Generated: {report.generated_at.isoformat(timespec='seconds')}")
    if report.ignored:
        lines.append(f"Ignored patterns: {', '.join(report.ignored)}")
    lines.append("")

    def _emit_group(label: str, dirs: list[Path], uniques: list[Path]) -> None:
        lines.append(f"{label} ({len(uniques)} item(s))")
        lines.append("Directories:")
        for d in dirs:
            lines.append(f"  - {d}")
        lines.append("Unique items:")
        for p in uniques:
            lines.append(f"  {p}")
        lines.append("")

    _emit_group("Group A only", report.dirs_a, report.result.unique_a)
    _emit_group("Group B only", report.dirs_b, report.result.unique_b)

    if report.mode == "proxy-frames":
        lines.append("=" * 72)
        lines.append(
            f"Frame count mismatches ({len(report.result.frame_mismatches)} item(s))"
        )
        lines.append("=" * 72)
        for m in sorted(report.result.frame_mismatches, key=_diff_sort_key):
            lines.append(f"Basename: {m.basename}")
            lines.append(f"  Group A: {m.file_a} ({m.frames_a} frames)")
            lines.append(f"  Group B: {m.file_b} ({m.frames_b} frames)")
            lines.append(f"  Difference: {m.difference}")
            lines.append(f"  Path A: {m.path_a}")
            lines.append(f"  Path B: {m.path_b}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def export_csv(report: Report, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Mode", report.mode])
        writer.writerow(
            ["Generated", report.generated_at.isoformat(timespec="seconds")]
        )
        if report.ignored:
            writer.writerow(["Ignored patterns", *report.ignored])
        writer.writerow([])
        writer.writerow(["Group A directories", *(str(p) for p in report.dirs_a)])
        writer.writerow(["Group B directories", *(str(p) for p in report.dirs_b)])
        writer.writerow([])
        writer.writerow(["Group", "Path"])
        for p in report.result.unique_a:
            writer.writerow(["A", str(p)])
        for p in report.result.unique_b:
            writer.writerow(["B", str(p)])

        if report.mode == "proxy-frames":
            writer.writerow([])
            writer.writerow(["Frame count mismatches"])
            writer.writerow(
                [
                    "Basename",
                    "File A",
                    "Frames A",
                    "File B",
                    "Frames B",
                    "Difference",
                    "Path A",
                    "Path B",
                ]
            )
            for m in sorted(report.result.frame_mismatches, key=_diff_sort_key):
                writer.writerow(
                    [
                        m.basename,
                        m.file_a,
                        m.frames_a,
                        m.file_b,
                        m.frames_b,
                        m.difference,
                        str(m.path_a),
                        str(m.path_b),
                    ]
                )


_HTML_STYLE = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    margin: 0;
    padding: 24px;
    line-height: 1.5;
    color: #333;
    background-color: #f5f6f8;
}
.page { max-width: 1400px; margin: 0 auto; }
h2 { margin: 0 0 12px; }
.meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.chip {
    background-color: #e9ecef; border: 1px solid #dee2e6; border-radius: 999px;
    padding: 4px 14px; font-size: 0.88em;
}
.chip strong { margin-right: 4px; }
.stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.stat {
    background-color: #fff; border: 1px solid #ddd; border-radius: 8px;
    padding: 10px 18px; min-width: 150px;
}
.stat .num { font-size: 1.6em; font-weight: 700; display: block; }
.stat.a .num { color: #b02a37; }
.stat.b .num { color: #1a5fa8; }
.stat.warn .num { color: #856404; }
.stat .label { font-size: 0.85em; color: #666; }
.toolbar {
    position: sticky; top: 0; z-index: 10;
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
    background-color: #fff; border: 1px solid #ddd; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 20px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.toolbar input[type="search"] {
    flex: 1; min-width: 220px; padding: 8px 12px; font-size: 1em;
    border: 1px solid #ccc; border-radius: 6px;
}
.toolbar button {
    padding: 8px 16px; font-size: 0.92em; cursor: pointer;
    border: 1px solid #ccc; border-radius: 6px; background-color: #f8f9fa;
}
.toolbar button:hover { background-color: #e9ecef; }
details.section {
    background-color: #fff; border: 1px solid #ddd; border-radius: 8px;
    margin-bottom: 20px; overflow: hidden;
}
details.section > summary {
    cursor: pointer; user-select: none; list-style: none;
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px; font-size: 1.1em; font-weight: 600;
    background-color: #f8f9fa;
}
details.section > summary::-webkit-details-marker { display: none; }
details.section[open] > summary { border-bottom: 1px solid #ddd; }
.chev { margin-left: auto; transition: transform 0.15s; font-size: 0.8em; color: #888; }
details.section[open] .chev { transform: rotate(90deg); }
.count {
    border-radius: 999px; padding: 2px 12px; font-size: 0.8em; font-weight: 700;
}
.count.a { background-color: #ffeeee; color: #b02a37; }
.count.b { background-color: #eef4fb; color: #1a5fa8; }
.count.warn { background-color: #fff3cd; color: #856404; }
.section-body { padding: 14px 18px 18px; }
.dirs { margin-bottom: 12px; }
.dirs-label { font-size: 0.85em; color: #666; margin-bottom: 6px; }
.path-text {
    background-color: #f8f9fa; padding: 8px 12px; border-radius: 4px;
    border: 1px solid #e3e5e8; word-break: break-all; margin-bottom: 5px;
    font-size: 0.92em;
}
table { border-collapse: collapse; width: 100%; margin: 0; }
th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; word-break: break-all; }
th { background-color: #f2f2f2; font-weight: 600; }
.group-a { background-color: #ffeeee; }
.group-b { background-color: #eef4fb; }
.mismatch { background-color: #fff3cd; }
.empty-note {
    background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724;
    border-radius: 6px; padding: 12px 16px;
}
.warning-note {
    background-color: #fff3cd; border: 1px solid #ffc107; color: #856404;
    border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;
}
.no-results { color: #888; padding: 12px 16px; display: none; }
"""

_HTML_SCRIPT = """
function setAll(open) {
  document.querySelectorAll('details.section').forEach(function (d) { d.open = open; });
}
var filterBox = document.getElementById('filter');
function applyFilter() {
  var q = filterBox.value.trim().toLowerCase();
  document.querySelectorAll('details.section').forEach(function (sec) {
    var visible = 0;
    sec.querySelectorAll('tbody tr').forEach(function (tr) {
      var hit = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
      tr.hidden = !hit;
      if (hit) visible++;
    });
    var count = sec.querySelector('.count');
    if (count) {
      count.textContent = q ? visible + ' / ' + count.dataset.total : count.dataset.total;
    }
    var noRes = sec.querySelector('.no-results');
    if (noRes) { noRes.style.display = (q && visible === 0) ? 'block' : 'none'; }
    if (q && visible > 0) { sec.open = true; }
  });
}
filterBox.addEventListener('input', applyFilter);
"""


def _fmt_num(value: int | float | str | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def _dirs_html(dirs: list[Path]) -> str:
    items = "".join(
        f'<div class="path-text">{html.escape(str(d))}</div>' for d in dirs
    )
    return f'<div class="dirs"><div class="dirs-label">Directories scanned:</div>{items}</div>'


def _section_html(
    title: str,
    badge_class: str,
    count: int,
    body: str,
) -> str:
    return f"""
<details class="section" open>
  <summary>
    {html.escape(title)}
    <span class="count {badge_class}" data-total="{count}">{count}</span>
    <span class="chev">&#9654;</span>
  </summary>
  <div class="section-body">{body}</div>
</details>
"""


def _group_section_html(
    label: str,
    badge_class: str,
    row_class: str,
    dirs: list[Path],
    uniques: list[Path],
) -> str:
    if uniques:
        rows = "".join(
            f'<tr class="{row_class}"><td>{html.escape(str(p))}</td></tr>'
            for p in uniques
        )
        listing = (
            f"<table><thead><tr><th>Path</th></tr></thead><tbody>{rows}</tbody></table>"
            '<div class="no-results">No paths match the current filter.</div>'
        )
    else:
        listing = '<div class="empty-note">No unique items — fully covered by the other group.</div>'
    body = _dirs_html(dirs) + listing
    return _section_html(f"{label} only", badge_class, len(uniques), body)


def _mismatches_html(mismatches: list[FrameMismatch]) -> str:
    if not mismatches:
        body = (
            '<div class="empty-note">Frame counts all match — every shared '
            "basename has matching frame counts.</div>"
        )
        return _section_html("Frame count mismatches", "warn", 0, body)
    rows = "".join(
        f"""
<tr class="mismatch">
  <td>{html.escape(m.basename)}</td>
  <td>{html.escape(m.file_a)}</td>
  <td>{_fmt_num(m.frames_a)}</td>
  <td>{html.escape(m.file_b)}</td>
  <td>{_fmt_num(m.frames_b)}</td>
  <td><strong>{_fmt_num(m.difference)}</strong></td>
</tr>"""
        for m in sorted(mismatches, key=_diff_sort_key)
    )
    body = f"""
<div class="warning-note">Shared basenames with differing frame counts — likely incomplete or corrupted proxies.</div>
<table>
  <thead>
    <tr>
      <th>Basename</th><th>File A</th><th>Frames A</th>
      <th>File B</th><th>Frames B</th><th>Difference</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<div class="no-results">No rows match the current filter.</div>
"""
    return _section_html(
        "Frame count mismatches", "warn", len(mismatches), body
    )


def export_html(report: Report, path: Path) -> None:
    mode_label = _MODE_LABELS.get(report.mode, report.mode)

    is_frames = report.mode == "proxy-frames"
    mismatch_section = (
        _mismatches_html(report.result.frame_mismatches) if is_frames else ""
    )
    mismatch_stat = (
        f"""
    <div class="stat warn"><span class="num">{len(report.result.frame_mismatches)}</span>
      <span class="label">Frame mismatches</span></div>"""
        if is_frames
        else ""
    )

    ignored_chip = (
        f"""
    <span class="chip"><strong>Ignored:</strong>
      {html.escape(", ".join(report.ignored))}</span>"""
        if report.ignored
        else ""
    )

    section_a = _group_section_html(
        "Group A", "a", "group-a", report.dirs_a, report.result.unique_a
    )
    section_b = _group_section_html(
        "Group B", "b", "group-b", report.dirs_b, report.result.unique_b
    )

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>fcmp report</title>
  <style>{_HTML_STYLE}</style>
</head>
<body>
<div class="page">
  <h2>File Comparison Report</h2>
  <div class="meta">
    <span class="chip"><strong>Mode:</strong> {html.escape(mode_label)}</span>
    <span class="chip"><strong>Generated:</strong> {report.generated_at.isoformat(timespec="seconds")}</span>
    {ignored_chip}
  </div>
  <div class="stats">
    <div class="stat a"><span class="num">{len(report.result.unique_a)}</span>
      <span class="label">Only in Group A</span></div>
    <div class="stat b"><span class="num">{len(report.result.unique_b)}</span>
      <span class="label">Only in Group B</span></div>
    {mismatch_stat}
  </div>
  <div class="toolbar">
    <input type="search" id="filter" placeholder="Filter paths&hellip;" autocomplete="off">
    <button type="button" onclick="setAll(true)">Expand all</button>
    <button type="button" onclick="setAll(false)">Collapse all</button>
  </div>
  {mismatch_section}
  {section_a}
  {section_b}
</div>
<script>{_HTML_SCRIPT}</script>
</body>
</html>"""

    with path.open("wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(body.encode("utf-8"))


EXPORTERS: dict[str, Exporter] = {
    "json": export_json,
    "txt": export_txt,
    "csv": export_csv,
    "html": export_html,
}


def export(report: Report, path: Path, fmt: str) -> None:
    try:
        exporter = EXPORTERS[fmt]
    except KeyError as exc:
        raise ValueError(f"Unknown format: {fmt!r}. Choose from {sorted(EXPORTERS)}.") from exc
    exporter(report, path)
