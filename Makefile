.PHONY: install run

install:
	uv sync

run:
	uv run uvicorn src.main:app --reload --port 8000
