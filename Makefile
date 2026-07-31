# ============================================================
# ProcessScope — Makefile
# Linux Process Observability Platform
# ============================================================

SHELL := /bin/bash

# Project metadata
APP_NAME       := processscope
APP_DISPLAY    := ProcessScope
VERSION        := 0.1.0
ARCH           := $(shell uname -m)
OS             := $(shell uname -s | tr '[:upper:]' '[:lower:]')

# Build number: YYYYMMDD.HHMMSS.gitsha
GIT_SHA        := $(shell git rev-parse --short HEAD 2>/dev/null || echo "nogit")
GIT_BRANCH     := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE     := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
BUILD_NUMBER   := $(shell date -u +"%Y%m%d.%H%M%S").$(GIT_SHA)

# Directories
SRC_DIR        := src
WEB_DIR        := web
DIST_DIR       := dist
BUILD_DIR      := build
OUTPUT_DIR     := dist/output
CONFIGS_DIR    := configs

# Python
PYTHON         := python3
PIP            := pip3
VENV           := .venv
VENV_BIN       := $(VENV)/bin

# ============================================================
# Targets
# ============================================================

.PHONY: all build clean install dev test lint format \
        dashboard version package-tar package-deb package-rpm help

## help: Show this help message
help:
	@echo ""
	@echo "  $(APP_DISPLAY) v$(VERSION) — Build System"
	@echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | sort
	@echo ""

## version: Print version and build information
version:
	@echo "$(APP_DISPLAY)"
	@echo "  Version:      $(VERSION)"
	@echo "  Build:        $(BUILD_NUMBER)"
	@echo "  Git Commit:   $(GIT_SHA)"
	@echo "  Git Branch:   $(GIT_BRANCH)"
	@echo "  Build Date:   $(BUILD_DATE)"
	@echo "  Python:       $(shell $(PYTHON) --version 2>&1)"
	@echo "  Platform:     $(OS)/$(ARCH)"

## venv: Create Python virtual environment
venv:
	@echo "━━━ Creating virtual environment ━━━"
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip setuptools wheel build
	@echo "✓ Virtual environment created at $(VENV)/"

## install: Install ProcessScope in development mode
install: venv
	@echo "━━━ Installing ProcessScope (development mode) ━━━"
	$(VENV_BIN)/pip install -e ".[dev]"
	@echo "✓ ProcessScope installed"

## dev: Install and run in development mode
dev: install
	@echo "━━━ Starting ProcessScope (dev mode) ━━━"
	$(VENV_BIN)/processscope start --dev

## build: Build the production Python package
build: venv dashboard
	@echo "━━━ Building ProcessScope v$(VERSION) (build: $(BUILD_NUMBER)) ━━━"
	@mkdir -p $(BUILD_DIR)
	# Write build metadata
	@echo '{"version":"$(VERSION)","build_number":"$(BUILD_NUMBER)","git_commit":"$(GIT_SHA)","git_branch":"$(GIT_BRANCH)","build_date":"$(BUILD_DATE)"}' \
		> $(SRC_DIR)/processscope/_build_meta.json
	# Copy dashboard build into package
	@if [ -d "$(WEB_DIR)/dist" ]; then \
		rm -rf $(SRC_DIR)/processscope/dashboard; \
		cp -r $(WEB_DIR)/dist $(SRC_DIR)/processscope/dashboard; \
		echo "✓ Dashboard embedded"; \
	fi
	# Build wheel and sdist
	$(VENV_BIN)/python -m build --outdir $(BUILD_DIR)
	@echo "✓ Build complete: $(BUILD_DIR)/"

## dashboard: Build the React web dashboard
dashboard:
	@echo "━━━ Building Web Dashboard ━━━"
	@cd $(WEB_DIR) && npm install && npm run build
	@echo "✓ Dashboard built"

## test: Run the test suite
test:
	@echo "━━━ Running Tests ━━━"
	$(VENV_BIN)/pytest tests/ -v --tb=short --cov=processscope --cov-report=term-missing
	@echo "✓ Tests complete"

## lint: Run linters
lint:
	@echo "━━━ Running Linters ━━━"
	$(VENV_BIN)/ruff check $(SRC_DIR)/
	$(VENV_BIN)/mypy $(SRC_DIR)/processscope/
	@echo "✓ Lint complete"

## format: Format code
format:
	@echo "━━━ Formatting Code ━━━"
	$(VENV_BIN)/ruff format $(SRC_DIR)/
	$(VENV_BIN)/ruff check --fix $(SRC_DIR)/
	@echo "✓ Format complete"

## package-tar: Create tar.gz distribution
package-tar: build
	@echo "━━━ Creating tar.gz package ━━━"
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)
	# Create installation layout
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/bin
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/lib
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/share/doc
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/plugins
	@mkdir -p $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/etc/$(APP_NAME)
	# Copy files
	@cp -r $(BUILD_DIR)/*.whl $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/lib/
	@cp $(CONFIGS_DIR)/processscope.yaml $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/etc/$(APP_NAME)/
	@cp $(DIST_DIR)/systemd/processscope.service $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/
	@cp $(DIST_DIR)/logrotate/processscope $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/
	@cp $(DIST_DIR)/install.sh $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/
	@cp README.md $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/opt/$(APP_NAME)/share/doc/
	@chmod +x $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/install.sh
	# Create tarball
	@cd $(OUTPUT_DIR) && tar -czf $(APP_NAME)-$(VERSION)-$(OS)-$(ARCH).tar.gz $(APP_NAME)-$(VERSION)/
	@rm -rf $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)/
	@echo "✓ Package: $(OUTPUT_DIR)/$(APP_NAME)-$(VERSION)-$(OS)-$(ARCH).tar.gz"

## package-deb: Create .deb package
package-deb: build
	@echo "━━━ Creating DEB package ━━━"
	@mkdir -p $(OUTPUT_DIR)
	@./scripts/build-deb.sh $(VERSION) $(BUILD_NUMBER) $(ARCH)
	@echo "✓ DEB package created"

## package-rpm: Create .rpm package
package-rpm: build
	@echo "━━━ Creating RPM package ━━━"
	@mkdir -p $(OUTPUT_DIR)
	@./scripts/build-rpm.sh $(VERSION) $(BUILD_NUMBER) $(ARCH)
	@echo "✓ RPM package created"

## clean: Remove all build artifacts
clean:
	@echo "━━━ Cleaning ━━━"
	rm -rf $(BUILD_DIR) $(OUTPUT_DIR) $(VENV)
	rm -rf $(SRC_DIR)/processscope.egg-info
	rm -rf $(SRC_DIR)/processscope/dashboard
	rm -rf $(SRC_DIR)/processscope/_build_meta.json
	rm -rf $(WEB_DIR)/node_modules $(WEB_DIR)/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Clean complete"

## all: Full build pipeline (build + package)
all: build package-tar
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  $(APP_DISPLAY) v$(VERSION) — Build Complete"
	@echo "  Build: $(BUILD_NUMBER)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
