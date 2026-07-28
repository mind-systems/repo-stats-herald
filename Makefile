-include .env.dev
export

.PHONY: install run tunnel dev eval test report-daily report-weekly

install:
	uv sync

run:
	uv run uvicorn src.main:app --reload --port 8000

test:
	uv run pytest

tunnel:
	nc -z localhost 11434 || ssh -f -N -i $(SSH_KEY) -p $(SSH_PORT) -L 11434:127.0.0.1:11434 $(SSH_HOST)

dev: tunnel
	uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD

eval: tunnel
	uv run python -m scripts.eval

report-daily: tunnel
	uv run python -m scripts.report --schedule daily

report-weekly: tunnel
	uv run python -m scripts.report --schedule weekly
