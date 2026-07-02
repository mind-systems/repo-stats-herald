-include .env
export

.PHONY: install run tunnel dev eval

install:
	uv sync

run:
	uv run uvicorn src.main:app --reload --port 8000

tunnel:
	nc -z localhost 11434 || ssh -f -N -i $(SSH_KEY) -p $(SSH_PORT) -L 11434:127.0.0.1:11434 $(SSH_HOST)

dev: tunnel
	uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD

eval: tunnel
	uv run python -m scripts.eval
