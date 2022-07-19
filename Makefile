all: generate-vhdl dist ## build ctucan python package

generate-vhdl: ctucan/vhdl ## recreate ctucan/vhdl directory

test: ## run tests
	python3 -m pytest -v tests/

test-dev: ## run tests in verbose mode
	python3 -m pytest -vvv --log-cli-level=INFO tests/

format: ## format python sources
	python3 -m yapf --exclude=third-party/ -i -r .

clean: ## clean build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

dist: clean ## package the sources
	python3 setup.py sdist
	python3 setup.py bdist_wheel

.PHONY: test test-dev format clean all generate-vhdl

ctucan/vhdl: ./scripts/generate_vhdl_sources.py third-party/ctucanfd_ip_core
	python3 ./scripts/generate_vhdl_sources.py -f -p patches/* third-party/ctucanfd_ip_core $@

HELP_COLUMN_SPAN = 15
HELP_FORMAT_STRING = "\033[36m%-${HELP_COLUMN_SPAN}s\033[0m %s\n"
help: ## show this help
	@echo Here is the list of available targets:
	@echo ""
	@grep -E '^[a-zA-Z_\/-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf ${HELP_FORMAT_STRING}, $$1, $$2}'
	@echo ""

.PHONY: help
.DEFAULT_GOAL := help
