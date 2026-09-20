# GuardMeter — Claude Code Project Memory

## What this project is
AI safety guard evaluation framework. Compares a baseline guard vs a candidate guard
on labeled datasets. Outputs per-slice metrics, HTML report, and CI gate (pass/fail).

## Package being built
- Source of truth: `guardmeter/` package (refactored from `src/`)
- CLI entry point: `guardmeter` (via click)
- Install: `pip install -e ".[dev]"`

## Key architectural decisions
- Guard ABC + Registry pattern (replaces hardcoded imports in run_compare.py)
- Pydantic DatasetRecord schema (replaces ad-hoc CSV parsing)
- EvalResults dataclass (replaces dict-passing between modules)
- SQLiteStore for run history (reproducibility via run_id + dataset SHA + git commit)

## Files to preserve logic from
- src/guards/baseline.py → RegexGuard(profile="baseline")
- src/guards/candidate.py → RegexGuard(profile="enhanced")
- src/runner/run_compare.py → Evaluator class
- src/report/build_report.py → ReportGenerator class
- src/runner/ci_gate.py → GateChecker class
- templates/report.html → guardmeter/report/templates/report.html

## Do not delete src/ until Phase 9 tests pass

## Known issues (fix as you go)
- .DS_Store files committed to repo — add to .gitignore and remove
- 37 open PRs — do not touch, they'll be closed when branches are cleaned up
- backup.py files in src/ — delete in Phase 10
- run_compare.py imports guards by hardcoded path — the whole point of Phase 2 is to fix this

## Tests location
- New guardmeter tests live in `tests/guardmeter/`
- Run with: `pytest tests/guardmeter/ --cov=guardmeter`
