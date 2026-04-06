define HELP_MESSAGE
VLCaption - Auto-generate subtitles in VLC

# Installing

1. Install uv: https://docs.astral.sh/uv/getting-started/installation/
2. Install the package: `uv sync --extra dev`

# Running Tests

1. Run autoformatting: `make format`
2. Run static checks: `make static-checks`
3. Run unit tests: `make test`

endef
export HELP_MESSAGE

all:
	@echo "$$HELP_MESSAGE"
.PHONY: all

# ------------------------ #
#        PyPI Build        #
# ------------------------ #

build-for-pypi:
	@uv build
.PHONY: build-for-pypi

push-to-pypi: build-for-pypi
	@uv publish
.PHONY: push-to-pypi

# ------------------------ #
#       Static Checks      #
# ------------------------ #

excluded := ./.venv
exclude_args := $(foreach d,$(excluded),-path "$(d)" -prune -o)

py-files := $(shell find . $(exclude_args) -name '*.py' -print)

format:
	@uv run ruff format $(py-files)
	@uv run ruff check --fix $(py-files)
.PHONY: format

static-checks:
	@uv run ruff format --check $(py-files)
	@uv run ruff check $(py-files)
	@uv run mypy --install-types --non-interactive $(py-files)
.PHONY: static-checks

# ------------------------ #
#        Unit tests        #
# ------------------------ #

test:
	uv run python -m pytest
.PHONY: test
