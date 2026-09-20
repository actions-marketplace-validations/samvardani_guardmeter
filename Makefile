.PHONY: install test lint typecheck compare report gate dashboard demo clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/guardmeter/ --cov=guardmeter -q

lint:
	ruff check guardmeter tests

typecheck:
	mypy guardmeter

compare:
	guardmeter compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv

report:
	guardmeter report --run latest

gate:
	guardmeter gate --config gate.json --run latest

dashboard:
	guardmeter dashboard --open

demo: compare report gate dashboard

clean:
	rm -rf report/ htmlcov/ .coverage .pytest_cache .ruff_cache .mypy_cache dist/ build/
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name ".DS_Store" -delete
