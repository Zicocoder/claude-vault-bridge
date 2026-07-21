# Phase 5 — packaging, CI, release polish

Turn the working code into something installable and maintainable.

## What landed

- **Package rename.** `src/` → `claude_vault_bridge/` so it installs under a real
  import name (not a generic `src`). All imports, tests, and docs updated.
- **`pyproject.toml`** — PEP 621 metadata, runtime dependencies, a `dev` extra
  (`pytest`), and a console entry point:
  ```
  [project.scripts]
  claude-vault-bridge = "claude_vault_bridge.main:main"
  ```
  So `pip install -e .` gives you a `claude-vault-bridge` command.
- **CI** — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the test
  suite on `windows-latest` across Python 3.12 and 3.13 on every push/PR. Badge in
  the README.
- **`docs/versions.md`** — where the verified `aac` / `bw` versions get pinned.
- **README** — install & run section, status bumped to *alpha*, roadmap complete.

## Install & test

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q      # 60 passing
```

## Not done yet (needs a live Phase 0 run — your side)

These are the only things between here and a tagged `v0.5.0` release:

1. **Demo GIF.** Record the real flow (hotkey → phone tap → form fills) and drop
   it in `docs/demo.gif`, referenced from the README. Needs the tool running
   against a real vault, so it can't be produced from here.
2. **Pin versions.** Fill the `<unverified>` rows in
   [`docs/versions.md`](versions.md) with your actual `aac --version` /
   `bw --version`.
3. **Tag the release.** Once 1–2 are done and you've confirmed an end-to-end fill:
   ```powershell
   git tag v0.5.0
   git push origin v0.5.0
   ```
   Optionally attach a built wheel (`python -m build`) to a GitHub Release.

Until then the version stays `0.5.0.dev0` — the code is feature-complete, but
"released" waits on a human having actually watched it fill a login.
