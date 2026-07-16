# fcmp

Check that every file in the source directory tree also exists in the
destination, by comparing filenames across the nested hierarchy.

Built for verifying transcode jobs: after producing proxies from source clips,
confirm no clip was dropped. In a long-running session, corrupted clips can be
skipped silently — this catches those gaps.

- **Proxy mode** (default) — match video files by basename, ignoring extension
- **Normal mode** — match all files by filename (name + extension)
- **Proxy-frames mode** — proxy mode plus frame-count verification

Exports to JSON, TXT, CSV, or HTML (or any combination in a single run).
The HTML report is interactive: sections collapse/expand, and a live filter
box narrows the path lists.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for install / run
- `mediainfo` CLI (only for `proxy-frames` mode):

  ```bash
  # macOS
  brew install mediainfo

  # Linux
  sudo apt-get install mediainfo

  # Windows
  # https://mediaarea.net/en/MediaInfo/Download
  ```

## Install

### As a tool (recommended)

Install straight from GitHub with `uv` — no clone, no venv management. `fcmp`
lands on your PATH like any `brew`- or `winget`-installed CLI:

```bash
uv tool install git+https://github.com/geekshootjack/fcmp

# then, from anywhere:
fcmp -a /src -b /backup
```

Maintenance:

```bash
# pick up new commits later
uv tool upgrade fcmp

# install a specific branch or tag
uv tool install git+https://github.com/geekshootjack/fcmp@v0.1.0

# one-off run without installing anything
uvx --from git+https://github.com/geekshootjack/fcmp fcmp -a /src -b /backup
```

### For development

```bash
git clone https://github.com/geekshootjack/fcmp.git
cd fcmp
uv sync
```

`uv sync` creates a virtualenv at `.venv/` and installs the package plus its
dependencies. The `fcmp` command is available via `uv run fcmp ...` or by activating
the venv.

## Usage

```
fcmp -a DIR [DIR ...] -b DIR [DIR ...]
     [-m {normal,proxy,proxy-frames}]
     [-f {json,txt,csv,html} ...]
     [-i PATTERN [PATTERN ...]]
     [-o OUTPUT_DIR] [-q]
```

### Options

| Flag | Description | Default |
| --- | --- | --- |
| `-a`, `--group-a` | One or more directories making up group A | required |
| `-b`, `--group-b` | One or more directories making up group B | required |
| `-m`, `--mode` | `normal`, `proxy`, or `proxy-frames` | `proxy` |
| `-f`, `--format` | One or more of `json`, `txt`, `csv`, `html` | `html` |
| `-i`, `--ignore` | Name patterns to exclude from the comparison (glob syntax, case-insensitive; trailing `/` restricts a pattern to directories) | none |
| `-o`, `--output-dir` | Directory to write reports into | current dir |
| `-q`, `--quiet` | Suppress progress and summary output | off |
| `-v`, `--version` | Print version and exit | — |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `2` | Invalid arguments or missing prerequisite (e.g. mediainfo for `proxy-frames`) |

### JSON report format

The JSON export is a stable interface for downstream tools:

| Key | Type |
| --- | --- |
| `format_version` | `int` — schema version, currently `1` |
| `mode` | `str` — `normal`, `proxy`, or `proxy-frames` |
| `generated_at` | `str` — ISO 8601 timestamp |
| `ignored` | `list[str]` — ignore patterns in effect |
| `group_a.directories`, `group_b.directories` | `list[str]` |
| `unique_in_a`, `unique_in_b` | `list[str]` — absolute paths |
| `frame_mismatches` | `list[obj]` — proxy-frames mode only; includes `path_a`, `path_b` |

New keys may be added at any time; keys are only renamed/removed in a MAJOR
release, together with a `format_version` bump. Consumers should check
`format_version` and fail clearly on versions they don't understand.

## Examples

```bash
# Simple: verify proxies against originals (proxy mode is the default),
# write an HTML report to the current dir.
uv run fcmp -a /Volumes/Originals -b /Volumes/Proxies

# Compare all files by exact name (backup mirrors, non-video trees).
uv run fcmp -a /src -b /backup -m normal

# Multiple formats in one run.
uv run fcmp -a /src -b /backup -m normal -f html json csv

# Multiple directories per group (supersedes the old "+" syntax).
uv run fcmp -a /part1 /part2 /part3 -b /mirror -m normal -o reports/

# Ignore sync/hash artifacts so only real media differences are reported.
uv run fcmp -a /src -b /backup -m normal -i _gsdata_ '*.log' '*.mhl' ascmhl/

# Full proxy verification: basename match + frame-count check.
uv run fcmp -a /Volumes/Originals -b /Volumes/Proxies -m proxy-frames -f html
```

## Real-World Scenarios

**Video production workflow:**

```bash
# Compare original footage with proxy files (proxy mode is the default).
uv run fcmp -f html \
  -a /Volumes/Storage/Originals \
  -b /Volumes/EditDrive/Proxies

# Same, but export both HTML and JSON.
uv run fcmp -f html json \
  -a /Volumes/Storage/Originals \
  -b /Volumes/EditDrive/Proxies

# Advanced verification with frame-count checking.
uv run fcmp -m proxy-frames -f html \
  -a /Volumes/Storage/Originals \
  -b /Volumes/EditDrive/Proxies
```

**LAN storage via Windows UNC paths:**

```powershell
# Compare footage on a NAS share against a local proxy drive.
# UNC paths work as-is — no drive-letter mapping needed.
uv run fcmp -f html -a "\\nas\footage\ProjectX" -b "D:\Proxies\ProjectX"
```

Note: in PowerShell, don't end a quoted path with a backslash
(`"\\nas\share\"` turns `\"` into an escaped quote) — write
`"\\nas\share"` instead. Mapped drive letters (`Z:\...`) work equally well.
`proxy-frames` mode reads video headers over the network, so frame-count
checks against a NAS are noticeably slower than against local disks.

**Copy-completeness check across multiple drives:**

```bash
# Confirm every file in Backup1 + Backup2 also exists on the master drive.
uv run fcmp -m normal -f csv \
  -a /Volumes/Backup1 /Volumes/Backup2 \
  -b /Volumes/Master
```

**Multi-location archive:**

```bash
# Check whether every archived file made it into the current project set.
uv run fcmp -m normal -f json \
  -a /Archive/2024/Q1 /Archive/2024/Q2 /Archive/2024/Q3 \
  -b /CurrentProjects
```

**Proxy-encoding QC:**

```bash
# Flag proxies that are missing or have the wrong frame count.
uv run fcmp -m proxy-frames -f html \
  -a /Production/Camera_Originals \
  -b /Production/Proxies
```

## Project layout

```
fcmp/
├── pyproject.toml
├── src/fcmp/
│   ├── __init__.py       # __version__
│   ├── __main__.py       # python -m fcmp
│   ├── cli.py            # argparse + rich output
│   ├── scanner.py        # directory walk, FileEntry
│   ├── compare.py        # ComparisonResult, FrameMismatch
│   ├── mediainfo.py      # mediainfo subprocess wrapper
│   ├── filters.py        # skip patterns + video extension set
│   └── exporters.py      # json/txt/csv/html renderers
└── tests/                # pytest suite
```

## Development

```bash
# Install dev deps (pytest + coverage).
uv sync --all-groups

# Run the full test suite.
uv run pytest

# Coverage.
uv run pytest --cov=fcmp --cov-report=term-missing
```
