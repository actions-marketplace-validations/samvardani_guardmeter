# Contributing to GuardMeter

Thanks for your interest. Bug reports, guard adapters, dataset improvements, and docs fixes are all welcome.

## Development setup

```bash
git clone https://github.com/samvardani/GuardMeter.git
cd GuardMeter
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/guardmeter/ -q
```

All dependencies live in `pyproject.toml`. There are no `requirements*.txt` files.

## Before opening a PR

- `pytest tests/guardmeter/ -q` passes
- `ruff check guardmeter tests` passes
- `mypy guardmeter` passes (or the failure is pre-existing and noted in the PR)
- If you changed evaluation or gate behaviour, run the full pipeline once:

  ```bash
  guardmeter compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv
  guardmeter report --run latest
  guardmeter gate --config gate.json --run latest
  ```

- Add a line to `CHANGELOG.md` under an `[Unreleased]` heading

## Adding a guard

Subclass `guardmeter.core.guard.Guard`, implement `classify(text) -> GuardResult`, and register it:

```python
from guardmeter.core.registry import register
register("my-guard", MyGuard)
```

Third-party packages can expose guards through the `guardmeter.guards` entry-point group so they resolve by name without any import.

## Releases

Maintainers cut releases by bumping the version in `pyproject.toml` and `guardmeter/__init__.py`, updating `CHANGELOG.md`, and pushing a `vX.Y.Z` tag. The `release.yml` workflow builds, publishes to PyPI via trusted publishing, and creates the GitHub release.
