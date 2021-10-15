src-dirs = fourget

.PHONY: all
all: pydocstyle isort black flake8 mypy

.PHONY: mypy
mypy:
	mypy $(src-dirs)

.PHONY: isort
isort:
	isort $(src-dirs)

.PHONY: flake8
flake8:
	flake8 $(src-dirs)

.PHONY: black
black:
	black $(src-dirs)

.PHONY: pydocstyle
pydocstyle:
	pydocstyle $(src-dirs)
