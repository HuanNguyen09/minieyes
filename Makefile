# Run from WSL/Linux/macOS or CI. On Windows without make, run the uv commands directly.
.PHONY: test lint fmt test-helm test-tf test-rules e2e

test:
	uv run --package minieyes-detector pytest apps/detector --cov=minieyes_detector --cov-report=term-missing
	uv run --package minieyes-api pytest apps/event-api --cov=minieyes_api --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test-helm:
	@echo "TODO: helm lint + helm-unittest (#19)"

test-tf:
	@echo "TODO: terraform fmt/validate/test (#21)"

test-rules:
	@echo "TODO: promtool test rules (#31)"

e2e:
	@echo "TODO: docker compose up + pytest -m e2e (#17)"
