# MiniEyes — notes for Claude Code

Read `PRD.md` first. Work is tracked as GitHub issues in `HuanNguyen09/minieyes`; each issue lists the behaviours to drive with tests. Use `/tdd` per issue: one failing test, simplest passing code, refactor, repeat.

## Conventions
- Python 3.12, dependencies managed with `uv`. Each service is its own package under `apps/<service>/` with `src/` layout and `tests/`.
- Packages: `minieyes_detector` (apps/detector), `minieyes_api` (apps/event-api).
- Domain code (zones, postprocess, debounce, backoff) is pure: no I/O, no global state, time comes from an injected `Clock`.
- Adapters (RTSP, Triton, HTTP, DB) live behind small interfaces with in-memory fakes in `tests/fakes.py`.
- Test markers: default = unit (no network, no Docker, < 60 s total); `integration` needs Docker; `e2e` needs `docker compose up`.
- Metric names and labels must match PRD §7.2; alert names must match PRD §7.3.
- Lint/format: `ruff check` and `ruff format`. Type hints everywhere.
- AWS: every IAM role is named `minieyes-*` with permissions boundary `Boundary-MiniEyes-Workload`; every resource is tagged `Project=minieyes` (see `infra/aws/iam/README.md`). Never use Bedrock.
- Commit messages reference the issue: `feat(detector): debounce intrusions (#5)`; PRs use `Closes #N`.

## Commands
```bash
make test            # unit tests for all Python services
make lint            # ruff, hadolint, helm lint, tflint, ansible-lint
make test-helm       # helm-unittest for charts/
make test-tf         # terraform fmt -check, validate, terraform test
make test-rules      # promtool test rules observability/alerts/tests/*.yaml
make e2e             # docker compose up + pytest -m e2e
```

## Never
- Commit secrets, kubeconfigs, `.tfstate`, `.onnx`/`.pt` files or videos.
- Run `terraform apply`/`destroy` or touch AWS without the owner asking.
