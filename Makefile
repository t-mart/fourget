src-dirs = fourget

.PHONY: all
all: black flake8 isort mypy

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
