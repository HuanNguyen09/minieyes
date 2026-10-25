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

# Offline only: init without backend, plan-only tests against mock providers. No AWS credentials needed.
TF_DIRS := infra/terraform/bootstrap

test-tf:
	terraform fmt -check -recursive infra/terraform
	@set -e; for d in $(TF_DIRS); do \
		echo "== $$d"; \
		terraform -chdir=$$d init -backend=false -input=false >/dev/null; \
		terraform -chdir=$$d validate; \
		if [ -d $$d/tests ]; then terraform -chdir=$$d test; fi; \
		tflint --chdir=$$d --config=$(CURDIR)/infra/terraform/.tflint.hcl; \
	done

test-rules:
	promtool check rules observability/alerts/*.rules.yaml
	promtool test rules observability/alerts/tests/*.yaml
	bash observability/alertmanager/test.sh
	uv run --no-project --with pytest --with pyyaml pytest observability -q

e2e:  # needs the model exported first: see triton/scripts/export_model.py
	docker compose up -d --build --wait
	uv run --no-project --with pytest --with httpx pytest tests/e2e -m e2e -v
