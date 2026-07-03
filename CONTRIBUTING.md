# Contributing to FlowPulse

## Ethical use

FlowPulse simulates human input for **authorized** security testing, research,
and lab environments only. Contributions that add or improve capabilities
specifically meant to evade legitimate security controls (EDR, monitoring
software, endpoint policy) rather than to make *authorized* testing more
realistic will not be accepted. When in doubt, open an issue describing the
use case before submitting a PR.

## Development setup

Requires Python 3.11+ on Windows (some functionality — the tray icon,
`GetLastInputInfo`, window enumeration — is Windows-only; core logic is
importable on other platforms for testing).

```powershell
git clone https://github.com/erquier/FlowPulse.git
cd FlowPulse
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

## Running tests

```powershell
python -m unittest tests.test_all -v
python smoke_test.py
```

Both must pass before opening a PR. If you're on Windows and see an
intermittent failure in `TestDetector`, see the note in that test class's
docstring — real mouse/keyboard activity on the machine running the suite is
mocked out for exactly this reason; if you add a new test that reads
`ActivityDetector.is_user_active()`, mock
`flowpulse.win32_api.milliseconds_since_last_input()` the same way.

## Linting, formatting, and type checking

```powershell
ruff check .
ruff format .
mypy flowpulse/
```

`ruff check`/`ruff format --check` run in CI (`.github/workflows/test.yml`)
and must pass. `mypy` runs in permissive mode
(`disallow_untyped_defs = false` in `pyproject.toml`) — new code in modules
that are already fully typed should stay fully typed, but partial typing
elsewhere won't fail CI.

## Making a change

1. Branch from `main`.
2. Keep commits focused — one logical change per commit, with a message
   explaining *why*, not just *what* (the diff already shows what changed).
3. Run the full verification above before pushing.
4. If you touch `flowpulse/config.py`'s schema (`_CONFIG_SCHEMA`, `_BOUNDS`,
   `_ORDERED_PAIRS`), update `docs/CONFIGURATION.md` to match.
5. If you touch `flowpulse/detector.py`, `flowpulse/engine.py`, or the tray
   message loop in `flowpulse/app.py`, do a manual smoke test on Windows —
   these have thin or no automated coverage around threading/UI behavior.

## Project structure

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the module map and the
two-layer activity-detection design.
