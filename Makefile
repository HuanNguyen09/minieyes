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

test-helm:  # needs helm, the helm-unittest binary (or plugin) and kubeconform on PATH
	bash scripts/check-charts.sh

test-tf:
	@echo "TODO: terraform fmt/validate/test (#21)"

test-rules:
	promtool check rules observability/alerts/*.rules.yaml
	promtool test rules observability/alerts/tests/*.yaml
	bash observability/alertmanager/test.sh
	uv run --no-project --with pytest --with pyyaml pytest observability -q

e2e:  # needs the model exported first: see triton/scripts/export_model.py
	docker compose up -d --build --wait
	uv run --no-project --with pytest --with httpx pytest tests/e2e -m e2e -v
