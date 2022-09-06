.DEFAULT_GOAL := all
isort = isort ot2_driver
black = black --target-version py39 ot2_driver

.PHONY: format
format:
	$(isort)
	$(black)

.PHONY: lint
lint:
	$(black) --check --diff
	flake8 ot2_driver/
	pydocstyle ot2_driver/ --count



.PHONY: mypy
mypy:
	mypy --config-file setup.cfg --package ot2_driver/
	mypy --config-file setup.cfg ot2_driver/

.PHONY: all
all: format lint
