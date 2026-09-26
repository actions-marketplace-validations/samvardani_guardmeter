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

Subclass `guardmeter.core.guard.Guard`, implement `predict(text, **meta) -> GuardResult`, and register it:

```python
from guardmeter.core.registry import register
register("my-guard", MyGuard)
```

Third-party packages can expose guards through the `guardmeter.guards` entry-point group so they resolve by name without any import.

## Contributing rows

The **Agentic Attack Dataset** (`dataset/agentic/v1/`) is frozen: corrections go
to `v1.1`, breaking changes to `v2`. If you're adding rows to a working dataset,
follow these rules — `guardmeter dataset validate` enforces most of them and CI
runs it, so a PR that fails validation won't merge.

**Native reviewers wanted.** The multilingual v2 dataset needs native speakers to
review each language before it can be released. See
[docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md) — reviewers are named in the
dataset card and credited under CC-BY-4.0.

**Content rules (non-negotiable):**

- **No working exploits** against real products, no real credentials, no real
  people, no real company names, no PII, no malware code. Injection text
  references generic tools only ("the email tool", "the file system").
- **Author every row fresh.** No copying from public jailbreak collections —
  licence and provenance would be unclear.
- **Farsi rows are natural Farsi** written for Farsi speakers — not translations
  of English rows, and not transliteration.
- **No template stamping.** Rows within a family must differ in structure,
  register, length, and framing.

**Schema:** each row needs `id` (unique, `[A-Za-z0-9._-]+`), `text`, `label`
(`benign` | `borderline` | `unsafe`), `category`, `language`, and — for agentic
rows — `attack_family`, `attack_technique`, `target`
(`override`/`exfiltrate`/`tool_action`/`persona`/`none`), and `context` for the
`multi_turn` and `indirect_injection` families. `benign` rows must have
`target: none`; `unsafe` rows must not.

**What `validate` checks:** id uniqueness/format, no exact or near-duplicate rows
within a family (token-set Jaccard ≥ 0.6), language script ratios (fa ≥ 60%
Arabic script, en < 10%), decoded-payload sanity for the `encoded` family, and
label/target/context consistency.

```bash
guardmeter dataset validate path/to/data.jsonl   # must exit 0
guardmeter dataset stats    path/to/data.jsonl --markdown
```

Bump the dataset's own `CHANGELOG.md` and `DATASET_CARD.md` composition table in
the same PR.

## Releases

Maintainers cut releases by bumping the version in `pyproject.toml` and `guardmeter/__init__.py`, updating `CHANGELOG.md`, and pushing a `vX.Y.Z` tag. The `release.yml` workflow builds, publishes to PyPI via trusted publishing, and creates the GitHub release.
