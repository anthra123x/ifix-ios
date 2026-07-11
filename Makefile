.PHONY: install dev test clean

install:
	pip install -e .

dev:
	python3 -m venv dev/venv && \
	. dev/venv/bin/activate && \
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

detect:
	python -m ifix_ios detect

tui:
	python -m ifix_ios tui

monitor:
	python -m ifix_ios monitor

mock:
	python dev/mock_device.py

clean:
	rm -rf build/ dist/ *.egg-info/ __pycache__/
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
