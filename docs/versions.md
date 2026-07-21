# Pinned versions

Agent Access is early preview — behaviour can change between builds. Record the
exact versions you verified against (Phase 0), so anyone reproducing your setup
uses the same ones.

> **TODO (fill after live Phase 0 run):** replace the `<unverified>` values below
> with the output of `aac --version` and `bw --version` on the machine where you
> confirmed `aac connect` works end-to-end.

| Tool | Verified version | Notes |
|---|---|---|
| `aac` (Agent Access) | `<unverified>` | from the [releases page](https://github.com/bitwarden/agent-access/releases) |
| `bw` (Bitwarden CLI) | `<unverified>` | `winget install Bitwarden.CLI` |
| Python | 3.12+ (dev: 3.14.3) | see `pyproject.toml` `requires-python` |

## Python dependencies

Runtime + dev dependencies are declared in [`pyproject.toml`](../pyproject.toml)
(`[project].dependencies` and the `dev` extra). `requirements.txt` /
`requirements-dev.txt` mirror them for the plain-venv workflow.

To capture an exact, reproducible snapshot of what you actually installed:

```powershell
.\.venv\Scripts\python.exe -m pip freeze > docs/requirements.lock.txt
```
