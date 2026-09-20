# Contributing to GuardBench

Thanks for your interest. Bug reports, guard adapters, dataset improvements, and docs fixes are all welcome.

## Development setup

```bash
git clone https://github.com/samvardani/GuardBench.git
cd GuardBench
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/guardbench/ -q
```

All dependencies live in `pyproject.toml`. There are no `requirements*.txt` files.

## Before opening a PR

- `pytest tests/guardbench/ -q` passes
- `ruff check guardbench tests` passes
- `mypy guardbench` passes (or the failure is pre-existing and noted in the PR)
- If you changed evaluation or gate behaviour, run the full pipeline once:

  ```bash
  guardbench compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv
  guardbench report --run latest
  guardbench gate --config gate.json --run latest
  ```

- Add a line to `CHANGELOG.md` under an `[Unreleased]` heading

## Adding a guard

Subclass `guardbench.core.guard.Guard`, implement `classify(text) -> GuardResult`, and register it:

```python
from guardbench.core.registry import register
register("my-guard", MyGuard)
```

Third-party packages can expose guards through the `guardbench.guards` entry-point group so they resolve by name without any import.

## Releases

Maintainers cut releases by bumping the version in `pyproject.toml` and `guardbench/__init__.py`, updating `CHANGELOG.md`, and pushing a `vX.Y.Z` tag. The `release.yml` workflow builds, publishes to PyPI via trusted publishing, and creates the GitHub release.
