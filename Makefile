# Run from WSL/Linux/macOS or CI. On Windows without make, run the uv commands directly.
.PHONY: test lint fmt test-helm test-tf test-rules test-ansible e2e

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

# Offline only: init without backend, plan-only tests against mock providers. No AWS credentials needed.
TF_DIRS := infra/terraform/bootstrap \
	infra/terraform/modules/vpc \
	infra/terraform/modules/ecr \
	infra/terraform/modules/github-oidc \
	infra/terraform/modules/eks \
	infra/terraform/modules/edge-ec2 \
	infra/terraform/modules/budgets \
	infra/terraform/envs/lab \
	infra/terraform/envs/lab-platform

test-tf:
	terraform fmt -check -recursive infra/terraform
	@set -e; for d in $(TF_DIRS); do \
		echo "== $$d"; \
		terraform -chdir=$$d init -backend=false -input=false >/dev/null; \
		terraform -chdir=$$d validate; \
		if [ -d $$d/tests ]; then terraform -chdir=$$d test; fi; \
		tflint --chdir=$$d --config=$(CURDIR)/infra/terraform/.tflint.hcl; \
	done
	trivy config --quiet --exit-code 1 --severity HIGH,CRITICAL \
		--ignorefile infra/terraform/.trivyignore infra/terraform

test-rules:
	promtool check rules observability/alerts/*.rules.yaml
	promtool test rules observability/alerts/tests/*.yaml
	bash observability/alertmanager/test.sh
	uv run --no-project --with pytest --with pyyaml pytest observability -q

# Needs ansible-core, ansible-lint, molecule and molecule-plugins[docker] (see
# docs/runbooks/edge-node-ansible.md). ANSIBLE_CONFIG is explicit because Ansible
# ignores ansible.cfg in a world-writable directory (WSL /mnt/c checkouts).
ANSIBLE_DIR := infra/ansible
ANSIBLE_ENV := ANSIBLE_CONFIG=$(CURDIR)/$(ANSIBLE_DIR)/ansible.cfg
test-ansible:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_ENV) ansible-galaxy collection install -r requirements.yml
	cd $(ANSIBLE_DIR) && $(ANSIBLE_ENV) ansible-lint
	cd $(ANSIBLE_DIR) && $(ANSIBLE_ENV) ansible-playbook --syntax-check site.yml verify.yml
	cd $(ANSIBLE_DIR)/roles/common && $(ANSIBLE_ENV) molecule test
	cd $(ANSIBLE_DIR)/roles/node_exporter && $(ANSIBLE_ENV) molecule test

e2e:  # needs the model exported first: see triton/scripts/export_model.py
	docker compose up -d --build --wait
	uv run --no-project --with pytest --with httpx pytest tests/e2e -m e2e -v
