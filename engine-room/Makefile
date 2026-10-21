# =============================================================================
# Nexus — developer task runner
# =============================================================================
# Thin wrappers over `uv run` so local commands match CI exactly. Recipes assume
# a POSIX shell (Linux/macOS, or Git Bash / WSL on Windows). Windows users
# without `make` can run the underlying `uv run ...` commands directly — see
# docs/development/DEVELOPMENT.md.
# =============================================================================

# Packages and their tests (Phase 1 foundation + Phase 2 infra + Phase 3 planning
# + Phase 4 context engineering + Phase 5 orchestration + Phase 6 harness
# + Phase 8A runtime core).
PACKAGES := nexus_core nexus_infra nexus_planning nexus_context nexus_orchestration nexus_harness nexus_runtime nexus_execution nexus_runtime_claude nexus_runtime_gemini nexus_runtime_shell nexus_runtime_adapters nexus_validation nexus_recovery nexus_reflection nexus_knowledge nexus_workflows nexus_research nexus_briefings nexus_operator
TESTS := tests/unit/nexus_core tests/unit/nexus_infra tests/unit/nexus_planning tests/unit/nexus_context tests/unit/nexus_orchestration tests/unit/nexus_harness tests/unit/nexus_runtime tests/unit/nexus_execution tests/unit/nexus_runtime_claude tests/unit/nexus_runtime_gemini tests/unit/nexus_runtime_shell tests/unit/nexus_runtime_adapters tests/unit/nexus_validation tests/unit/nexus_recovery tests/unit/nexus_reflection tests/unit/nexus_knowledge tests/unit/nexus_workflows tests/unit/nexus_research tests/unit/nexus_briefings tests/unit/nexus_operator tests/integration
COV_MIN := 95

.DEFAULT_GOAL := help
.PHONY: help install lint format format-check typecheck test test-cov \
        coverage-html check pre-commit build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies + register pre-commit hooks
	uv sync
	uv run pre-commit install

lint: ## Ruff lint (no autofix)
	uv run ruff check $(PACKAGES) $(TESTS)

format: ## Ruff auto-format in place
	uv run ruff format $(PACKAGES) $(TESTS)

format-check: ## Verify formatting without writing
	uv run ruff format --check $(PACKAGES) $(TESTS)

typecheck: ## MyPy strict
	uv run mypy $(PACKAGES)

test: ## Run the test suite (fast)
	uv run pytest $(TESTS) -q

test-cov: ## Run tests with coverage gate (term + xml + html)
	uv run pytest $(TESTS) \
		--cov=nexus_core \
		--cov=nexus_infra \
		--cov=nexus_planning \
		--cov=nexus_context \
		--cov=nexus_orchestration \
		--cov=nexus_harness \
		--cov=nexus_runtime \
		--cov=nexus_execution \
		--cov=nexus_runtime_claude \
		--cov=nexus_runtime_gemini \
		--cov=nexus_runtime_shell \
		--cov=nexus_runtime_adapters \
		--cov=nexus_validation \
		--cov=nexus_recovery \
		--cov=nexus_reflection \
		--cov=nexus_knowledge \
		--cov=nexus_workflows \
		--cov=nexus_research \
		--cov=nexus_briefings \
		--cov=nexus_operator \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		--cov-fail-under=$(COV_MIN)

coverage-html: test-cov ## Generate the HTML coverage report (htmlcov/index.html)
	@echo "Open htmlcov/index.html"

check: lint format-check typecheck test-cov ## Full local gate (matches CI)
	@echo "All quality gates passed."

pre-commit: ## Run every pre-commit hook against all files
	uv run pre-commit run --all-files

build: ## Build sdist + wheel
	uv build

clean: ## Remove caches and generated reports
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov coverage.xml dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
