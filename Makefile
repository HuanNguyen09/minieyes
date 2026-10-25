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

test-helm:
	@echo "TODO: helm lint + helm-unittest (#19)"

test-tf:
	@echo "TODO: terraform fmt/validate/test (#21)"

test-rules:
	@echo "TODO: promtool test rules (#31)"

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

e2e:
	@echo "TODO: docker compose up + pytest -m e2e (#17)"
