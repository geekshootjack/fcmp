# Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`
Common types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

# Commit Workflow

- After each completed, verified modification batch, create a git commit by default without waiting for an extra user reminder.
- Use small, reversible commits so problematic changes can be reverted cleanly.
- Only hold off on committing when the user explicitly asks not to commit yet, or when the work is still in a broken/unverified intermediate state.
- Do not push unless the user asks for a push.

# CI

GitHub Actions (`.github/workflows/ci.yml`) runs pytest on every push to
`main` and every PR, across ubuntu/windows/macos × Python 3.10/3.13.

Write platform-independent tests — both of these have caused real cross-OS
CI failures:
- Never hardcode path separators; build expectations with `Path` /
  `os.path` so they hold on Windows (`\`) and POSIX (`/`).
- Never rely on filesystem enumeration order (`os.walk`, `scandir`); it is
  alphabetical on NTFS but arbitrary on ext4. The scanner sorts its
  traversal for this reason — keep it deterministic.

# Releases

Version is derived automatically from git tags via `hatch-vcs` — there is no version string to edit in code.

**Semver rules:**
- `PATCH` (x.x.N) — bug fixes, internal cleanup, no behaviour change
- `MINOR` (x.N.0) — new feature or behaviour, backwards compatible
- `MAJOR` (N.0.0) — breaking change: CLI flags removed/renamed, output format changed, etc.

**When to tag:** when the accumulated commits since the last tag are ready for users — not every commit, not every PR. A meaningful feature or important fix is a good trigger.

**How to release:**
```sh
git tag v2.1.0
git push origin v2.1.0
```

That's it — no file edits needed. The version is read from the tag at build/install time.

Pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds the
sdist + wheel with `uv build` and publishes a GitHub Release with
auto-generated notes. No PyPI publishing — users install with
`uv tool install git+https://github.com/geekshootjack/fcmp[@vX.Y.Z]` or from
the release wheel.
