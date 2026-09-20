.PHONY: install test lint typecheck compare report gate dashboard demo clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/guardbench/ --cov=guardbench -q

lint:
	ruff check guardbench tests

typecheck:
	mypy guardbench

compare:
	guardbench compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv

report:
	guardbench report --run latest

gate:
	guardbench gate --config gate.json --run latest

dashboard:
	guardbench dashboard --open

demo: compare report gate dashboard

clean:
	rm -rf report/ htmlcov/ .coverage .pytest_cache .ruff_cache .mypy_cache dist/ build/
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name ".DS_Store" -delete
