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

### Authoring rows in a new language

Each language in v2 is authored natively, not translated. To add one:

1. Write `docs/languages/<code>.md` **first** — registers/markets, romanization
   system, and the script traps a reviewer should watch for (see the existing
   notes for the shape).
2. Author ≥ 6 unsafe + ≥ 3 benign rows per family across all 14 families, plus
   ≥ 5 borderline. Reason in the language; do not translate the English rows.
   Give cross-lingual families (`language_switch`, `script_mixing`, `encoded`)
   payloads distinct from other languages to avoid cross-language near-dups.
3. `guardmeter dataset validate <data.jsonl> --language <code>` and the full-file
   validate must both pass, then update `MANIFEST.json` and the card.
4. The language ships as `authored`. It becomes `reviewed` only after a native
   speaker signs off through the review workflow — see
   [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md).

## Releases

Maintainers cut releases by bumping the version, updating `CHANGELOG.md`, and
pushing a `vX.Y.Z` tag. `release.yml` builds, publishes to PyPI via trusted
publishing, attaches the current `dataset/agentic/v2/` files, and creates the
GitHub release.

**Release checklist:**

- [ ] Version bumped in **three** places: `pyproject.toml`, `guardmeter/__init__.py`, `action.yml` (`default` + the `@vX.Y.Z` example).
- [ ] `CHANGELOG.md` entry added.
- [ ] Fetch pins in `guardmeter/data/fetch.py` updated if any dataset file changed, and the release **tag** on the affected `DatasetRelease` retargeted to the new version (fetch downloads assets from that tag's GitHub release).
- [ ] Results docs regenerated if numbers changed (`docs/AGENTIC_RESULTS.md`, `docs/OPOD_SCENARIO_RESULTS.md`, `docs/MULTILINGUAL_RESULTS.md`).
- [ ] Dataset card status table and `MANIFEST.json` current (row counts, review status).
- [ ] README badges current — including the hard-coded **languages** badge (`N · X authored · Y reviewed`).
- [ ] `ruff` / `mypy` / `pytest` clean; after publish, a clean-venv `pip install` → `dataset fetch` → `validate`.
